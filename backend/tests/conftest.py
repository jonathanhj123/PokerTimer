import os
import tempfile

_tmp_dir = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_dir}/test.db"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["DISABLE_TICKER"] = "1"
