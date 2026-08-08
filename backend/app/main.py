from fastapi import FastAPI

from . import routes_auth

app = FastAPI(title="PokerTimer")
app.include_router(routes_auth.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
