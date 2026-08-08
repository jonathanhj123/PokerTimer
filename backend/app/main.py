import asyncio
import contextlib
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import routes_auth, routes_templates, ws
from .db import init_db
from .manager import manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    manager.load_from_db()
    ticker = None
    if not os.environ.get("DISABLE_TICKER"):
        ticker = asyncio.create_task(manager.run_ticker())
    try:
        yield
    finally:
        # An exception raised anywhere during app runtime (between startup
        # and shutdown) must still reach this cleanup, or the ticker task
        # leaks (never cancelled/awaited) on the way out.
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
