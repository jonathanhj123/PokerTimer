"""Pure tournament state machine and money math. No I/O here —
persistence and broadcasting live in manager.py."""
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
