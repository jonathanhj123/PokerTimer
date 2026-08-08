from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from . import config


class Base(DeclarativeBase):
    pass


_connect_args = (
    {"check_same_thread": False} if config.DATABASE_URL.startswith("sqlite") else {})
engine = create_engine(config.DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    from . import models  # noqa: F401  (register tables with Base.metadata)
    Base.metadata.create_all(engine)
