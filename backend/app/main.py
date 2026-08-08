import asyncio
import contextlib
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config, routes_auth, routes_templates, ws
from .db import init_db
from .manager import manager

logger = logging.getLogger(__name__)

DIST_DIR = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not config.SECRET_KEY or not config.ADMIN_PASSWORD_HASH:
        logger.warning(
            "SECRET_KEY/ADMIN_PASSWORD_HASH not configured — admin login will not "
            "work. Run: python scripts/setup_env.py"
        )
    if not DIST_DIR.exists():
        logger.warning(
            "frontend/dist not found — the app will only serve the API, no UI. "
            "Run: npm run build (from frontend/)"
        )
    init_db()
    manager.load_from_db()
    ticker = None
    if not os.environ.get("DISABLE_TICKER"):
        ticker = asyncio.create_task(manager.run_ticker())
    try:
        yield
    finally:
        if ticker:
            ticker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await ticker


app = FastAPI(title="PokerTimer", lifespan=lifespan)
app.include_router(routes_auth.router)
app.include_router(routes_templates.router)
app.include_router(ws.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


if DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        if full_path.startswith(("api/", "ws")):
            raise HTTPException(status_code=404)
        return FileResponse(DIST_DIR / "index.html")
