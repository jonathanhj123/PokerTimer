from app.engine import TournamentState
from app.manager import manager
from tests.helpers import level


def seed_structure():
    manager.state = TournamentState(structure=[level(25, 50), level(50, 100)])


def login_cookie(client) -> dict:
    client.post("/api/login", json={"password": "test-password"})
    return {"Cookie": f"session={client.cookies.get('session')}"}


def test_connect_receives_state_and_admin_flag(client):
    seed_structure()
    with client.websocket_connect("/ws") as websocket:
        message = websocket.receive_json()
    assert message["type"] == "state"
    assert message["is_admin"] is False
    assert message["state"]["status"] == "setup"


def test_anonymous_commands_rejected(client):
    seed_structure()
    with client.websocket_connect("/ws") as websocket:
        websocket.receive_json()
        websocket.send_json({"type": "command", "action": "start", "payload": {}})
        reply = websocket.receive_json()
    assert reply["type"] == "error"
    assert manager.state.status == "setup"


def test_admin_command_flows_to_all_clients(client):
    seed_structure()
    headers = login_cookie(client)
    with client.websocket_connect("/ws") as viewer:
        viewer.receive_json()
        with client.websocket_connect("/ws", headers=headers) as admin:
            first = admin.receive_json()
            assert first["is_admin"] is True
            admin.send_json({"type": "command", "action": "start", "payload": {}})
            admin_view = admin.receive_json()
            viewer_view = viewer.receive_json()
    assert admin_view["state"]["status"] == "running"
    assert viewer_view["state"]["status"] == "running"


def test_engine_error_reaches_only_the_sender(client):
    seed_structure()
    headers = login_cookie(client)
    with client.websocket_connect("/ws", headers=headers) as admin:
        admin.receive_json()
        admin.send_json({"type": "command", "action": "pause", "payload": {}})
        reply = admin.receive_json()
    assert reply["type"] == "error"
    assert "pause" in reply["message"].lower() or "running" in reply["message"].lower()
