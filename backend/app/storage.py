"""Persistence helpers. None of these commit — the caller owns the transaction."""
import json

from .models import Snapshot, Template


def save_snapshot(session, state_dict: dict) -> None:
    snapshot = session.get(Snapshot, 1)
    if snapshot is None:
        session.add(Snapshot(id=1, state_json=json.dumps(state_dict)))
    else:
        snapshot.state_json = json.dumps(state_dict)


def load_snapshot(session) -> dict | None:
    snapshot = session.get(Snapshot, 1)
    return json.loads(snapshot.state_json) if snapshot else None


def _template_dict(template: Template) -> dict:
    return {"id": template.id, "name": template.name,
            "structure": json.loads(template.structure_json)}


def list_templates(session) -> list[dict]:
    templates = session.query(Template).order_by(Template.name).all()
    return [_template_dict(t) for t in templates]


def get_template(session, template_id: int) -> dict | None:
    template = session.get(Template, template_id)
    return _template_dict(template) if template else None


def create_template(session, name: str, structure: list[dict]) -> dict:
    if session.query(Template).filter(Template.name == name).first() is not None:
        raise ValueError(f'A template named "{name}" already exists')
    template = Template(name=name, structure_json=json.dumps(structure))
    session.add(template)
    session.flush()  # assigns template.id
    return _template_dict(template)


def delete_template(session, template_id: int) -> bool:
    template = session.get(Template, template_id)
    if template is None:
        return False
    session.delete(template)
    return True
