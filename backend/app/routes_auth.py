from fastapi import APIRouter, Cookie, HTTPException, Response
from pydantic import BaseModel

from . import auth, config

router = APIRouter(prefix="/api")


class LoginRequest(BaseModel):
    password: str


@router.post("/login")
def login(payload: LoginRequest, response: Response):
    if not config.ADMIN_PASSWORD_HASH or not auth.verify_password(
            payload.password, config.ADMIN_PASSWORD_HASH):
        raise HTTPException(status_code=401, detail="Invalid password")
    response.set_cookie(
        "session", auth.create_session_token(),
        httponly=True, samesite="lax", path="/",
        max_age=config.SESSION_MAX_AGE_SECONDS,
        # No secure=True: Phase 1 is plain http on the LAN; the Phase 2
        # Cloudflare Tunnel terminates TLS before traffic reaches this app.
    )
    return {"ok": True}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("session", path="/")
    return {"ok": True}


@router.get("/me")
def me(session: str | None = Cookie(default=None)):
    return {"is_admin": auth.verify_session_token(session)}
