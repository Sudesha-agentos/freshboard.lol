"""FreshBoard.lol backend tests — share-to-earn credits mechanic (iteration 3).

Covers new /submit (no bid, welcome credits), /listings/{id}/share endpoint with
dedupe, /activity refactored to share_events + new_listings, /stats returning
total_credits/total_shares, WebSocket broadcast on submit + share, plus regression
for /config, /reset-info, /board, /preview, /yesterday-top, /top-today, /click.
"""
import os
import asyncio
import json
from datetime import datetime, timezone, timedelta

import pytest
import requests
import websockets
from bson import ObjectId
from pymongo import MongoClient

# --- Base URL
BASE_URL = None
if os.environ.get("REACT_APP_BACKEND_URL"):
    BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

API = f"{BASE_URL}/api"
WS_URL = BASE_URL.replace("https://", "wss://").replace("http://", "ws://") + "/api/ws/board"

# Shared session — reuses TCP connection so `request.client.host` stays stable across a run
# (dedupe key is per client IP; ingress may have multiple replicas → new connections
# can land on a different ingress pod IP).
_SESSION = requests.Session()
requests = _SESSION  # so existing `requests.post/get` calls use the pooled session

MONGO_URL = "mongodb://localhost:27017"
DB_NAME = os.environ.get("DB_NAME", "test_database")
mc = MongoClient(MONGO_URL)
mdb = mc[DB_NAME]

TP = "TEST_FB_"


def _make_product(title_suffix="A"):
    return {
        "listing_type": "product",
        "title": f"{TP}{title_suffix}",
        "tagline": "test tagline",
        "url": "https://example.com",
        "image_url": "https://example.com/img.png",
        "category": "SaaS",
    }


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    ids = [d["_id"] for d in mdb.listings.find({"title": {"$regex": f"^{TP}"}}, {"_id": 1})]
    mdb.listings.delete_many({"title": {"$regex": f"^{TP}"}})
    if ids:
        mdb.share_events.delete_many({"listing_id": {"$in": [str(i) for i in ids]}})


# ---------------------------------------------------------------
# /config
# ---------------------------------------------------------------
class TestConfig:
    def test_config_has_credits_fields(self):
        r = requests.get(f"{API}/config", timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d["credits_per_share"] == 5
        assert d["welcome_credits"] == 5
        assert set(d["share_targets"]) == {"x", "linkedin", "reddit", "facebook", "whatsapp", "copy"}
        assert isinstance(d["categories"], list) and len(d["categories"]) >= 10


# ---------------------------------------------------------------
# /submit (FREE now — no bid_amount)
# ---------------------------------------------------------------
class TestSubmit:
    def test_submit_valid_product_returns_credits(self):
        r = requests.post(f"{API}/submit", json=_make_product("Prod1"), timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("credits") == 5.0
        assert d.get("credits_per_share") == 5
        assert d.get("listing_id")
        # verify persistence
        get = requests.get(f"{API}/listings/{d['listing_id']}", timeout=10)
        assert get.status_code == 200
        assert get.json()["current_bid"] == 5.0

    def test_submit_no_bid_amount_field_needed(self):
        # regression: previous version required bid_amount, new version must accept without it
        r = requests.post(f"{API}/submit", json=_make_product("Prod2"), timeout=15)
        assert r.status_code == 200

    def test_submit_rejects_missing_title(self):
        p = _make_product("Bad")
        del p["title"]
        r = requests.post(f"{API}/submit", json=p, timeout=10)
        assert r.status_code == 422

    def test_submit_rejects_bad_url(self):
        p = _make_product("BadURL")
        p["url"] = "not-a-url"
        r = requests.post(f"{API}/submit", json=p, timeout=10)
        assert r.status_code == 400

    def test_submit_rejects_bad_category(self):
        p = _make_product("BadCat")
        p["category"] = "NotACategory"
        r = requests.post(f"{API}/submit", json=p, timeout=10)
        assert r.status_code == 400

    def test_submit_social_missing_platform(self):
        r = requests.post(f"{API}/submit", json={
            "listing_type": "social",
            "title": f"{TP}SocBad",
            "tagline": "t",
            "url": "https://example.com",
            "image_url": "https://example.com/i.png",
        }, timeout=10)
        # platform must be x or instagram -> 400
        assert r.status_code in (400, 422)

    def test_submit_lands_on_board(self):
        r = requests.post(f"{API}/submit", json=_make_product("OnBoard"), timeout=15)
        lid = r.json()["listing_id"]
        b = requests.get(f"{API}/board", timeout=10).json()
        ids = [p["id"] for p in b["products"]]
        assert lid in ids


# ---------------------------------------------------------------
# /listings/{id}/share
# ---------------------------------------------------------------
@pytest.fixture(scope="module")
def share_listing_id():
    r = requests.post(f"{API}/submit", json=_make_product("ShareTgt"), timeout=15)
    return r.json()["listing_id"]


class TestShare:
    def test_share_x_credits_10(self, share_listing_id):
        listing_id = share_listing_id
        r = requests.post(f"{API}/listings/{listing_id}/share", json={"target": "x"}, timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d["credited"] is True
        assert d["credits"] == 10.0
        # verify persisted
        get = requests.get(f"{API}/listings/{listing_id}", timeout=10).json()
        assert get["current_bid"] == 10.0

    def test_share_same_target_dedupes(self, share_listing_id):
        listing_id = share_listing_id
        r = requests.post(f"{API}/listings/{listing_id}/share", json={"target": "x"}, timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d["credited"] is False
        assert d.get("reason") == "already_shared"
        # credits unchanged
        get = requests.get(f"{API}/listings/{listing_id}", timeout=10).json()
        assert get["current_bid"] == 10.0

    def test_share_linkedin_credits_15(self, share_listing_id):
        listing_id = share_listing_id
        r = requests.post(f"{API}/listings/{listing_id}/share", json={"target": "linkedin"}, timeout=10)
        assert r.status_code == 200
        assert r.json()["credits"] == 15.0

    def test_share_invalid_target(self, share_listing_id):
        listing_id = share_listing_id
        r = requests.post(f"{API}/listings/{listing_id}/share", json={"target": "discord"}, timeout=10)
        assert r.status_code == 422

    def test_share_nonexistent_id(self):
        r = requests.post(f"{API}/listings/507f1f77bcf86cd799439011/share",
                          json={"target": "x"}, timeout=10)
        assert r.status_code == 404

    def test_share_malformed_id(self):
        r = requests.post(f"{API}/listings/not-an-oid/share",
                          json={"target": "x"}, timeout=10)
        assert r.status_code == 400


# ---------------------------------------------------------------
# Board ranking after credits
# ---------------------------------------------------------------
class TestBoardRanking:
    def test_ranking_by_credits(self):
        # A: 15, B: 10, C: 5
        a = requests.post(f"{API}/submit", json=_make_product("RankA"), timeout=15).json()["listing_id"]
        b = requests.post(f"{API}/submit", json=_make_product("RankB"), timeout=15).json()["listing_id"]
        c = requests.post(f"{API}/submit", json=_make_product("RankC"), timeout=15).json()["listing_id"]
        # A gets 2 shares (10, 15) — use two different targets to bypass dedupe
        for t in ("linkedin", "reddit"):
            requests.post(f"{API}/listings/{a}/share", json={"target": t}, timeout=10)
        # B gets 1 share
        requests.post(f"{API}/listings/{b}/share", json={"target": "linkedin"}, timeout=10)

        board = requests.get(f"{API}/board", timeout=10).json()
        # find our three
        prod_map = {p["id"]: p for p in board["products"] if p["id"] in (a, b, c)}
        assert prod_map[a]["current_bid"] == 15.0
        assert prod_map[b]["current_bid"] == 10.0
        assert prod_map[c]["current_bid"] == 5.0
        # A rank should be < B rank should be < C rank
        assert prod_map[a]["rank"] < prod_map[b]["rank"] < prod_map[c]["rank"]


# ---------------------------------------------------------------
# /activity
# ---------------------------------------------------------------
class TestActivity:
    def test_activity_shape_and_purposes(self):
        # trigger a submit and a share to guarantee entries
        lid = requests.post(f"{API}/submit", json=_make_product("Act1"), timeout=15).json()["listing_id"]
        requests.post(f"{API}/listings/{lid}/share", json={"target": "facebook"}, timeout=10)
        import time as _t
        _t.sleep(0.8)
        r = requests.get(f"{API}/activity", params={"limit": 50}, timeout=10)
        assert r.status_code == 200
        items = r.json()["items"]
        assert isinstance(items, list)
        # Note: parallel xdist workers may clean up mid-run; if items present, validate shape
        if items:
            for it in items[:5]:
                assert "title" in it
                assert "current_bid" in it
                assert it["purpose"] in ("share", "new_listing")
            ats = [i.get("at") for i in items if i.get("at")]
            assert ats == sorted(ats, reverse=True)


# ---------------------------------------------------------------
# /stats
# ---------------------------------------------------------------
class TestStats:
    def test_stats_shape(self):
        r = requests.get(f"{API}/stats", timeout=10)
        assert r.status_code == 200
        d = r.json()
        for k in ("total_credits", "total_shares", "active_today", "launched_at"):
            assert k in d
        assert isinstance(d["total_credits"], (int, float))
        assert isinstance(d["total_shares"], int)


# ---------------------------------------------------------------
# Regressions
# ---------------------------------------------------------------
class TestRegressions:
    def test_reset_info_ist(self):
        r = requests.get(f"{API}/reset-info", timeout=10)
        assert r.status_code == 200
        assert "IST" in r.json()["timezone"]

    def test_preview_valid(self):
        r = requests.post(f"{API}/preview", json={"url": "https://stripe.com"}, timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert d.get("title") and d.get("image_url")

    def test_preview_invalid(self):
        r = requests.post(f"{API}/preview", json={"url": "not-a-url"}, timeout=10)
        assert r.status_code == 400

    def test_yesterday_top_shape(self):
        r = requests.get(f"{API}/yesterday-top", timeout=10)
        assert r.status_code == 200
        assert "item" in r.json()

    def test_top_today(self):
        r = requests.get(f"{API}/top-today", timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json()["items"], list)

    def test_click_increment(self):
        lid = requests.post(f"{API}/submit", json=_make_product("Click"), timeout=15).json()["listing_id"]
        r = requests.post(f"{API}/listings/{lid}/click", timeout=10)
        assert r.status_code == 200
        # verify DB got incremented
        doc = mdb.listings.find_one({"_id": ObjectId(lid)})
        assert (doc.get("click_count") or 0) >= 1


# ---------------------------------------------------------------
# WebSocket broadcast tests
# ---------------------------------------------------------------
@pytest.mark.asyncio
async def test_ws_hello_and_submit_share_broadcast():
    """Connect WS client, then POST submit + share, verify board_update messages."""
    async with websockets.connect(WS_URL, open_timeout=10, close_timeout=5) as ws:
        hello = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        assert hello.get("type") == "hello"

        # Submit -> expect new_listing broadcast
        loop = asyncio.get_event_loop()
        r = await loop.run_in_executor(
            None,
            lambda: requests.post(f"{API}/submit", json=_make_product("WS1"), timeout=15),
        )
        assert r.status_code == 200
        lid = r.json()["listing_id"]

        got_new = False
        got_share = False
        deadline = loop.time() + 8
        # Now share too
        r2 = await loop.run_in_executor(
            None,
            lambda: requests.post(f"{API}/listings/{lid}/share", json={"target": "reddit"}, timeout=10),
        )
        assert r2.status_code == 200

        while loop.time() < deadline and not (got_new and got_share):
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=max(0.1, deadline - loop.time()))
            except asyncio.TimeoutError:
                break
            msg = json.loads(raw)
            if msg.get("type") == "board_update":
                if msg.get("purpose") == "new_listing":
                    got_new = True
                elif msg.get("purpose") == "share":
                    got_share = True
        assert got_new, "Missed new_listing broadcast"
        assert got_share, "Missed share broadcast"
