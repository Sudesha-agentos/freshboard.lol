import os
import logging
import uuid
import re
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Annotated, Any, Literal

from fastapi import FastAPI, APIRouter, HTTPException, Request
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
    bid_amount: float = Field(ge=MIN_BID)
    add_boost: bool = False
    origin_url: str


class OutbidPayload(BaseModel):
    listing_id: str
    bid_amount: float = Field(ge=MIN_BID)
    add_boost: bool = False
    origin_url: str


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


# ---------------------------------------------------------------------
# Stripe payments
# ---------------------------------------------------------------------
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
    validate_url(payload.url)
    validate_url(payload.image_url)
    if payload.listing_type == "product":
        if not payload.category or payload.category not in CATEGORIES:
            raise HTTPException(400, "Valid category required for products")
    else:
        if payload.platform not in ("x", "instagram"):
            raise HTTPException(400, "Platform must be 'x' or 'instagram' for social")

    if payload.bid_amount < MIN_BID:
        raise HTTPException(400, f"Minimum bid is ${MIN_BID}")

    total_amount = payload.bid_amount + (BOOST_PRICE if payload.add_boost else 0)

    metadata = {
        "kind": "new_listing",
        "listing_type": payload.listing_type,
        "title": payload.title,
        "tagline": payload.tagline,
        "description": payload.description or "",
        "url": payload.url,
        "image_url": payload.image_url,
        "category": payload.category or "",
        "platform": payload.platform or "",
        "bid_amount": str(payload.bid_amount),
        "add_boost": "1" if payload.add_boost else "0",
    }
    return await _create_checkout(
        request, total_amount, "new_listing", payload.origin_url, metadata
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
            "created_at_iso": now,
            "last_bid_at_iso": now,
        }
        result = await db.listings.insert_one(listing_doc)
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
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {
                "status": "completed",
                "payment_status": "paid",
                "updated_at": now,
            }},
        )


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
