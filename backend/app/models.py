from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class Template(Base):
    __tablename__ = "templates"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    structure_json: Mapped[str] = mapped_column(Text)


class Snapshot(Base):
    __tablename__ = "snapshot"
    id: Mapped[int] = mapped_column(primary_key=True)  # always row 1
    state_json: Mapped[str] = mapped_column(Text)
