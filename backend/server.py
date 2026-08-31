import os
import logging
import uuid
import re
import secrets
from urllib.parse import quote_plus, urlparse
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Annotated, Any, Literal

import requests
import asyncio
from fastapi import FastAPI, APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, ConfigDict, BeforeValidator, HttpUrl
from bson import ObjectId

from share_verify import (
    SHARE_TARGETS,
    POST_TARGETS,
    fixture_html,
    is_crawler_ua,
    test_fixtures_enabled,
    verify_post,
)


ROOT_DIR = Path(__file__).parent

# Load every place Render / local can stash secrets. Never crash if a file is missing.
for _env_path in (
    ROOT_DIR / ".env",
    ROOT_DIR / "atlas-credentials.env",
    Path("/etc/secrets/.env"),
    Path("/etc/secrets/atlas-credentials.env"),
    Path("/etc/secrets/atlas-credentials"),
):
    if _env_path.is_file():
        load_dotenv(_env_path, override=False)

# Render secret files are sometimes one file per variable
_secrets = Path("/etc/secrets")
if _secrets.is_dir():
    for _f in _secrets.iterdir():
        if _f.is_file() and _f.name in {
            "MONGO_URL", "MONGODB_URI", "MONGODB_USERNAME", "MONGODB_PASSWORD", "DB_NAME",
        } and not os.environ.get(_f.name):
            os.environ[_f.name] = _f.read_text(encoding="utf-8").strip().strip('"').strip("'")

# ---------------------------------------------------------------------
# Environment / DB
# ---------------------------------------------------------------------
# Public Atlas hostname for this project (not a secret). Used if only user/pass are set.
DEFAULT_ATLAS_HOST = "frshboard.15rissw.mongodb.net"


def _env(name: str, default: str = "") -> str:
    raw = os.environ.get(name, default) or default
    return str(raw).strip().strip('"').strip("'")


def _mongo_url() -> str:
    """Always return a mongodb:// URI. Missing env → local placeholder so gunicorn still boots."""
    raw = _env("MONGO_URL") or _env("MONGODB_URI")
    if raw.lower().startswith("mongo_url="):
        raw = raw.split("=", 1)[1].strip().strip('"').strip("'")
    user = _env("MONGODB_USERNAME")
    password = _env("MONGODB_PASSWORD")

    host_only = DEFAULT_ATLAS_HOST
    if raw:
        host_part = raw.split("://", 1)[-1]
        if "@" in host_part:
            host_part = host_part.split("@", 1)[1]
        host_part = host_part.split("?")[0].rstrip("/")
        host_only = host_part.split("/")[0] or DEFAULT_ATLAS_HOST

    atlas = "mongodb.net" in host_only
    scheme = "mongodb+srv" if atlas else ("mongodb+srv" if raw.startswith("mongodb+srv://") else "mongodb")

    if user and password:
        url = f"{scheme}://{quote_plus(user)}:{quote_plus(password)}@{host_only}"
    elif raw.startswith(("mongodb://", "mongodb+srv://")):
        url = raw.split("?")[0]
        if "@" in url and "://" in url:
            creds, host = url.split("@", 1)
            kind, rest = creds.split("://", 1)
            if ":" in rest:
                u, p = rest.split(":", 1)
                url = f"{kind}://{quote_plus(u)}:{quote_plus(p)}@{host.split('/')[0]}"
    else:
        logging.error(
            "No Mongo credentials found. Set MONGODB_USERNAME and MONGODB_PASSWORD on Render. "
            "Booting anyway so /health stays up."
        )
        return "mongodb://127.0.0.1:27017"

    q = ["retryWrites=true", "w=majority"]
    if atlas:
        q.append("authSource=admin")
    return url + "?" + "&".join(q)


mongo_url = _mongo_url()
db_name = _env("DB_NAME") or "freshboard"
client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=8000)
db = client[db_name]

STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY", "")

# IST timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))

CATEGORIES = [
    "SaaS", "AI", "Voice AI", "CRM", "DevTools", "Fintech",
    "Healthtech", "E-commerce", "Productivity", "Social", "Gaming", "Other",
]

MIN_BID = 1.0
BOOST_PRICE = 10.0
BOOST_REACH = 5

# ---------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------
def _oid_to_str(v: Any) -> Any:
    if isinstance(v, ObjectId):
        return str(v)
    return v

PyObjectId = Annotated[str, BeforeValidator(_oid_to_str)]


class BaseDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True, extra="ignore")
    id: Optional[PyObjectId] = Field(default=None, alias="_id")


class Listing(BaseDocument):
    listing_type: Literal["product", "social"]
    title: str
    tagline: str
    description: Optional[str] = ""
    url: str
    image_url: str
    # products only
    category: Optional[str] = None
    # socials only
    platform: Optional[Literal["x", "instagram"]] = None
    # bidding
    current_bid: float = 0.0
    boosted: bool = False
    boost_count: int = 0
    # timestamps
    created_at_iso: str = ""
    last_bid_at_iso: str = ""


class SubmitPayload(BaseModel):
    listing_type: Literal["product", "social"]
    title: str = Field(min_length=1, max_length=100)
    tagline: str = Field(min_length=1, max_length=140)
    description: Optional[str] = Field(default="", max_length=1000)
    url: str
    image_url: str
    category: Optional[str] = None
    platform: Optional[Literal["x", "instagram"]] = None


class ShareRequest(BaseModel):
    target: Literal["x", "linkedin", "reddit", "facebook", "whatsapp"]
    post_url: Optional[str] = Field(default=None, max_length=2000)


class ShareStartRequest(BaseModel):
    listing_id: str
    target: Literal["x", "linkedin", "reddit", "facebook", "whatsapp"]
    origin: Optional[str] = None


class ShareVerifyRequest(BaseModel):
    token: str = Field(min_length=6, max_length=80)
    post_url: Optional[str] = Field(default=None, max_length=2000)


class OutbidPayload(BaseModel):
    listing_id: str
    bid_amount: float = Field(ge=MIN_BID)
    add_boost: bool = False
    origin_url: str


CREDITS_PER_SHARE = 5
WELCOME_CREDITS = 5


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def ist_day_start_utc() -> datetime:
    """Return the UTC datetime for the last midnight IST (today's IST 00:00)."""
    now_ist = datetime.now(IST)
    day_start_ist = now_ist.replace(hour=0, minute=0, second=0, microsecond=0)
    return day_start_ist.astimezone(timezone.utc)


def next_ist_midnight_utc() -> datetime:
    now_ist = datetime.now(IST)
    tomorrow_ist = (now_ist + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return tomorrow_ist.astimezone(timezone.utc)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


URL_REGEX = re.compile(r"^https?://[^\s]+$", re.IGNORECASE)


def validate_url(u: str) -> str:
    if not URL_REGEX.match(u.strip()):
        raise HTTPException(400, f"Invalid URL: {u}")
    return u.strip()


def client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for") or ""
    if xff:
        return xff.split(",")[0].strip() or "unknown"
    return request.client.host if request.client else "unknown"


# ---------------------------------------------------------------------
# App / router
# ---------------------------------------------------------------------
app = FastAPI(title="FreshBoard.lol API")
api = APIRouter(prefix="/api")


@app.get("/")
@app.get("/health")
async def health():
    return {"service": "FreshBoard.lol", "status": "ok"}


@api.get("/")
async def root():
    return {"service": "FreshBoard.lol", "status": "ok"}


@api.get("/config")
async def get_config():
    return {
        "categories": CATEGORIES,
        "min_bid": MIN_BID,
        "boost_price": BOOST_PRICE,
        "boost_reach": BOOST_REACH,
        "credits_per_share": CREDITS_PER_SHARE,
        "welcome_credits": WELCOME_CREDITS,
        "share_targets": list(SHARE_TARGETS),
    }


@api.get("/reset-info")
async def reset_info():
    nxt = next_ist_midnight_utc()
    now = datetime.now(timezone.utc)
    return {
        "next_reset_utc": nxt.isoformat(),
        "server_now_utc": now.isoformat(),
        "seconds_until_reset": int((nxt - now).total_seconds()),
        "timezone": "IST (UTC+5:30)",
    }


def _serialize(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    return doc


@api.get("/board")
async def get_board(category: Optional[str] = None):
    """Return today's active listings, ranked by bid, grouped by section."""
    day_start = ist_day_start_utc().isoformat()
    query = {"created_at_iso": {"$gte": day_start}, "current_bid": {"$gt": 0}}
    cursor = db.listings.find(query).sort([("current_bid", -1), ("last_bid_at_iso", -1)])
    products, socials = [], []
    rank_p, rank_s = 0, 0
    async for doc in cursor:
        item = _serialize(doc)
        if item["listing_type"] == "product":
            if category and category != "All" and item.get("category") != category:
                continue
            rank_p += 1
            item["rank"] = rank_p
            products.append(item)
        else:
            rank_s += 1
            item["rank"] = rank_s
            socials.append(item)
    return {
        "products": products,
        "socials": socials,
        "reset": await reset_info(),
    }


@api.get("/companies")
async def search_companies(q: Optional[str] = None, limit: int = 20):
    """Today's listings for the share-on-behalf typeahead. Exact title matches first."""
    day_start = ist_day_start_utc().isoformat()
    query: dict = {"created_at_iso": {"$gte": day_start}}
    needle = (q or "").strip()
    if needle:
        query["title"] = {"$regex": re.escape(needle), "$options": "i"}
    limit = min(max(limit, 1), 50)
    cursor = db.listings.find(query).sort("current_bid", -1).limit(limit)
    items = []
    async for doc in cursor:
        items.append({
            "id": str(doc["_id"]),
            "title": doc.get("title"),
            "image_url": doc.get("image_url"),
            "credits": float(doc.get("current_bid", 0)),
            "listing_type": doc.get("listing_type"),
            "category": doc.get("category"),
        })
    if needle:
        low = needle.lower()

        def _rank(it):
            t = (it.get("title") or "").lower()
            if t == low:
                return (0, -it["credits"])
            if t.startswith(low):
                return (1, -it["credits"])
            return (2, -it["credits"])

        items.sort(key=_rank)
    return {"items": items}


@api.get("/listings/{listing_id}")
async def get_listing(listing_id: str):
    try:
        oid = ObjectId(listing_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    doc = await db.listings.find_one({"_id": oid})
    if not doc:
        raise HTTPException(404, "Listing not found")
    return _serialize(doc)


@api.post("/listings/{listing_id}/click")
async def track_click(listing_id: str):
    try:
        oid = ObjectId(listing_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    result = await db.listings.update_one({"_id": oid}, {"$inc": {"click_count": 1}})
    if result.matched_count == 0:
        raise HTTPException(404, "Listing not found")
    return {"ok": True}


@api.get("/activity")
async def get_activity(limit: int = 20):
    """Return latest activity: recent share events (credits earned) and new listings."""
    limit = min(max(limit, 1), 50)
    events = []

    async for ev in db.share_events.find({}).sort("created_at", -1).limit(limit):
        events.append({
            "kind": "share",
            "at": ev.get("created_at"),
            "listing_id": ev.get("listing_id"),
            "target": ev.get("target"),
        })

    day_start = ist_day_start_utc().isoformat()
    async for lst in db.listings.find(
        {"created_at_iso": {"$gte": day_start}}
    ).sort("created_at_iso", -1).limit(limit):
        events.append({
            "kind": "new_listing",
            "at": lst.get("created_at_iso"),
            "listing_id": str(lst["_id"]),
        })

    events.sort(key=lambda e: e.get("at") or "", reverse=True)
    events = events[:limit]

    out = []
    for e in events:
        listing = None
        if e.get("listing_id"):
            try:
                listing = await db.listings.find_one({"_id": ObjectId(e["listing_id"])})
            except Exception:
                listing = None
        if not listing:
            continue
        rank = None
        if listing.get("created_at_iso", "") >= day_start:
            bid = listing.get("current_bid", 0)
            last = listing.get("last_bid_at_iso") or ""
            higher = await db.listings.count_documents({
                "listing_type": listing["listing_type"],
                "created_at_iso": {"$gte": day_start},
                "$or": [
                    {"current_bid": {"$gt": bid}},
                    {"current_bid": bid, "last_bid_at_iso": {"$gt": last}},
                ],
            })
            rank = higher + 1
        out.append({
            "id": str(listing["_id"]),
            "title": listing.get("title"),
            "image_url": listing.get("image_url"),
            "url": listing.get("url"),
            "listing_type": listing.get("listing_type"),
            "category": listing.get("category"),
            "platform": listing.get("platform"),
            "current_bid": listing.get("current_bid"),
            "rank": rank,
            "purpose": "share" if e["kind"] == "share" else "new_listing",
            "target": e.get("target"),
            "at": e.get("at"),
        })
    return {"items": out}


@api.get("/stats")
async def get_stats():
    """Aggregate totals since launch (credit-based mechanic)."""
    day_start = ist_day_start_utc().isoformat()
    active_today = await db.listings.count_documents({"created_at_iso": {"$gte": day_start}})
    total_shares = await db.share_events.count_documents({})
    agg = await db.listings.aggregate([
        {"$group": {"_id": None, "total_credits": {"$sum": "$current_bid"}}}
    ]).to_list(1)
    total_credits = float(agg[0]["total_credits"]) if agg else 0.0
    launched_at = os.environ.get("APP_LAUNCHED_AT", "2026-02-01T00:00:00+00:00")
    return {
        "total_credits": total_credits,
        "total_shares": total_shares,
        "active_today": active_today,
        "launched_at": launched_at,
    }


@api.get("/top-today")
async def top_today(limit: int = 3):
    """Top-N listings by bid today (mixed products+socials)."""
    day_start = ist_day_start_utc().isoformat()
    cursor = db.listings.find(
        {"created_at_iso": {"$gte": day_start}, "current_bid": {"$gt": 0}}
    ).sort([("current_bid", -1), ("last_bid_at_iso", -1)]).limit(min(max(limit, 1), 10))
    items = []
    async for doc in cursor:
        items.append(_serialize(doc))
    return {"items": items}


@api.get("/yesterday-top")
async def yesterday_top():
    """Yesterday's IST-day #1 listing (winner of the last completed day)."""
    now_ist = datetime.now(IST)
    today_start_ist = now_ist.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start_ist = today_start_ist - timedelta(days=1)
    y_start = yesterday_start_ist.astimezone(timezone.utc).isoformat()
    y_end = today_start_ist.astimezone(timezone.utc).isoformat()
    doc = await db.listings.find_one(
        {"created_at_iso": {"$gte": y_start, "$lt": y_end}, "current_bid": {"$gt": 0}},
        sort=[("current_bid", -1), ("last_bid_at_iso", -1)],
    )
    if not doc:
        return {"item": None}
    return {"item": _serialize(doc)}


class PreviewRequest(BaseModel):
    url: str


_TITLE_RE = re.compile(r"<title[^>]*>([^<]+)</title>", re.IGNORECASE | re.DOTALL)
_META_RE = re.compile(
    r"""<meta\s+[^>]*?(?:property|name)\s*=\s*['"]([^'"]+)['"][^>]*?content\s*=\s*['"]([^'"]*)['"][^>]*?/?>""",
    re.IGNORECASE,
)
_META_RE_ALT = re.compile(
    r"""<meta\s+[^>]*?content\s*=\s*['"]([^'"]*)['"][^>]*?(?:property|name)\s*=\s*['"]([^'"]+)['"][^>]*?/?>""",
    re.IGNORECASE,
)


def _clean(text: str, max_len: int) -> str:
    if not text:
        return ""
    t = re.sub(r"\s+", " ", text).strip()
    return t[:max_len]


@api.post("/preview")
async def preview_url(payload: PreviewRequest):
    """Fetch OpenGraph metadata for a URL (title, tagline, image)."""
    url = payload.url.strip()
    if not URL_REGEX.match(url):
        raise HTTPException(400, "Invalid URL")

    parsed = urlparse(url)
    domain = parsed.netloc

    title = ""
    tagline = ""
    image_url = ""

    try:
        r = requests.get(
            url,
            timeout=6,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; FreshBoardPreviewBot/1.0)",
                "Accept": "text/html,application/xhtml+xml",
            },
            allow_redirects=True,
        )
        html = r.text if r.status_code < 400 else ""
    except Exception as e:
        logging.info("preview fetch failed: %s", e)
        html = ""

    if html:
        meta = {}
        for m in _META_RE.finditer(html):
            k, v = m.group(1).lower(), m.group(2)
            meta.setdefault(k, v)
        for m in _META_RE_ALT.finditer(html):
            v, k = m.group(1), m.group(2).lower()
            meta.setdefault(k, v)

        title = meta.get("og:title") or meta.get("twitter:title") or ""
        if not title:
            tm = _TITLE_RE.search(html)
            if tm:
                title = tm.group(1)
        tagline = meta.get("og:description") or meta.get("twitter:description") or meta.get("description") or ""
        image_url = meta.get("og:image") or meta.get("twitter:image") or ""

        # Absolute-ize image URL
        if image_url and image_url.startswith("//"):
            image_url = f"{parsed.scheme}:{image_url}"
        elif image_url and image_url.startswith("/"):
            image_url = f"{parsed.scheme}://{parsed.netloc}{image_url}"

    if not image_url and domain:
        image_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=256"

    return {
        "title": _clean(title, 100) or domain,
        "tagline": _clean(tagline, 140),
        "image_url": image_url,
        "domain": domain,
    }



# ---------------------------------------------------------------------
# Stripe payments
# ---------------------------------------------------------------------
class WSManager:
    def __init__(self):
        self.conns: set = set()
        self.lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self.lock:
            self.conns.add(ws)

    async def disconnect(self, ws: WebSocket):
        async with self.lock:
            self.conns.discard(ws)

    async def broadcast(self, msg: dict):
        async with self.lock:
            targets = list(self.conns)
        dead = []
        for ws in targets:
            try:
                await ws.send_json(msg)
            except Exception:
                dead.append(ws)
        if dead:
            async with self.lock:
                for ws in dead:
                    self.conns.discard(ws)


ws_manager = WSManager()


@app.websocket("/api/ws/board")
async def ws_board(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        # Send a hello then keep the connection alive.
        await ws.send_json({"type": "hello", "at": now_iso()})
        while True:
            # Discard anything the client sends; used only as keep-alive
            await ws.receive_text()
    except WebSocketDisconnect:
        await ws_manager.disconnect(ws)
    except Exception:
        await ws_manager.disconnect(ws)


def _payments_disabled():
    raise HTTPException(503, "Card payments are not enabled. Share to earn credits.")


async def _create_checkout(
    request: Request,
    amount: float,
    purpose: str,
    origin_url: str,
    metadata: dict,
) -> dict:
    _payments_disabled()


@api.post("/submit")
async def submit_listing(payload: SubmitPayload, request: Request):
    """Free submission: instantly places the listing on the board with welcome credits.
    Rank is earned by sharing; no money required for the initial mechanic."""
    validate_url(payload.url)
    validate_url(payload.image_url)
    if payload.listing_type == "product":
        if not payload.category or payload.category not in CATEGORIES:
            raise HTTPException(400, "Valid category required for products")
    else:
        if payload.platform not in ("x", "instagram"):
            raise HTTPException(400, "Platform must be 'x' or 'instagram' for social")

    now = now_iso()
    doc = {
        "listing_type": payload.listing_type,
        "title": payload.title,
        "tagline": payload.tagline,
        "description": payload.description or "",
        "url": payload.url,
        "image_url": payload.image_url,
        "category": payload.category or None,
        "platform": payload.platform or None,
        "current_bid": float(WELCOME_CREDITS),
        "boosted": False,
        "boost_count": 0,
        "click_count": 0,
        "created_at_iso": now,
        "last_bid_at_iso": now,
    }
    result = await db.listings.insert_one(doc)
    listing_id = str(result.inserted_id)
    try:
        await ws_manager.broadcast({
            "type": "board_update",
            "purpose": "new_listing",
            "listing_id": listing_id,
            "credits": float(WELCOME_CREDITS),
            "at": now,
        })
    except Exception:
        pass
    return {
        "listing_id": listing_id,
        "credits": float(WELCOME_CREDITS),
        "credits_per_share": CREDITS_PER_SHARE,
    }


def _share_template(title: str, track_url: Optional[str] = None) -> str:
    line = f"Check out {title} in freshboard.lol"
    if track_url:
        return f"{line} {track_url}"
    return line


async def _apply_credit(
    listing_id: str,
    oid: ObjectId,
    doc: dict,
    target: str,
    sharer_ip: str,
    *,
    post_url: Optional[str] = None,
    post_url_norm: Optional[str] = None,
    token: Optional[str] = None,
    verify_method: str = "post_fetch",
    visitor_ip: Optional[str] = None,
) -> dict:
    """Idempotent +5 after a share has already been proven."""
    existing = await db.share_events.find_one({
        "listing_id": listing_id,
        "target": target,
        "ip": sharer_ip,
    })
    if existing:
        return {
            "credited": False,
            "credits": float(doc.get("current_bid", 0)),
            "reason": "already_shared",
            "listing_id": listing_id,
        }

    if post_url_norm:
        used = await db.share_events.find_one({"post_url_norm": post_url_norm})
        if used:
            return {
                "credited": False,
                "credits": float(doc.get("current_bid", 0)),
                "reason": "post_already_used",
                "listing_id": listing_id,
            }

    now = now_iso()
    await db.share_events.insert_one({
        "listing_id": listing_id,
        "title": doc.get("title") or "",
        "target": target,
        "ip": sharer_ip,
        "visitor_ip": visitor_ip,
        "post_url": (post_url or "").strip() or None,
        "post_url_norm": post_url_norm,
        "token": token,
        "verify_method": verify_method,
        "created_at": now,
    })
    await db.listings.update_one(
        {"_id": oid},
        {
            "$inc": {"current_bid": CREDITS_PER_SHARE},
            "$set": {"last_bid_at_iso": now},
        },
    )
    updated = await db.listings.find_one({"_id": oid})
    new_credits = float(updated.get("current_bid", 0))
    try:
        await ws_manager.broadcast({
            "type": "board_update",
            "purpose": "share",
            "listing_id": listing_id,
            "credits": new_credits,
            "target": target,
            "at": now,
        })
    except Exception:
        pass
    return {
        "credited": True,
        "credits": new_credits,
        "target": target,
        "listing_id": listing_id,
    }


async def _credit_verified_share(
    listing_id: str,
    oid: ObjectId,
    doc: dict,
    target: str,
    ip: str,
    post_url: str,
    token: Optional[str] = None,
) -> dict:
    """Fetch the public post; only then award +CREDITS_PER_SHARE."""
    if target == "whatsapp":
        raise HTTPException(
            400,
            "WhatsApp is counted when someone opens your unique FreshBoard link — not by pasting a URL.",
        )
    try:
        norm = verify_post(target, post_url, doc.get("title") or "")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return await _apply_credit(
        listing_id, oid, doc, target, ip,
        post_url=post_url, post_url_norm=norm, token=token, verify_method="post_fetch",
    )


@api.get("/dev/share-fixture")
async def share_fixture(company: str = "", token: str = "", blank: str = "0"):
    """HTML stand-in for a public post. Only available against the test database."""
    if not test_fixtures_enabled():
        raise HTTPException(404, "Not found")
    return HTMLResponse(fixture_html(company, token, blank == "1"))


@api.post("/share/start")
async def share_start(payload: ShareStartRequest, request: Request):
    """Open a share attempt. Credits are NOT awarded until the post (or WhatsApp link hit) is proven."""
    try:
        oid = ObjectId(payload.listing_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    doc = await db.listings.find_one({"_id": oid})
    if not doc:
        raise HTTPException(404, "Listing not found")

    ip = client_ip(request)
    hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    recent = await db.share_intents.count_documents({"ip": ip, "created_at": {"$gte": hour_ago}})
    if recent >= 20:
        raise HTTPException(429, "Too many share attempts. Try later.")

    token = secrets.token_urlsafe(12)
    now = now_iso()
    origin = (payload.origin or "").rstrip("/")
    track_path = f"/s/{token}"
    track_url = f"{origin}{track_path}" if origin else track_path
    title = doc.get("title") or ""
    await db.share_intents.insert_one({
        "token": token,
        "listing_id": payload.listing_id,
        "title": title,
        "target": payload.target,
        "ip": ip,
        "origin": origin or None,
        "status": "pending",
        "created_at": now,
    })
    template = _share_template(title, track_url if payload.target == "whatsapp" else None)
    return {
        "token": token,
        "listing_id": payload.listing_id,
        "title": title,
        "target": payload.target,
        "template": template,
        "track_path": track_path,
        "verify_method": "track_hit" if payload.target == "whatsapp" else "post_fetch",
        "credits_per_share": CREDITS_PER_SHARE,
    }


@api.post("/share/verify")
async def share_verify(payload: ShareVerifyRequest, request: Request):
    """Award +5 only after the published post is fetched and matches the template."""
    intent = await db.share_intents.find_one({"token": payload.token})
    if not intent:
        raise HTTPException(404, "Share session not found. Start again.")
    created = intent.get("created_at") or ""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    if created < cutoff:
        raise HTTPException(400, "Share expired. Start again.")
    if intent.get("status") == "credited":
        try:
            oid = ObjectId(intent["listing_id"])
        except Exception:
            oid = None
        doc = await db.listings.find_one({"_id": oid}) if oid else None
        return {
            "credited": False,
            "credits": float((doc or {}).get("current_bid", 0)),
            "reason": "already_shared",
            "listing_id": intent["listing_id"],
        }

    try:
        oid = ObjectId(intent["listing_id"])
    except Exception:
        raise HTTPException(400, "Invalid id")
    doc = await db.listings.find_one({"_id": oid})
    if not doc:
        raise HTTPException(404, "Listing not found")

    if intent.get("target") == "whatsapp":
        raise HTTPException(
            400,
            "WhatsApp is counted when someone opens your unique FreshBoard link.",
        )
    if not (payload.post_url or "").strip():
        raise HTTPException(400, "Paste the live post URL after you publish.")

    ip = client_ip(request)
    result = await _credit_verified_share(
        intent["listing_id"], oid, doc, intent["target"], ip, payload.post_url, payload.token,
    )
    if result.get("credited"):
        await db.share_intents.update_one(
            {"token": payload.token},
            {"$set": {"status": "credited", "post_url": payload.post_url.strip()}},
        )
    return result


@api.get("/share/status/{token}")
async def share_status(token: str):
    intent = await db.share_intents.find_one({"token": token})
    if not intent:
        raise HTTPException(404, "Share session not found")
    try:
        oid = ObjectId(intent["listing_id"])
    except Exception:
        oid = None
    doc = await db.listings.find_one({"_id": oid}) if oid else None
    return {
        "token": token,
        "status": intent.get("status"),
        "target": intent.get("target"),
        "listing_id": intent["listing_id"],
        "title": intent.get("title"),
        "credited": intent.get("status") == "credited",
        "credits": float((doc or {}).get("current_bid", 0)),
    }


@api.get("/share/hit/{token}")
async def share_hit(token: str, request: Request):
    """WhatsApp proof: a human opens the unique link. Crawlers and the sharer's own IP do not count."""
    intent = await db.share_intents.find_one({"token": token})
    if not intent:
        raise HTTPException(404, "Share link not found")
    try:
        oid = ObjectId(intent["listing_id"])
    except Exception:
        raise HTTPException(400, "Invalid id")
    doc = await db.listings.find_one({"_id": oid})
    if not doc:
        raise HTTPException(404, "Listing not found")

    visitor = client_ip(request)
    ua = request.headers.get("user-agent") or ""
    crawler = is_crawler_ua(ua)
    now = now_iso()
    await db.share_hits.insert_one({
        "token": token,
        "listing_id": intent["listing_id"],
        "ip": visitor,
        "ua": ua[:300],
        "kind": "crawler" if crawler else "human",
        "created_at": now,
    })

    redirect = f"/product/{intent['listing_id']}"
    base = {
        "listing_id": intent["listing_id"],
        "title": intent.get("title"),
        "redirect": redirect,
        "target": intent.get("target"),
    }

    if intent.get("target") != "whatsapp":
        return {**base, "credited": False, "reason": "not_whatsapp", "credits": float(doc.get("current_bid", 0))}
    if intent.get("status") == "credited":
        return {**base, "credited": False, "reason": "already_shared", "credits": float(doc.get("current_bid", 0))}
    if crawler:
        return {**base, "credited": False, "reason": "preview_fetch", "credits": float(doc.get("current_bid", 0))}
    if visitor == intent.get("ip"):
        return {**base, "credited": False, "reason": "same_device", "credits": float(doc.get("current_bid", 0))}

    result = await _apply_credit(
        intent["listing_id"], oid, doc, "whatsapp", intent.get("ip") or visitor,
        post_url_norm=f"whatsapp:hit:{token}",
        token=token,
        verify_method="track_hit",
        visitor_ip=visitor,
    )
    if result.get("credited"):
        await db.share_intents.update_one(
            {"token": token},
            {"$set": {"status": "credited", "credited_at": now, "visitor_ip": visitor}},
        )
    return {**base, **result}


@api.post("/listings/{listing_id}/share")
async def share_listing(listing_id: str, payload: ShareRequest, request: Request):
    """One-shot: verify a published post URL, then +CREDITS_PER_SHARE on that company."""
    try:
        oid = ObjectId(listing_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    doc = await db.listings.find_one({"_id": oid})
    if not doc:
        raise HTTPException(404, "Listing not found")
    if payload.target not in POST_TARGETS:
        raise HTTPException(
            400,
            "WhatsApp needs /share/start plus a click on the unique link.",
        )
    if not (payload.post_url or "").strip():
        raise HTTPException(422, "post_url required")

    ip = client_ip(request)
    return await _credit_verified_share(
        listing_id, oid, doc, payload.target, ip, payload.post_url,
    )


@api.post("/outbid")
async def outbid_listing(payload: OutbidPayload, request: Request):
    try:
        oid = ObjectId(payload.listing_id)
    except Exception:
        raise HTTPException(400, "Invalid listing id")
    doc = await db.listings.find_one({"_id": oid})
    if not doc:
        raise HTTPException(404, "Listing not found")
    if payload.bid_amount <= float(doc.get("current_bid", 0)):
        raise HTTPException(
            400,
            f"Bid must be greater than current bid of ${doc['current_bid']:.2f}",
        )
    total_amount = payload.bid_amount + (BOOST_PRICE if payload.add_boost else 0)
    metadata = {
        "kind": "outbid",
        "listing_id": payload.listing_id,
        "bid_amount": str(payload.bid_amount),
        "add_boost": "1" if payload.add_boost else "0",
    }
    return await _create_checkout(
        request, total_amount, "outbid", payload.origin_url, metadata
    )


async def _apply_paid_transaction(session_id: str, session_metadata: Optional[dict] = None):
    """Idempotently apply the effects of a paid transaction (listing create / bid update)."""
    txn = await db.payment_transactions.find_one({"session_id": session_id})
    if not txn:
        return
    if txn.get("payment_status") == "paid":
        return
    md = txn.get("metadata") or session_metadata or {}
    purpose = txn.get("purpose") or md.get("purpose")
    now = now_iso()

    broadcast_payload = {"type": "board_update", "purpose": purpose, "at": now}

    if purpose == "new_listing":
        bid_amount = float(md.get("bid_amount", txn.get("amount", 0)))
        add_boost = md.get("add_boost") == "1"
        listing_doc = {
            "listing_type": md.get("listing_type"),
            "title": md.get("title"),
            "tagline": md.get("tagline"),
            "description": md.get("description", ""),
            "url": md.get("url"),
            "image_url": md.get("image_url"),
            "category": md.get("category") or None,
            "platform": md.get("platform") or None,
            "current_bid": bid_amount,
            "boosted": add_boost,
            "boost_count": BOOST_REACH if add_boost else 0,
            "click_count": 0,
            "created_at_iso": now,
            "last_bid_at_iso": now,
        }
        result = await db.listings.insert_one(listing_doc)
        broadcast_payload["listing_id"] = str(result.inserted_id)
        broadcast_payload["listing_type"] = listing_doc["listing_type"]
        broadcast_payload["title"] = listing_doc["title"]
        broadcast_payload["current_bid"] = bid_amount
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {
                "status": "completed",
                "payment_status": "paid",
                "listing_id": str(result.inserted_id),
                "updated_at": now,
            }},
        )
    elif purpose == "outbid":
        try:
            oid = ObjectId(md.get("listing_id"))
        except Exception:
            oid = None
        bid_amount = float(md.get("bid_amount", txn.get("amount", 0)))
        add_boost = md.get("add_boost") == "1"
        if oid:
            update = {
                "current_bid": bid_amount,
                "last_bid_at_iso": now,
            }
            if add_boost:
                update["boosted"] = True
            inc = {"boost_count": BOOST_REACH} if add_boost else None
            u = {"$set": update}
            if inc:
                u["$inc"] = inc
            await db.listings.update_one({"_id": oid}, u)
            broadcast_payload["listing_id"] = str(oid)
            broadcast_payload["current_bid"] = bid_amount
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {
                "status": "completed",
                "payment_status": "paid",
                "updated_at": now,
            }},
        )

    # Push to any connected clients (best effort, non-blocking)
    try:
        await ws_manager.broadcast(broadcast_payload)
    except Exception as e:
        logging.info("ws broadcast failed: %s", e)


@api.get("/payments/status/{session_id}")
async def payment_status(session_id: str, request: Request):
    record = await db.payment_transactions.find_one({"session_id": session_id})
    if not record:
        raise HTTPException(404, "Transaction not found")
    if record.get("payment_status") != "paid" and STRIPE_API_KEY:
        logging.info("Stripe status poll skipped — payments package not installed")
    return {
        "session_id": record["session_id"],
        "status": record.get("status"),
        "payment_status": record.get("payment_status"),
        "purpose": record.get("purpose"),
        "listing_id": record.get("listing_id"),
        "amount": record.get("amount"),
    }


@app.post("/api/webhook/stripe")
async def stripe_webhook(request: Request):
    _payments_disabled()


# ---------------------------------------------------------------------
# Mount
# ---------------------------------------------------------------------
app.include_router(api)

_cors_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_credentials="*" not in _cors_origins,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


@app.on_event("startup")
async def ensure_share_indexes():
    """listings, share_intents, share_events, share_hits — the share-to-rank store."""
    try:
        await db.command("ping")
        await db.listings.create_index([("created_at_iso", 1), ("current_bid", -1)])
        await db.listings.create_index([("title", 1)])
        await db.share_intents.create_index("token", unique=True)
        await db.share_intents.create_index([("ip", 1), ("created_at", -1)])
        await db.share_intents.create_index([("listing_id", 1), ("status", 1)])
        await db.share_events.create_index([("listing_id", 1), ("target", 1), ("ip", 1)])
        await db.share_events.create_index("post_url_norm", unique=True, sparse=True)
        await db.share_events.create_index("token", sparse=True)
        await db.share_hits.create_index([("token", 1), ("created_at", -1)])
    except Exception as e:
        logging.error("MongoDB startup failed (API is up; board routes need a valid Atlas user): %s", e)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
