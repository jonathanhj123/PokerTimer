def login(client):
    client.post("/api/login", json={"password": "test-password"})


def test_all_endpoints_require_admin(client):
    assert client.get("/api/regulars").status_code == 401
    assert client.post("/api/regulars", json={"name": "Anna"}).status_code == 401
    assert client.delete("/api/regulars/1").status_code == 401


def test_create_list_delete_roundtrip(client):
    login(client)
    created = client.post("/api/regulars", json={"name": "Anna B."})
    assert created.status_code == 201
    regular_id = created.json()["id"]
    assert [r["name"] for r in client.get("/api/regulars").json()] == ["Anna B."]
    assert client.delete(f"/api/regulars/{regular_id}").json() == {"ok": True}
    assert client.get("/api/regulars").json() == []
    assert client.delete(f"/api/regulars/{regular_id}").status_code == 404


def test_duplicate_or_bad_name(client):
    login(client)
    assert client.post("/api/regulars", json={"name": "Anna B."}).status_code == 201
    assert client.post("/api/regulars", json={"name": "anna b."}).status_code == 409
    assert client.post("/api/regulars", json={"name": "   "}).status_code in (409, 422)


def test_reset_keeps_regulars(client):
    login(client)
    client.post("/api/regulars", json={"name": "Anna B."})
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()
        ws.send_json({"type": "command", "action": "reset", "payload": {}})
        ws.receive_json()
    assert [r["name"] for r in client.get("/api/regulars").json()] == ["Anna B."]
