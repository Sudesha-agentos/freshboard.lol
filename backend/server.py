import os
import logging
import uuid
import re
from urllib.parse import urlparse
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Annotated, Any, Literal

import requests
import asyncio
from fastapi import FastAPI, APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, ConfigDict, BeforeValidator, HttpUrl
from bson import ObjectId

from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout,
    CheckoutSessionRequest,
)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

# ---------------------------------------------------------------------
# Environment / DB
# ---------------------------------------------------------------------
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

STRIPE_API_KEY = os.environ["STRIPE_API_KEY"]

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
    target: Literal["x", "linkedin", "reddit", "facebook", "whatsapp", "copy"]


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


# ---------------------------------------------------------------------
# App / router
# ---------------------------------------------------------------------
app = FastAPI(title="FreshBoard.lol API")
api = APIRouter(prefix="/api")


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
        "share_targets": ["x", "linkedin", "reddit", "facebook", "whatsapp", "copy"],
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
    cursor = db.listings.find(query).sort("current_bid", -1)
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
            higher = await db.listings.count_documents({
                "listing_type": listing["listing_type"],
                "created_at_iso": {"$gte": day_start},
                "current_bid": {"$gt": listing.get("current_bid", 0)},
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
    ).sort("current_bid", -1).limit(min(max(limit, 1), 10))
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
        sort=[("current_bid", -1)],
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


def _stripe_from_request(request: Request) -> StripeCheckout:
    host_url = str(request.base_url)
    webhook_url = f"{host_url}api/webhook/stripe"
    return StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)


async def _create_checkout(
    request: Request,
    amount: float,
    purpose: str,
    origin_url: str,
    metadata: dict,
) -> dict:
    stripe_checkout = _stripe_from_request(request)
    success_url = f"{origin_url.rstrip('/')}/payment/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin_url.rstrip('/')}/payment/cancel"
    req = CheckoutSessionRequest(
        amount=float(round(amount, 2)),
        currency="usd",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={**metadata, "purpose": purpose},
    )
    session = await stripe_checkout.create_checkout_session(req)
    await db.payment_transactions.insert_one({
        "session_id": session.session_id,
        "amount": float(round(amount, 2)),
        "currency": "usd",
        "purpose": purpose,
        "status": "initiated",
        "payment_status": "pending",
        "metadata": metadata,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    })
    return {"checkout_url": session.url, "session_id": session.session_id}


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


@api.post("/listings/{listing_id}/share")
async def share_listing(listing_id: str, payload: ShareRequest, request: Request):
    """Register a share: +CREDITS_PER_SHARE credits per (listing, target, ip) — once each."""
    try:
        oid = ObjectId(listing_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    doc = await db.listings.find_one({"_id": oid})
    if not doc:
        raise HTTPException(404, "Listing not found")

    ip = request.client.host if request.client else "unknown"
    now = now_iso()
    existing = await db.share_events.find_one({
        "listing_id": listing_id,
        "target": payload.target,
        "ip": ip,
    })
    if existing:
        return {
            "credited": False,
            "credits": float(doc.get("current_bid", 0)),
            "reason": "already_shared",
        }

    await db.share_events.insert_one({
        "listing_id": listing_id,
        "target": payload.target,
        "ip": ip,
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
            "target": payload.target,
            "at": now,
        })
    except Exception:
        pass
    return {
        "credited": True,
        "credits": new_credits,
        "target": payload.target,
    }


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
    if record.get("payment_status") != "paid":
        try:
            stripe_checkout = _stripe_from_request(request)
            status = await stripe_checkout.get_checkout_status(session_id)
            if status.payment_status == "paid" or status.status == "complete":
                await _apply_paid_transaction(session_id, dict(status.metadata or {}))
                record = await db.payment_transactions.find_one({"session_id": session_id})
        except Exception as e:
            logging.exception("Stripe status poll failed: %s", e)
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
    body = await request.body()
    sig = request.headers.get("Stripe-Signature", "")
    try:
        stripe_checkout = _stripe_from_request(request)
        event = await stripe_checkout.handle_webhook(body, sig)
    except Exception as e:
        logging.exception("Webhook error: %s", e)
        raise HTTPException(400, "Invalid webhook")
    if event.payment_status == "paid":
        await _apply_paid_transaction(event.session_id, dict(event.metadata or {}))
    return {"status": "ok"}


# ---------------------------------------------------------------------
# Mount
# ---------------------------------------------------------------------
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
