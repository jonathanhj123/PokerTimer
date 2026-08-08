from fastapi import FastAPI

app = FastAPI(title="PokerTimer")


@app.get("/api/health")
def health():
    return {"status": "ok"}
