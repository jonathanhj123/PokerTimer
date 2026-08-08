import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import storage
from app.db import Base
from tests.helpers import brk, level


@pytest.fixture
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/storage_test.db")
    import app.models  # noqa: F401  (register tables)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as db_session:
        yield db_session


def test_snapshot_roundtrip(session):
    state = {"status": "running", "seconds_remaining": 123}
    storage.save_snapshot(session, state)
    session.commit()
    assert storage.load_snapshot(session) == state


def test_snapshot_overwrites_single_row(session):
    storage.save_snapshot(session, {"v": 1})
    session.commit()
    storage.save_snapshot(session, {"v": 2})
    session.commit()
    assert storage.load_snapshot(session) == {"v": 2}


def test_load_snapshot_empty_db(session):
    assert storage.load_snapshot(session) is None


def test_template_crud(session):
    structure = [level(25, 50), brk(10)]
    created = storage.create_template(session, "Friday Night", structure)
    session.commit()
    assert created["name"] == "Friday Night"
    assert created["structure"] == structure

    templates = storage.list_templates(session)
    assert [t["name"] for t in templates] == ["Friday Night"]
    assert storage.get_template(session, created["id"])["structure"] == structure

    assert storage.delete_template(session, created["id"]) is True
    session.commit()
    assert storage.list_templates(session) == []
    assert storage.delete_template(session, 999) is False


def test_duplicate_template_name_raises(session):
    storage.create_template(session, "Friday", [level(25, 50)])
    session.commit()
    with pytest.raises(ValueError):
        storage.create_template(session, "Friday", [level(50, 100)])
