from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from . import storage
from .db import SessionLocal
from .routes_templates import require_admin

router = APIRouter(prefix="/api/regulars", dependencies=[Depends(require_admin)])


class RegularCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)  # storage enforces 30 after trimming


@router.get("")
def list_regulars():
    with SessionLocal() as session:
        return storage.list_regulars(session)


@router.post("", status_code=201)
def create_regular(payload: RegularCreate):
    with SessionLocal() as session:
        try:
            regular = storage.create_regular(session, payload.name)
            session.commit()
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
    return regular


@router.delete("/{regular_id}")
def delete_regular(regular_id: int):
    with SessionLocal() as session:
        deleted = storage.delete_regular(session, regular_id)
        session.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="Regular not found")
    return {"ok": True}
