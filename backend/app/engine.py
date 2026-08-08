"""Pure tournament state machine and money math. No I/O here —
persistence and broadcasting live in manager.py."""
from dataclasses import dataclass, field
from decimal import Decimal

LEVEL = "level"
BREAK = "break"


class EngineError(ValueError):
    """Invalid command; the message is safe to show the admin verbatim."""


def compute_prize_pool(total_entries: int, buy_in: Decimal) -> Decimal:
    return buy_in * total_entries


def compute_payouts(pool: Decimal, percentages: list[int]) -> list[Decimal]:
    # Exact by design: the spec forbids rounding payouts.
    return [pool * pct / Decimal(100) for pct in percentages]


def compute_chips_in_play(total_entries: int, starting_stack: int,
                          early_bird_count: int, early_bird_bonus: int) -> int:
    return total_entries * starting_stack + early_bird_count * early_bird_bonus


def compute_average_stack(chips_in_play: int, players_remaining: int) -> int | None:
    if players_remaining <= 0:
        return None
    return round(chips_in_play / players_remaining)


@dataclass
class TournamentState:
    status: str = "setup"  # setup | running | paused | finished
    structure: list[dict] = field(default_factory=list)
    current_index: int = 0
    seconds_remaining: int = 0
    buy_in: Decimal = Decimal("0")
    currency: str = "$"
    total_entries: int = 0
    players_remaining: int = 0
    starting_stack: int = 0
    early_bird_bonus: int = 0
    early_bird_count: int = 0
    payout_percentages: list[int] = field(default_factory=lambda: [50, 30, 20])

    # --- lifecycle -----------------------------------------------------
    def start(self) -> None:
        if self.status != "setup":
            raise EngineError("Tournament already started")
        if not self.structure:
            raise EngineError("Cannot start with an empty structure")
        self.status = "running"
        self.current_index = 0
        self.seconds_remaining = self.structure[0]["minutes"] * 60

    def pause(self) -> None:
        if self.status != "running":
            raise EngineError("Can only pause a running tournament")
        self.status = "paused"

    def resume(self) -> None:
        if self.status != "paused":
            raise EngineError("Can only resume a paused tournament")
        self.status = "running"

    def end(self) -> None:
        if self.status not in ("running", "paused"):
            raise EngineError("No tournament in progress")
        self.status = "finished"

    def reset(self) -> None:
        # structure, buy_in, currency, starting_stack, early_bird_bonus and
        # payout_percentages survive a reset so the next game starts configured
        self.status = "setup"
        self.current_index = 0
        self.seconds_remaining = 0
        self.total_entries = 0
        self.players_remaining = 0
        self.early_bird_count = 0

    # --- clock ---------------------------------------------------------
    def tick(self) -> str | None:
        """Advance the clock one second. Returns "level_change" when a new
        entry begins, else None. No-op unless running."""
        if self.status != "running":
            return None
        if self.seconds_remaining > 0:
            self.seconds_remaining -= 1
        if self.seconds_remaining > 0:
            return None
        # clock at zero: move to the next entry if there is one, else park
        if self.current_index + 1 < len(self.structure):
            self.current_index += 1
            self.seconds_remaining = self.structure[self.current_index]["minutes"] * 60
            return "level_change"
        return None

    # --- navigation & time adjustment ---------------------------------
    def _require_active(self) -> None:
        if self.status not in ("running", "paused"):
            raise EngineError("No tournament in progress")

    def next_level(self) -> None:
        self._require_active()
        if self.current_index + 1 >= len(self.structure):
            raise EngineError("Already at the final level")
        self.current_index += 1
        self.seconds_remaining = self.structure[self.current_index]["minutes"] * 60

    def prev_level(self) -> None:
        self._require_active()
        if self.current_index == 0:
            raise EngineError("Already at the first level")
        self.current_index -= 1
        self.seconds_remaining = self.structure[self.current_index]["minutes"] * 60

    def adjust_time(self, delta_seconds: int) -> None:
        self._require_active()
        self.seconds_remaining = max(0, self.seconds_remaining + delta_seconds)

    def set_time(self, seconds: int) -> None:
        self._require_active()
        if seconds < 0:
            raise EngineError("Time cannot be negative")
        self.seconds_remaining = seconds

    # --- structure editing --------------------------------------------
    def _check_index(self, index: int) -> None:
        if not 0 <= index < len(self.structure):
            raise EngineError("Invalid entry index")

    def _advance_or_park(self) -> None:
        if self.current_index + 1 < len(self.structure):
            self.current_index += 1
            self.seconds_remaining = self.structure[self.current_index]["minutes"] * 60
        else:
            self.seconds_remaining = 0

    def update_entry(self, index: int, entry: dict) -> None:
        self._check_index(index)
        if index == self.current_index and self.status in ("running", "paused"):
            elapsed = self.structure[index]["minutes"] * 60 - self.seconds_remaining
            self.structure[index] = entry
            new_remaining = entry["minutes"] * 60 - elapsed
            if new_remaining <= 0:
                self._advance_or_park()
            else:
                self.seconds_remaining = new_remaining
        else:
            self.structure[index] = entry

    def insert_entry(self, index: int, entry: dict) -> None:
        if not 0 <= index <= len(self.structure):
            raise EngineError("Invalid entry index")
        self.structure.insert(index, entry)
        if self.status != "setup" and index <= self.current_index:
            self.current_index += 1

    def delete_entry(self, index: int) -> None:
        self._check_index(index)
        if len(self.structure) == 1:
            raise EngineError("Cannot delete the only entry")
        del self.structure[index]
        if self.status == "setup":
            self.current_index = 0
            return
        if index < self.current_index:
            self.current_index -= 1
        elif index == self.current_index:
            if self.current_index >= len(self.structure):
                # deleted the final entry while on it: park on the new last
                self.current_index = len(self.structure) - 1
                self.seconds_remaining = 0
            else:
                # spec: jump to the start of the entry that slid into this slot
                self.seconds_remaining = (
                    self.structure[self.current_index]["minutes"] * 60)

    def move_entry(self, from_index: int, to_index: int) -> None:
        self._check_index(from_index)
        if not 0 <= to_index < len(self.structure):
            raise EngineError("Invalid entry index")
        entry = self.structure.pop(from_index)
        self.structure.insert(to_index, entry)
        if self.status == "setup":
            return
        if from_index == self.current_index:
            self.current_index = to_index
        elif from_index < self.current_index <= to_index:
            self.current_index -= 1
        elif to_index <= self.current_index < from_index:
            self.current_index += 1

    def load_structure(self, structure: list[dict]) -> None:
        if self.status != "setup":
            raise EngineError("Templates can only be loaded during setup")
        if not structure:
            raise EngineError("Structure cannot be empty")
        self.structure = [dict(entry) for entry in structure]
        self.current_index = 0
        self.seconds_remaining = 0
