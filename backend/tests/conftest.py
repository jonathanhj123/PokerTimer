import os
import tempfile

_tmp_dir = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_dir}/test.db"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["DISABLE_TICKER"] = "1"

from app import auth, config  # noqa: E402

# Low iteration count keeps the test suite fast; production default is 600k.
config.ADMIN_PASSWORD_HASH = auth.hash_password("test-password", iterations=1000)
