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

    # --- settings ------------------------------------------------------
    def set_config(self, *, buy_in: Decimal | None = None,
                   currency: str | None = None,
                   starting_stack: int | None = None,
                   early_bird_bonus: int | None = None) -> None:
        if buy_in is not None:
            if buy_in < 0:
                raise EngineError("Buy-in cannot be negative")
            self.buy_in = buy_in
        if currency is not None:
            currency = currency.strip()
            if not 1 <= len(currency) <= 5:
                raise EngineError("Currency must be 1-5 characters")
            self.currency = currency
        if starting_stack is not None:
            if starting_stack < 0:
                raise EngineError("Starting stack cannot be negative")
            self.starting_stack = starting_stack
        if early_bird_bonus is not None:
            if early_bird_bonus < 0:
                raise EngineError("Early-bird bonus cannot be negative")
            self.early_bird_bonus = early_bird_bonus

    def set_counts(self, *, total_entries: int | None = None,
                   players_remaining: int | None = None,
                   early_bird_count: int | None = None) -> None:
        for name, value in (("total_entries", total_entries),
                            ("players_remaining", players_remaining),
                            ("early_bird_count", early_bird_count)):
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise EngineError(f"{name} must be a non-negative whole number")
            setattr(self, name, value)

    def set_payouts(self, percentages: list[int]) -> None:
        if not percentages:
            raise EngineError("At least one paid place is required")
        for pct in percentages:
            if isinstance(pct, bool) or not isinstance(pct, int) or pct < 1:
                raise EngineError("Each percentage must be a whole number of at least 1")
        if sum(percentages) != 100:
            raise EngineError(f"Percentages must sum to 100 (currently {sum(percentages)})")
        self.payout_percentages = list(percentages)

    # --- serialization -------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "structure": [dict(entry) for entry in self.structure],
            "current_index": self.current_index,
            "seconds_remaining": self.seconds_remaining,
            "buy_in": str(self.buy_in),
            "currency": self.currency,
            "total_entries": self.total_entries,
            "players_remaining": self.players_remaining,
            "starting_stack": self.starting_stack,
            "early_bird_bonus": self.early_bird_bonus,
            "early_bird_count": self.early_bird_count,
            "payout_percentages": list(self.payout_percentages),
            "computed": self._computed(),
        }

    def _computed(self) -> dict:
        pool = compute_prize_pool(self.total_entries, self.buy_in)
        chips = compute_chips_in_play(self.total_entries, self.starting_stack,
                                      self.early_bird_count, self.early_bird_bonus)
        current = self.structure[self.current_index] if self.structure else None
        next_entry = (self.structure[self.current_index + 1]
                      if self.current_index + 1 < len(self.structure) else None)
        next_blinds = next(
            (entry for entry in self.structure[self.current_index + 1:]
             if entry["type"] == LEVEL), None)
        level_number = None
        if current is not None and current["type"] == LEVEL:
            level_number = sum(
                1 for entry in self.structure[: self.current_index + 1]
                if entry["type"] == LEVEL)
        return {
            "prize_pool": str(pool),
            "payouts": [str(p) for p in compute_payouts(pool, self.payout_percentages)],
            "chips_in_play": chips,
            "average_stack": compute_average_stack(chips, self.players_remaining),
            "current_entry": current,
            "next_entry": next_entry,
            "next_blinds": next_blinds,
            "level_number": level_number,
            "is_final_entry": (bool(self.structure)
                               and self.current_index == len(self.structure) - 1),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TournamentState":
        return cls(
            status=data["status"],
            structure=[dict(entry) for entry in data["structure"]],
            current_index=data["current_index"],
            seconds_remaining=data["seconds_remaining"],
            buy_in=Decimal(data["buy_in"]),
            currency=data["currency"],
            total_entries=data["total_entries"],
            players_remaining=data["players_remaining"],
            starting_stack=data["starting_stack"],
            early_bird_bonus=data["early_bird_bonus"],
            early_bird_count=data["early_bird_count"],
            payout_percentages=list(data["payout_percentages"]),
        )
