import asyncio
from decimal import Decimal, InvalidOperation

from pydantic import ValidationError

from . import schemas, storage
from .db import SessionLocal
from .engine import EngineError, TournamentState


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
        return Decimal(str(raw))
    except InvalidOperation:
        raise EngineError("Invalid amount")


class TournamentManager:
    def __init__(self, session_factory=None):
        self.state = TournamentState()
        self.session_factory = session_factory or SessionLocal
        self.clients: list = []
        self.lock = asyncio.Lock()

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
    async def broadcast(self, message_type: str = "state") -> None:
        payload = {"type": message_type, "state": self.state.to_dict()}
        dead = []
        for websocket in list(self.clients):
            try:
                await websocket.send_json(payload)
            except Exception:
                dead.append(websocket)
        for websocket in dead:
            if websocket in self.clients:
                self.clients.remove(websocket)

    async def tick_once(self) -> None:
        async with self.lock:
            if self.state.status != "running":
                return
            event = self.state.tick()
            self.persist()
            await self.broadcast("level_change" if event == "level_change" else "state")

    async def run_ticker(self) -> None:
        while True:
            await asyncio.sleep(1)
            await self.tick_once()

    # --- commands ------------------------------------------------------
    async def handle_command(self, websocket, action: str, payload: dict) -> None:
        async with self.lock:
            try:
                self._apply(action, payload or {})
            except EngineError as exc:
                await websocket.send_json({"type": "error", "message": str(exc)})
                return
            self.persist()
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
