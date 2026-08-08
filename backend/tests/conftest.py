import os
import tempfile

_tmp_dir = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_dir}/test.db"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["DISABLE_TICKER"] = "1"

from app import auth, config  # noqa: E402

# Low iteration count keeps the test suite fast; production default is 600k.
config.ADMIN_PASSWORD_HASH = auth.hash_password("test-password", iterations=1000)

import pytest  # noqa: E402


@pytest.fixture
def clean_db():
    from app.db import SessionLocal, init_db
    from app.models import Snapshot, Template

    init_db()
    with SessionLocal() as session:
        session.query(Snapshot).delete()
        session.query(Template).delete()
        session.commit()
    yield


@pytest.fixture
def client(clean_db):
    from fastapi.testclient import TestClient

    from app.engine import TournamentState
    from app.main import app
    from app.manager import manager

    manager.state = TournamentState()
    manager.clients = []
    with TestClient(app) as test_client:
        yield test_client
