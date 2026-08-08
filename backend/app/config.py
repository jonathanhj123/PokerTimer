import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'pokertimer.db'}")
SECRET_KEY = os.environ.get("SECRET_KEY", "")
ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH", "")
SESSION_MAX_AGE_SECONDS = 60 * 60 * 24  # one poker night, generously
