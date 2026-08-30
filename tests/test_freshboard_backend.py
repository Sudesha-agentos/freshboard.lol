"""Backend smoke tests for FreshBoard.lol"""
import os
import sys
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

results = {"passed": [], "failed": []}

def rec_pass(name):
    print(f"PASS: {name}")
    results["passed"].append(name)

def rec_fail(name, evidence):
    print(f"FAIL: {name} :: {evidence}")
    results["failed"].append({"name": name, "evidence": evidence})


def test_config():
    r = requests.get(f"{BASE}/config", timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    assert len(j["categories"]) == 12, j["categories"]
    assert j["min_bid"] == 1.0
    assert j["boost_price"] == 10.0
    assert j["boost_reach"] == 5
    rec_pass("GET /api/config")


def test_reset_info():
    r = requests.get(f"{BASE}/reset-info", timeout=15)
    assert r.status_code == 200
    j = r.json()
    assert j["timezone"] == "IST (UTC+5:30)"
    assert j["seconds_until_reset"] > 0
    assert "next_reset_utc" in j
    rec_pass("GET /api/reset-info")


def test_board_initial_shape():
    r = requests.get(f"{BASE}/board", timeout=15)
    assert r.status_code == 200
    j = r.json()
    assert "products" in j and "socials" in j
    assert isinstance(j["products"], list) and isinstance(j["socials"], list)
    assert "reset" in j and "next_reset_utc" in j["reset"]
    rec_pass("GET /api/board shape")


def test_submit_product_valid():
    payload = {
        "listing_type": "product",
        "title": "TestProd",
        "tagline": "A test tagline",
        "description": "desc",
        "url": "https://example.com",
        "image_url": "https://example.com/i.png",
        "category": "SaaS",
        "bid_amount": 1.5,
        "add_boost": False,
        "origin_url": "https://example.com",
    }
    r = requests.post(f"{BASE}/submit", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    assert "checkout_url" in j and "session_id" in j
    rec_pass("POST /api/submit product valid")
    return j["session_id"]


def test_submit_social_valid():
    payload = {
        "listing_type": "social",
        "title": "TestSocial",
        "tagline": "Test tagline",
        "url": "https://x.com/user/status/1",
        "image_url": "https://example.com/i.png",
        "platform": "x",
        "bid_amount": 2.0,
        "add_boost": False,
        "origin_url": "https://example.com",
    }
    r = requests.post(f"{BASE}/submit", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    assert "checkout_url" in r.json()
    rec_pass("POST /api/submit social valid")


def test_submit_invalid_category():
    payload = {
        "listing_type": "product", "title": "x", "tagline": "y",
        "url": "https://a.com", "image_url": "https://a.com/i.png",
        "category": "NotACategory", "bid_amount": 1.5, "origin_url": "https://a.com",
    }
    r = requests.post(f"{BASE}/submit", json=payload, timeout=15)
    assert r.status_code in (400, 422), r.status_code
    rec_pass("POST /api/submit rejects invalid category")


def test_submit_invalid_platform():
    payload = {
        "listing_type": "social", "title": "x", "tagline": "y",
        "url": "https://a.com", "image_url": "https://a.com/i.png",
        "bid_amount": 1.5, "origin_url": "https://a.com",
    }
    r = requests.post(f"{BASE}/submit", json=payload, timeout=15)
    assert r.status_code in (400, 422), r.status_code
    rec_pass("POST /api/submit rejects missing platform")


def test_submit_low_bid():
    payload = {
        "listing_type": "product", "title": "x", "tagline": "y",
        "url": "https://a.com", "image_url": "https://a.com/i.png",
        "category": "SaaS", "bid_amount": 0.5, "origin_url": "https://a.com",
    }
    r = requests.post(f"{BASE}/submit", json=payload, timeout=15)
    assert r.status_code in (400, 422), r.status_code
    rec_pass("POST /api/submit rejects bid < 1.0")


def test_submit_bad_url():
    payload = {
        "listing_type": "product", "title": "x", "tagline": "y",
        "url": "notaurl", "image_url": "https://a.com/i.png",
        "category": "SaaS", "bid_amount": 1.5, "origin_url": "https://a.com",
    }
    r = requests.post(f"{BASE}/submit", json=payload, timeout=15)
    assert r.status_code in (400, 422), r.status_code
    rec_pass("POST /api/submit rejects malformed URL")


def test_submit_with_boost():
    payload = {
        "listing_type": "product", "title": "BoostP", "tagline": "y",
        "url": "https://a.com", "image_url": "https://a.com/i.png",
        "category": "AI", "bid_amount": 3.0, "add_boost": True,
        "origin_url": "https://a.com",
    }
    r = requests.post(f"{BASE}/submit", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    sid = r.json()["session_id"]
    # Verify amount = bid + 10 in DB
    async def check():
        cli = AsyncIOMotorClient(MONGO_URL)
        db = cli[DB_NAME]
        txn = await db.payment_transactions.find_one({"session_id": sid})
        cli.close()
        return txn
    txn = asyncio.get_event_loop().run_until_complete(check())
    assert txn is not None, "txn not found"
    assert abs(txn["amount"] - 13.0) < 0.01, f"expected 13.0 got {txn['amount']}"
    assert txn["metadata"].get("add_boost") == "1"
    rec_pass("POST /api/submit add_boost=true amount=bid+10")
    return sid


def test_payment_status(session_id):
    r = requests.get(f"{BASE}/payments/status/{session_id}", timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["session_id"] == session_id
    assert j["payment_status"] in ("pending", "paid", "initiated")
    rec_pass("GET /api/payments/status/{sid} shape")


async def insert_test_listings():
    cli = AsyncIOMotorClient(MONGO_URL)
    db = cli[DB_NAME]
    now = datetime.now(timezone.utc).isoformat()
    docs = [
        {"listing_type": "product", "title": "P-High", "tagline": "t", "url": "https://a.com",
         "image_url": "https://a.com/i.png", "category": "SaaS", "current_bid": 50.0,
         "boosted": False, "boost_count": 0, "created_at_iso": now, "last_bid_at_iso": now,
         "_test_marker": "freshboard_test"},
        {"listing_type": "product", "title": "P-Low", "tagline": "t", "url": "https://a.com",
         "image_url": "https://a.com/i.png", "category": "AI", "current_bid": 5.0,
         "boosted": False, "boost_count": 0, "created_at_iso": now, "last_bid_at_iso": now,
         "_test_marker": "freshboard_test"},
        {"listing_type": "social", "title": "S-Top", "tagline": "t", "url": "https://x.com/1",
         "image_url": "https://a.com/i.png", "platform": "x", "current_bid": 10.0,
         "boosted": False, "boost_count": 0, "created_at_iso": now, "last_bid_at_iso": now,
         "_test_marker": "freshboard_test"},
        # Yesterday's listing - should NOT show in board
        {"listing_type": "product", "title": "P-Old", "tagline": "t", "url": "https://a.com",
         "image_url": "https://a.com/i.png", "category": "SaaS", "current_bid": 999.0,
         "boosted": False, "boost_count": 0,
         "created_at_iso": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
         "last_bid_at_iso": now, "_test_marker": "freshboard_test"},
    ]
    ids = []
    for d in docs:
        res = await db.listings.insert_one(d)
        ids.append(res.inserted_id)
    cli.close()
    return ids


async def cleanup(ids):
    cli = AsyncIOMotorClient(MONGO_URL)
    db = cli[DB_NAME]
    await db.listings.delete_many({"_test_marker": "freshboard_test"})
    # Also cleanup pending test txns
    await db.payment_transactions.delete_many({
        "metadata.title": {"$in": ["TestProd", "TestSocial", "BoostP"]}
    })
    cli.close()


def test_board_ranking_and_filter(ids):
    r = requests.get(f"{BASE}/board", timeout=15)
    j = r.json()
    titles_p = [p["title"] for p in j["products"]]
    # P-High before P-Low
    assert "P-High" in titles_p and "P-Low" in titles_p
    assert titles_p.index("P-High") < titles_p.index("P-Low")
    # P-Old (yesterday) NOT present
    assert "P-Old" not in titles_p, "Daily reset filter failed - old listing showing"
    # Ranks assigned
    for p in j["products"]:
        assert "rank" in p
    for s in j["socials"]:
        assert "rank" in s
    rec_pass("Board ranking + daily-reset filter")

    # Category filter
    r2 = requests.get(f"{BASE}/board?category=SaaS", timeout=15)
    j2 = r2.json()
    for p in j2["products"]:
        assert p["category"] == "SaaS", p
    assert any(p["title"] == "P-High" for p in j2["products"])
    assert not any(p["title"] == "P-Low" for p in j2["products"])
    rec_pass("Board category filter")


def test_outbid(ids):
    lid = str(ids[0])  # P-High @ 50
    # Reject <= current
    r = requests.post(f"{BASE}/outbid", json={
        "listing_id": lid, "bid_amount": 50.0, "origin_url": "https://a.com"
    }, timeout=15)
    assert r.status_code == 400, r.text
    rec_pass("POST /api/outbid rejects bid <= current")

    # Invalid id
    r = requests.post(f"{BASE}/outbid", json={
        "listing_id": "notanid", "bid_amount": 100.0, "origin_url": "https://a.com"
    }, timeout=15)
    assert r.status_code in (400, 404), r.status_code
    rec_pass("POST /api/outbid rejects invalid id")

    # Nonexistent id (valid ObjectId form)
    r = requests.post(f"{BASE}/outbid", json={
        "listing_id": str(ObjectId()), "bid_amount": 100.0, "origin_url": "https://a.com"
    }, timeout=15)
    assert r.status_code in (400, 404), r.status_code
    rec_pass("POST /api/outbid rejects nonexistent id")

    # Valid outbid
    r = requests.post(f"{BASE}/outbid", json={
        "listing_id": lid, "bid_amount": 100.0, "origin_url": "https://a.com"
    }, timeout=30)
    assert r.status_code == 200, r.text
    assert "checkout_url" in r.json()
    rec_pass("POST /api/outbid valid returns checkout_url")


def test_webhook_invalid_sig():
    r = requests.post(f"{BASE}/webhook/stripe", data=b"{}",
                      headers={"Stripe-Signature": "bad"}, timeout=15)
    assert r.status_code == 400, r.status_code
    rec_pass("POST /api/webhook/stripe rejects invalid signature")


def run_all():
    ids = []
    try:
        for fn in [test_config, test_reset_info, test_board_initial_shape,
                   test_submit_invalid_category, test_submit_invalid_platform,
                   test_submit_low_bid, test_submit_bad_url]:
            try: fn()
            except Exception as e: rec_fail(fn.__name__, str(e))

        try:
            sid1 = test_submit_product_valid()
            test_payment_status(sid1)
        except Exception as e: rec_fail("submit_product+status", str(e))

        try: test_submit_social_valid()
        except Exception as e: rec_fail("submit_social", str(e))

        try: test_submit_with_boost()
        except Exception as e: rec_fail("submit_with_boost", str(e))

        ids = asyncio.get_event_loop().run_until_complete(insert_test_listings())

        try: test_board_ranking_and_filter(ids)
        except Exception as e: rec_fail("board_ranking_filter", str(e))

        try: test_outbid(ids)
        except Exception as e: rec_fail("outbid", str(e))

        try: test_webhook_invalid_sig()
        except Exception as e: rec_fail("webhook", str(e))
    finally:
        asyncio.get_event_loop().run_until_complete(cleanup(ids))

    print(f"\n=== PASSED: {len(results['passed'])} | FAILED: {len(results['failed'])} ===")
    for f in results["failed"]:
        print(f" - {f}")
    return len(results["failed"]) == 0


if __name__ == "__main__":
    ok = run_all()
    sys.exit(0 if ok else 1)
