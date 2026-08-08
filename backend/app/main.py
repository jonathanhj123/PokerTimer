import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import routes_auth, routes_templates, ws
from .db import init_db
from .manager import manager

DIST_DIR = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    manager.load_from_db()
    ticker = None
    if not os.environ.get("DISABLE_TICKER"):
        ticker = asyncio.create_task(manager.run_ticker())
    yield
    if ticker:
        ticker.cancel()


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
