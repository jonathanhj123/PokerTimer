import hashlib
import hmac
import time

from fastapi.testclient import TestClient

from app import auth, config
from app.main import app


def test_hash_and_verify_roundtrip():
    stored = auth.hash_password("hunter22", iterations=1000)
    assert stored.startswith("pbkdf2_sha256$1000$")
    assert auth.verify_password("hunter22", stored) is True
    assert auth.verify_password("wrong", stored) is False


def test_verify_malformed_hash_is_false():
    assert auth.verify_password("x", "not-a-real-hash") is False
    assert auth.verify_password("x", "") is False


def test_verify_password_none_stored_is_false():
    assert auth.verify_password("x", None) is False


def test_session_token_roundtrip():
    token = auth.create_session_token()
    assert auth.verify_session_token(token) is True


def test_tampered_token_rejected():
    token = auth.create_session_token()
    last = token[-1]
    flipped = "0" if last != "0" else "1"
    assert auth.verify_session_token(token[:-1] + flipped) is False
    assert auth.verify_session_token("garbage") is False
    assert auth.verify_session_token(None) is False


def test_expired_token_rejected(monkeypatch):
    monkeypatch.setattr(config, "SESSION_MAX_AGE_SECONDS", 10)
    old_ts = str(int(time.time()) - 60)
    sig = hmac.new(config.SECRET_KEY.encode(), old_ts.encode(),
                   hashlib.sha256).hexdigest()
    assert auth.verify_session_token(f"{old_ts}.{sig}") is False


def test_non_ascii_token_rejected_not_crashed():
    assert auth.verify_session_token("123.\xe9bad") is False
    assert auth.verify_session_token("123.bad☃signature") is False


def test_empty_secret_key_rejects_all_tokens(monkeypatch):
    token = auth.create_session_token()
    monkeypatch.setattr(config, "SECRET_KEY", "")
    assert auth.verify_session_token(token) is False


def test_login_wrong_password_401():
    client = TestClient(app)
    response = client.post("/api/login", json={"password": "nope"})
    assert response.status_code == 401
    assert "session" not in client.cookies


def test_login_sets_cookie_and_me_reports_admin():
    client = TestClient(app)
    assert client.get("/api/me").json() == {"is_admin": False}
    response = client.post("/api/login", json={"password": "test-password"})
    assert response.status_code == 200
    assert client.cookies.get("session")
    assert client.get("/api/me").json() == {"is_admin": True}


def test_logout_clears_session():
    client = TestClient(app)
    client.post("/api/login", json={"password": "test-password"})
    client.post("/api/logout")
    assert client.get("/api/me").json() == {"is_admin": False}
