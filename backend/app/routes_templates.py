from fastapi import APIRouter, Cookie, Depends, HTTPException
from pydantic import BaseModel, Field

from . import auth, storage
from .db import SessionLocal
from .engine import EngineError
from .manager import manager
from .schemas import Entry


def require_admin(session: str | None = Cookie(default=None)):
    if not auth.verify_session_token(session):
        raise HTTPException(status_code=401, detail="Admin login required")


router = APIRouter(prefix="/api/templates", dependencies=[Depends(require_admin)])


class TemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    structure: list[Entry] = Field(min_length=1)


@router.get("")
def list_templates():
    with SessionLocal() as session:
        return storage.list_templates(session)


@router.post("", status_code=201)
def create_template(payload: TemplateCreate):
    structure = [entry.model_dump() for entry in payload.structure]
    with SessionLocal() as session:
        try:
            template = storage.create_template(session, payload.name, structure)
            session.commit()
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
    return template


@router.delete("/{template_id}")
def delete_template(template_id: int):
    with SessionLocal() as session:
        deleted = storage.delete_template(session, template_id)
        session.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"ok": True}


@router.post("/{template_id}/load")
async def load_template(template_id: int):
    try:
        found = await manager.load_template(template_id)
    except EngineError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not found:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"ok": True}
