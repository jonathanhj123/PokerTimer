"""Password hashing and signed session tokens. Framework-free on purpose —
FastAPI dependencies that use these live next to the routes."""
import hashlib
import hmac
import secrets
import time

from . import config


def hash_password(password: str, *, iterations: int = 600_000) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), iterations).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt, digest = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        check = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt), int(iterations)).hex()
    except (ValueError, TypeError, AttributeError):
        return False
    return hmac.compare_digest(check, digest)


def create_session_token() -> str:
    timestamp = str(int(time.time()))
    signature = hmac.new(config.SECRET_KEY.encode(), timestamp.encode(),
                         hashlib.sha256).hexdigest()
    return f"{timestamp}.{signature}"


def verify_session_token(token: str | None) -> bool:
    if not config.SECRET_KEY:
        return False
    if not token or "." not in token:
        return False
    timestamp, signature = token.split(".", 1)
    expected = hmac.new(config.SECRET_KEY.encode(), timestamp.encode(),
                        hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature.encode(), expected.encode()):
        return False
    try:
        age = time.time() - int(timestamp)
    except ValueError:
        return False
    return 0 <= age <= config.SESSION_MAX_AGE_SECONDS
