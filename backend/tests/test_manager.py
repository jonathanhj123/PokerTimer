import asyncio
import contextlib

from app import storage
from app.db import SessionLocal
from app.engine import TournamentState
from app.manager import TournamentManager
from tests.helpers import level


class FakeWebSocket:
    def __init__(self):
        self.sent = []

    async def send_json(self, data):
        self.sent.append(data)


def make_manager():
    manager = TournamentManager()
    manager.state = TournamentState(structure=[level(25, 50, minutes=1),
                                               level(50, 100)])
    return manager


def test_command_persists_and_broadcasts(clean_db):
    manager = make_manager()
    admin, viewer = FakeWebSocket(), FakeWebSocket()
    manager.clients = [admin, viewer]

    asyncio.run(manager.handle_command(admin, "start", {}))

    assert manager.state.status == "running"
    for ws in (admin, viewer):
        assert ws.sent[-1]["type"] == "state"
        assert ws.sent[-1]["state"]["status"] == "running"
    with SessionLocal() as session:
        assert storage.load_snapshot(session)["status"] == "running"


def test_invalid_command_errors_sender_only(clean_db):
    manager = make_manager()
    admin, viewer = FakeWebSocket(), FakeWebSocket()
    manager.clients = [admin, viewer]

    asyncio.run(manager.handle_command(admin, "pause", {}))  # not running yet

    assert admin.sent[-1]["type"] == "error"
    assert viewer.sent == []
    assert manager.state.status == "setup"


def test_unknown_command_is_an_error(clean_db):
    manager = make_manager()
    admin = FakeWebSocket()
    asyncio.run(manager.handle_command(admin, "explode", {}))
    assert admin.sent[-1]["type"] == "error"


def test_tick_once_broadcasts_state(clean_db):
    manager = make_manager()
    viewer = FakeWebSocket()
    manager.clients = [viewer]
    asyncio.run(manager.handle_command(FakeWebSocket(), "start", {}))

    asyncio.run(manager.tick_once())

    assert viewer.sent[-1]["type"] == "state"
    assert viewer.sent[-1]["state"]["seconds_remaining"] == 59


def test_tick_once_emits_level_change_on_advance(clean_db):
    manager = make_manager()
    viewer = FakeWebSocket()
    manager.clients = [viewer]
    asyncio.run(manager.handle_command(FakeWebSocket(), "start", {}))
    manager.state.seconds_remaining = 1

    asyncio.run(manager.tick_once())

    assert viewer.sent[-1]["type"] == "level_change"
    assert viewer.sent[-1]["state"]["current_index"] == 1


def test_manual_jump_broadcasts_plain_state_not_level_change(clean_db):
    manager = make_manager()
    viewer = FakeWebSocket()
    manager.clients = [viewer]
    asyncio.run(manager.handle_command(FakeWebSocket(), "start", {}))

    asyncio.run(manager.handle_command(FakeWebSocket(), "next_level", {}))

    assert viewer.sent[-1]["type"] == "state"


def test_dead_clients_are_pruned(clean_db):
    class DeadWebSocket:
        async def send_json(self, data):
            raise RuntimeError("gone")

    manager = make_manager()
    dead, alive = DeadWebSocket(), FakeWebSocket()
    manager.clients = [dead, alive]
    asyncio.run(manager.broadcast())
    assert manager.clients == [alive]
    assert alive.sent[-1]["type"] == "state"


def test_restart_resumes_paused(clean_db):
    manager = make_manager()
    asyncio.run(manager.handle_command(FakeWebSocket(), "start", {}))

    restarted = TournamentManager()
    restarted.load_from_db()

    assert restarted.state.status == "paused"
    assert restarted.state.structure == manager.state.structure
    # and the paused status was persisted back
    with SessionLocal() as session:
        assert storage.load_snapshot(session)["status"] == "paused"


def test_load_from_db_without_snapshot_keeps_fresh_state(clean_db):
    manager = TournamentManager()
    manager.load_from_db()
    assert manager.state.status == "setup"


def test_set_config_parses_decimal_string(clean_db):
    from decimal import Decimal

    manager = make_manager()
    asyncio.run(manager.handle_command(
        FakeWebSocket(), "set_config", {"buy_in": "12.50", "currency": "kr"}))
    assert manager.state.buy_in == Decimal("12.50")
    assert manager.state.currency == "kr"


def test_bad_entry_payload_is_engine_error_not_crash(clean_db):
    manager = make_manager()
    admin = FakeWebSocket()
    asyncio.run(manager.handle_command(
        admin, "update_entry", {"index": 0, "entry": {"type": "level", "sb": -5}}))
    assert admin.sent[-1]["type"] == "error"


# --- Critical #1: non-finite buy_in must not poison the server -----------

def test_set_config_rejects_non_finite_buy_in(clean_db):
    manager = make_manager()
    original_buy_in = manager.state.buy_in

    for bad_value in ("Infinity", "NaN", "-Infinity"):
        admin = FakeWebSocket()

        asyncio.run(manager.handle_command(
            admin, "set_config", {"buy_in": bad_value}))

        assert admin.sent[-1]["type"] == "error"
        assert manager.state.buy_in == original_buy_in
        # The handshake path (and every future one) must still work —
        # to_dict() must not have been poisoned into raising forever.
        manager.state.to_dict()


# --- Important #3: a failed command must not leave partial mutations -----

def test_set_config_error_rolls_back_partial_mutation(clean_db):
    manager = make_manager()
    admin = FakeWebSocket()
    original_buy_in = manager.state.buy_in

    # engine.set_config assigns buy_in before validating currency, so a
    # valid buy_in paired with an invalid currency must not stick.
    asyncio.run(manager.handle_command(
        admin, "set_config", {"buy_in": "25", "currency": ""}))

    assert admin.sent[-1]["type"] == "error"
    assert manager.state.buy_in == original_buy_in


# --- Important #4: the ticker must survive an exception in tick_once -----

def test_ticker_survives_tick_once_exception(clean_db, monkeypatch):
    manager = make_manager()
    calls = []
    real_sleep = asyncio.sleep  # captured before patching, still a real checkpoint

    async def fast_sleep(_seconds):
        # Keep run_ticker's loop a real yield point (so the event loop can
        # interleave with the driving test coroutine below) without
        # actually waiting a full second per iteration.
        await real_sleep(0)

    async def flaky_tick_once():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")

    monkeypatch.setattr(asyncio, "sleep", fast_sleep)
    monkeypatch.setattr(manager, "tick_once", flaky_tick_once)

    async def run():
        task = asyncio.create_task(manager.run_ticker())
        for _ in range(50):
            if len(calls) >= 2:
                break
            await real_sleep(0)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    asyncio.run(run())

    # The exception on the first call must not have killed the loop —
    # tick_once (or its replacement) keeps getting invoked afterward.
    assert len(calls) >= 2


# --- Important #5: a wedged client must not block the broadcast lock -----

def test_slow_client_is_pruned_instead_of_blocking_broadcast(clean_db):
    class HangingWebSocket:
        async def send_json(self, data):
            await asyncio.sleep(999)

    manager = make_manager()
    manager.broadcast_timeout = 0.05
    hanging, alive = HangingWebSocket(), FakeWebSocket()
    manager.clients = [hanging, alive]

    asyncio.run(manager.broadcast())

    assert manager.clients == [alive]
    assert alive.sent[-1]["type"] == "state"
