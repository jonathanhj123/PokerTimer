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
        def __init__(self):
            self.closed = False

        async def send_json(self, data):
            await asyncio.sleep(999)

        async def close(self):
            self.closed = True

    manager = make_manager()
    manager.broadcast_timeout = 0.05
    hanging, alive = HangingWebSocket(), FakeWebSocket()
    manager.clients = [hanging, alive]

    # If the timeout logic ever regresses, broadcast() would hang on the
    # 999s sleep instead of pruning — wrap the drive in an outer timeout so
    # a regression fails this test fast instead of hanging the whole suite.
    asyncio.run(asyncio.wait_for(manager.broadcast(), timeout=10))

    assert manager.clients == [alive]
    assert alive.sent[-1]["type"] == "state"
    # Minor #2: a pruned client must actually be torn down, not left as a
    # zombie connection that gets no more broadcasts but never reconnects.
    assert hanging.closed is True


def test_pruned_client_without_close_method_does_not_crash_broadcast(clean_db):
    # A socket double (or a real socket already wedged) that lacks/fails a
    # close() must not raise past broadcast()'s own best-effort cleanup.
    class DeadNoCloseWebSocket:
        async def send_json(self, data):
            raise RuntimeError("gone")

    manager = make_manager()
    dead, alive = DeadNoCloseWebSocket(), FakeWebSocket()
    manager.clients = [dead, alive]

    asyncio.run(manager.broadcast())

    assert manager.clients == [alive]
    assert alive.sent[-1]["type"] == "state"


# --- Round 2 Critical: a huge finite buy_in must not brick the server ----

def test_set_config_rejects_huge_finite_buy_in(clean_db):
    # "1e999999999" is finite (passes is_finite()) and non-negative (passes
    # engine.py's buy_in < 0 check), but is astronomically beyond the
    # magnitude bound and must be rejected by _parse_decimal directly.
    manager = make_manager()
    original_buy_in = manager.state.buy_in
    admin = FakeWebSocket()

    asyncio.run(manager.handle_command(
        admin, "set_config", {"buy_in": "1e999999999"}))

    assert admin.sent[-1]["type"] == "error"
    assert manager.state.buy_in == original_buy_in


def test_set_config_huge_buy_in_does_not_poison_state_with_entries(clean_db):
    # Defense in depth: with total_entries > 0, compute_prize_pool's
    # buy_in * total_entries is actually exercised inside to_dict() (called
    # from persist()). Even if some huge-but-under-the-bound value slipped
    # through, the rollback in handle_command must keep self.state usable —
    # to_dict() must not raise, buy_in must be unchanged, and the connection
    # must keep working for subsequent commands (the server isn't bricked).
    manager = make_manager()
    admin = FakeWebSocket()
    manager.clients = [admin]
    asyncio.run(manager.handle_command(
        admin, "set_counts", {"total_entries": 10}))
    original_buy_in = manager.state.buy_in

    asyncio.run(manager.handle_command(
        admin, "set_config", {"buy_in": "1e999999999"}))

    assert admin.sent[-1]["type"] == "error"
    assert manager.state.buy_in == original_buy_in
    # Proves the server isn't bricked: to_dict() (called on every handshake,
    # broadcast, and tick) still works and reports the unchanged buy_in.
    assert manager.state.to_dict()["buy_in"] == str(original_buy_in)
    # And the connection is still fully usable afterward.
    asyncio.run(manager.handle_command(admin, "start", {}))
    assert admin.sent[-1]["type"] == "state"
    assert admin.sent[-1]["state"]["status"] == "running"


# --- Round 2 Important: a stalled direct error-reply must not wedge lock -

def test_stalled_error_reply_does_not_block_lock_for_other_commands(clean_db):
    class HangingWebSocket:
        def __init__(self):
            self.send_started = asyncio.Event()

        async def send_json(self, data):
            self.send_started.set()
            await asyncio.sleep(999)

    manager = make_manager()
    manager.broadcast_timeout = 0.05
    hanging = HangingWebSocket()
    second_client = FakeWebSocket()
    # handle_command's success path broadcasts to manager.clients, not
    # directly back to the caller's websocket — the second client must be
    # registered to observe the broadcast.
    manager.clients = [second_client]

    async def run():
        # "pause" before start is an EngineError — this exercises
        # handle_command's direct error-reply send, not broadcast().
        first = asyncio.create_task(manager.handle_command(hanging, "pause", {}))
        await asyncio.wait_for(hanging.send_started.wait(), timeout=5)
        # At this point `first` holds self.lock and is stalled inside its
        # direct error-reply send — exactly the scenario under test.
        assert manager.lock.locked()

        second = asyncio.create_task(
            manager.handle_command(second_client, "start", {}))
        # Bounded by broadcast_timeout (0.05s), not the 999s hang — if the
        # lock ever got wedged again, this would time out instead.
        await asyncio.wait_for(asyncio.gather(first, second), timeout=10)

    asyncio.run(run())

    assert manager.state.status == "running"
    assert second_client.sent[-1]["type"] == "state"
    assert second_client.sent[-1]["state"]["status"] == "running"
