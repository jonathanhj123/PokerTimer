import asyncio
import logging
from decimal import Decimal, InvalidOperation

from pydantic import ValidationError

from . import schemas, storage
from .db import SessionLocal
from .engine import EngineError, TournamentState

logger = logging.getLogger(__name__)


def _require_int(payload: dict, key: str, *, allow_negative: bool = False) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise EngineError(f"{key} must be a whole number")
    if not allow_negative and value < 0:
        raise EngineError(f"{key} cannot be negative")
    return value


def _parse_entry(raw) -> dict:
    try:
        return schemas.entry_adapter.validate_python(raw).model_dump()
    except ValidationError:
        raise EngineError("Invalid level/break entry")


def _parse_decimal(raw) -> Decimal:
    try:
        value = Decimal(str(raw))
    except InvalidOperation:
        raise EngineError("Invalid amount")
    # is_finite() and copy_abs() are quiet, context-free operations that
    # never raise regardless of magnitude. abs(value) is NOT safe to use
    # here: for an extreme exponent (e.g. "1e999999999") it applies the
    # ambient decimal context's rounding/Emax check and raises
    # decimal.Overflow itself, before this guard ever gets a chance to
    # reject the value cleanly.
    if not value.is_finite() or value.copy_abs() > Decimal("1000000000"):
        # Decimal("Infinity") / Decimal("NaN") construct successfully but
        # poison downstream money math (e.g. buy_in * total_entries) forever.
        # A huge-but-finite value (e.g. "1e999999999") passes is_finite() and
        # the engine's buy_in < 0 check, but can overflow Decimal's default
        # 28-digit context inside compute_prize_pool/compute_payouts once
        # multiplied against realistic entry counts or percentages. A
        # billion-unit bound is comically beyond anything realistic while
        # leaving huge headroom before that math could overflow.
        raise EngineError("Invalid amount")
    return value


class TournamentManager:
    def __init__(self, session_factory=None):
        self.state = TournamentState()
        self.session_factory = session_factory or SessionLocal
        self.clients: list = []
        self.lock = asyncio.Lock()
        # A wedged client (e.g. a laptop with its lid closed) must not be
        # able to block broadcast() — and therefore the lock — forever.
        self.broadcast_timeout = 5

    # --- persistence ---------------------------------------------------
    def load_from_db(self) -> None:
        with self.session_factory() as session:
            snapshot = storage.load_snapshot(session)
        if snapshot is None:
            return
        self.state = TournamentState.from_dict(snapshot)
        if self.state.status == "running":
            # Spec: wall time lost in a crash is not counted; resume paused.
            self.state.status = "paused"
            self.persist()

    def persist(self) -> None:
        with self.session_factory() as session:
            storage.save_snapshot(session, self.state.to_dict())
            session.commit()

    # --- realtime ------------------------------------------------------
    async def _send_with_timeout(self, websocket, payload, timeout: float = 5) -> bool:
        try:
            await asyncio.wait_for(websocket.send_json(payload), timeout=timeout)
            return True
        except Exception:
            return False

    async def broadcast(self, message_type: str = "state") -> None:
        payload = {"type": message_type, "state": self.state.to_dict()}
        dead = []
        for websocket in list(self.clients):
            # Includes asyncio.TimeoutError: a client whose send buffer is
            # stuck must be pruned, not allowed to hold self.lock (via
            # tick_once/handle_command) forever.
            ok = await self._send_with_timeout(
                websocket, payload, timeout=self.broadcast_timeout)
            if not ok:
                dead.append(websocket)
        for websocket in dead:
            if websocket in self.clients:
                self.clients.remove(websocket)
            # Best-effort teardown: a pruned client gets no more broadcasts,
            # so leaving the socket open would leave a "zombie" connection
            # that never prompts the browser to reconnect. A socket that's
            # already wedged might not close cleanly either — that must not
            # raise past this point.
            try:
                await websocket.close()
            except Exception:
                pass

    async def tick_once(self) -> None:
        async with self.lock:
            if self.state.status != "running":
                return
            # Same rollback discipline as handle_command below: if tick() or
            # persist() fails partway, self.state must not be left poisoned
            # in memory for every subsequent handshake/broadcast/tick.
            snapshot = self.state.to_dict()
            try:
                event = self.state.tick()
                self.persist()
            except Exception:
                self.state = TournamentState.from_dict(snapshot)
                logger.exception("tick_once failed unexpectedly")
                return
            await self.broadcast("level_change" if event == "level_change" else "state")

    async def run_ticker(self) -> None:
        while True:
            await asyncio.sleep(1)
            try:
                await self.tick_once()
            except Exception:
                # An unanticipated exception here must not permanently kill
                # the background ticker — that would freeze the clock for
                # every connected display with zero diagnostic output.
                logger.exception("Ticker iteration failed")

    # --- commands ------------------------------------------------------
    async def handle_command(self, websocket, action: str, payload: dict) -> None:
        async with self.lock:
            # Some engine methods (e.g. set_config) mutate state before
            # fully validating it, so on any failure we must roll back to
            # exactly what was in effect before this command ran — otherwise
            # a partial mutation survives silently in memory. persist() is
            # deliberately INSIDE this same try: if it raises (e.g. a huge
            # buy_in overflowing Decimal math in to_dict()'s computed
            # fields), self.state must be rolled back too, or the poisoned
            # value survives in memory even though nothing was committed to
            # the DB (SQLAlchemy only commits on persist()'s last line).
            snapshot = self.state.to_dict()
            try:
                self._apply(action, payload or {})
                self.persist()
            except EngineError as exc:
                self.state = TournamentState.from_dict(snapshot)
                # Use the timeout-guarded send (same self.broadcast_timeout
                # budget as broadcast()) so a stalled/malformed client can't
                # wedge self.lock forever on this direct reply.
                await self._send_with_timeout(
                    websocket, {"type": "error", "message": str(exc)},
                    timeout=self.broadcast_timeout)
                return
            except Exception:
                # Backstop for anything not raised as EngineError (e.g. a
                # malformed payload reaching engine code as AttributeError/
                # TypeError, or persist() failing on a poisoned state).
                # Never leak internal exception details to the client.
                self.state = TournamentState.from_dict(snapshot)
                logger.exception("Unexpected error applying command %r", action)
                await self._send_with_timeout(
                    websocket, {"type": "error", "message": "Invalid command"},
                    timeout=self.broadcast_timeout)
                return
            # Manual changes (including next/prev level) broadcast plain
            # "state" — only the automatic ticker advance emits "level_change",
            # so admin corrections never trigger the display's flash/sound.
            await self.broadcast()

    async def load_template(self, template_id: int) -> bool:
        async with self.lock:
            with self.session_factory() as session:
                template = storage.get_template(session, template_id)
            if template is None:
                return False
            self.state.load_structure(template["structure"])
            self.persist()
            await self.broadcast()
            return True

    def _apply(self, action: str, p: dict) -> None:
        s = self.state
        if action == "start":
            s.start()
        elif action == "pause":
            s.pause()
        elif action == "resume":
            s.resume()
        elif action == "end":
            s.end()
        elif action == "reset":
            s.reset()
        elif action == "next_level":
            s.next_level()
        elif action == "prev_level":
            s.prev_level()
        elif action == "adjust_time":
            s.adjust_time(_require_int(p, "delta_seconds", allow_negative=True))
        elif action == "set_time":
            s.set_time(_require_int(p, "seconds"))
        elif action == "update_entry":
            s.update_entry(_require_int(p, "index"), _parse_entry(p.get("entry")))
        elif action == "insert_entry":
            s.insert_entry(_require_int(p, "index"), _parse_entry(p.get("entry")))
        elif action == "delete_entry":
            s.delete_entry(_require_int(p, "index"))
        elif action == "move_entry":
            s.move_entry(_require_int(p, "from_index"), _require_int(p, "to_index"))
        elif action == "set_config":
            s.set_config(
                buy_in=_parse_decimal(p["buy_in"]) if "buy_in" in p else None,
                currency=p.get("currency"),
                starting_stack=(_require_int(p, "starting_stack")
                                if "starting_stack" in p else None),
                early_bird_bonus=(_require_int(p, "early_bird_bonus")
                                  if "early_bird_bonus" in p else None),
            )
        elif action == "set_counts":
            s.set_counts(
                total_entries=(_require_int(p, "total_entries")
                               if "total_entries" in p else None),
                players_remaining=(_require_int(p, "players_remaining")
                                   if "players_remaining" in p else None),
                early_bird_count=(_require_int(p, "early_bird_count")
                                  if "early_bird_count" in p else None),
            )
        elif action == "set_payouts":
            percentages = p.get("percentages")
            if not isinstance(percentages, list):
                raise EngineError("percentages must be a list")
            s.set_payouts(percentages)
        else:
            raise EngineError(f"Unknown command: {action}")


manager = TournamentManager()
