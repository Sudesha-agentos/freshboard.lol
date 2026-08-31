"""ASGI app for `gunicorn your_application.wsgi`.

Gunicorn.conf.py sets UvicornWorker so this FastAPI app runs as ASGI,
including the board websocket.
"""
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from server import app as application  # noqa: E402
