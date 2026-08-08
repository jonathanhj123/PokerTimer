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
