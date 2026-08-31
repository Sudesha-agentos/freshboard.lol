"""Sanitize Mongo env, then load the FastAPI app for gunicorn."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import quote_plus

BACKEND = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

ATLAS_HOST = "frshboard.15rissw.mongodb.net"


def _clean(value: str | None) -> str:
    if not value:
        return ""
    v = str(value).strip().lstrip("\ufeff").strip().strip('"').strip("'").strip()
    if v.lower().startswith("mongo_url="):
        v = v.split("=", 1)[1].strip().strip('"').strip("'")
    return v


def _fix_mongo_env() -> None:
    user = _clean(os.environ.get("MONGODB_USERNAME"))
    password = _clean(os.environ.get("MONGODB_PASSWORD"))
    uri = _clean(os.environ.get("MONGO_URL") or os.environ.get("MONGODB_URI"))
    db_name = _clean(os.environ.get("DB_NAME")) or "freshboard"
    os.environ["DB_NAME"] = db_name

    if user and password:
        os.environ["MONGO_URL"] = (
            f"mongodb+srv://{quote_plus(user)}:{quote_plus(password)}"
            f"@{ATLAS_HOST}/{db_name}?retryWrites=true&w=majority&authSource=admin"
        )
        return

    if uri.startswith(("mongodb://", "mongodb+srv://")):
        os.environ["MONGO_URL"] = uri
        return

    if uri and "mongodb.net" in uri:
        host = uri.split("@")[-1].split("/")[0]
        os.environ["MONGO_URL"] = (
            f"mongodb+srv://{host}/{db_name}?retryWrites=true&w=majority&authSource=admin"
        )
        return

    os.environ["MONGO_URL"] = "mongodb://127.0.0.1:27017"


_fix_mongo_env()

from server import app as application  # noqa: E402
