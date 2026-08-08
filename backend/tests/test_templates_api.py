from app.engine import TournamentState
from app.manager import manager
from tests.helpers import brk, level


def login(client):
    client.post("/api/login", json={"password": "test-password"})


def test_all_endpoints_require_admin(client):
    assert client.get("/api/templates").status_code == 401
    assert client.post("/api/templates", json={}).status_code == 401
    assert client.delete("/api/templates/1").status_code == 401
    assert client.post("/api/templates/1/load").status_code == 401


def test_create_list_delete_roundtrip(client):
    login(client)
    structure = [level(25, 50), brk(10), level(50, 100)]
    created = client.post("/api/templates",
                          json={"name": "Friday Night", "structure": structure})
    assert created.status_code == 201
    template_id = created.json()["id"]

    listed = client.get("/api/templates").json()
    assert [t["name"] for t in listed] == ["Friday Night"]
    assert listed[0]["structure"] == structure

    assert client.delete(f"/api/templates/{template_id}").json() == {"ok": True}
    assert client.get("/api/templates").json() == []
    assert client.delete(f"/api/templates/{template_id}").status_code == 404


def test_duplicate_name_409(client):
    login(client)
    body = {"name": "Friday", "structure": [level(25, 50)]}
    assert client.post("/api/templates", json=body).status_code == 201
    assert client.post("/api/templates", json=body).status_code == 409


def test_invalid_structure_422(client):
    login(client)
    bad = {"name": "Bad", "structure": [{"type": "level", "sb": 0, "bb": 50,
                                         "minutes": 15}]}
    assert client.post("/api/templates", json=bad).status_code == 422
    assert client.post("/api/templates",
                       json={"name": "Empty", "structure": []}).status_code == 422


def test_load_template_in_setup(client):
    login(client)
    structure = [level(100, 200), level(200, 400)]
    template_id = client.post(
        "/api/templates", json={"name": "Turbo", "structure": structure}).json()["id"]

    response = client.post(f"/api/templates/{template_id}/load")
    assert response.status_code == 200
    assert manager.state.structure == structure


def test_load_template_missing_404(client):
    login(client)
    assert client.post("/api/templates/999/load").status_code == 404


def test_load_template_mid_game_409(client):
    login(client)
    template_id = client.post(
        "/api/templates",
        json={"name": "Turbo", "structure": [level(100, 200)]}).json()["id"]
    manager.state = TournamentState(structure=[level(25, 50)])
    manager.state.start()
    assert client.post(f"/api/templates/{template_id}/load").status_code == 409
