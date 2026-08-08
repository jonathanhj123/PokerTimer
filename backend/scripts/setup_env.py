"""One-time setup: writes backend/.env with a fresh SECRET_KEY and the admin
password hash. Run: python scripts/setup_env.py  (password prompted; or pass
it as the first argument for non-interactive use)."""
import secrets
import sys
from getpass import getpass
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.auth import hash_password  # noqa: E402

env_path = BACKEND_DIR / ".env"
if env_path.exists():
    print(f"{env_path} already exists — delete it first to regenerate.")
    sys.exit(1)

password = sys.argv[1] if len(sys.argv) > 1 else getpass("Choose the admin password: ")
if len(password) < 8:
    print("Password must be at least 8 characters.")
    sys.exit(1)

env_path.write_text(
    f"SECRET_KEY={secrets.token_hex(32)}\n"
    f"ADMIN_PASSWORD_HASH={hash_password(password)}\n")
print(f"Wrote {env_path}")
