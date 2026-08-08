# Rebuy Pricing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let rebuys be priced (and stacked) differently from the original buy-in, and have the prize pool / chip count reflect both.

**Architecture:** This is a targeted amendment to an already-shipped, merged codebase, not a new feature built from scratch. It extends the existing `TournamentState` dataclass in `backend/app/engine.py` with a second price/stack/count triplet for rebuys — mirroring the `early_bird_bonus`/`early_bird_count` pattern the codebase already uses — then threads it through `manager.py`'s command dispatch and `MoneyPanel.svelte`'s admin UI. No new files, no new WebSocket message types, no new REST endpoints.

**Tech Stack:** Python 3.11+ (FastAPI backend, unchanged), Svelte 5 (frontend, unchanged).

**Spec:** `docs/superpowers/specs/2026-08-08-poker-timer-rebuy-pricing-design.md` — read it before starting if anything here seems ambiguous.

## Global Constraints

- Repo root is `C:\Users\jona2\ProProjects\PokerTimer`. Backend commands run from `backend/` with the venv active (`.venv\Scripts\activate` on PowerShell: `.venv\Scripts\Activate.ps1`). Frontend commands run from `frontend/`.
- Money (`rebuy_price`) is `decimal.Decimal`, serialized as a string, exactly like `buy_in`. **Never a float, never rounded.**
- `rebuy_price` and `rebuy_stack` go through the SAME validation helpers already used for `buy_in`/`starting_stack`: `manager.py`'s `_parse_decimal` (non-finite + magnitude-bound rejection) and `_require_int` (non-negative + magnitude-bound rejection). Do not write new validation logic — call the existing functions.
- `total_entries` is renamed to `entries` everywhere (dataclass field, `to_dict`/`from_dict` keys, `set_counts` parameter, WS payload key, admin UI). Its meaning also narrows: it now counts ONLY original buy-ins; rebuys are counted separately in the new `rebuy_count` field. There is no data migration concern — this is a pre-release local app with no production data.
- Reset behavior: `rebuy_count` zeroes on `reset()` (like `early_bird_count`); `rebuy_price` and `rebuy_stack` survive `reset()` as config (like `buy_in`/`starting_stack`).
- Commit after every task with the message given in the task.

## File Structure (changes only)

```
backend/
  app/
    engine.py          # MODIFY: rename total_entries→entries, add rebuy_price/rebuy_stack/rebuy_count,
                        #   update compute_prize_pool/compute_chips_in_play/reset/set_config/set_counts/
                        #   to_dict/_computed/from_dict
    manager.py          # MODIFY: _apply()'s set_config/set_counts branches gain the new fields;
                        #   two comments referencing total_entries updated for consistency
  tests/
    test_money.py               # MODIFY: update call sites for new function signatures, add rebuy cases
    test_engine_lifecycle.py    # MODIFY: reset test covers new fields
    test_engine_serialize.py    # MODIFY: renamed field, new set_config/set_counts coverage, new
                                 #   computed-pool/chips-with-rebuys test, roundtrip covers rebuy fields
    test_manager.py             # MODIFY: renamed payload key, new set_config/set_counts rebuy tests
frontend/
  src/lib/admin/
    MoneyPanel.svelte   # MODIFY: two new config fields (Rebuy price, Rebuy stack), counter row split
                        #   into Entries + Rebuys
```

---

### Task 1: Engine money math and data model

**Files:**
- Modify: `backend/app/engine.py` (complete replacement — see Step 3)
- Modify: `backend/tests/test_money.py` (complete replacement — see Step 1)
- Modify: `backend/tests/test_engine_lifecycle.py:60-78`
- Modify: `backend/tests/test_engine_serialize.py` (complete replacement — see Step 1)

**Interfaces:**
- Produces: `compute_prize_pool(entries: int, buy_in: Decimal, rebuy_count: int, rebuy_price: Decimal) -> Decimal` — was `compute_prize_pool(total_entries, buy_in)`, now returns `buy_in * entries + rebuy_price * rebuy_count`.
- Produces: `compute_chips_in_play(entries: int, starting_stack: int, rebuy_count: int, rebuy_stack: int, early_bird_count: int, early_bird_bonus: int) -> int` — was `compute_chips_in_play(total_entries, starting_stack, early_bird_count, early_bird_bonus)`.
- Produces: `TournamentState` gains fields `rebuy_price: Decimal = Decimal("0")`, `rebuy_stack: int = 0`, `rebuy_count: int = 0`; field `total_entries` is renamed to `entries` (same type/default: `int = 0`).
- Produces: `TournamentState.set_config(...)` gains keyword params `rebuy_price: Decimal | None = None`, `rebuy_stack: int | None = None`.
- Produces: `TournamentState.set_counts(...)` param `total_entries` renamed to `entries`; gains `rebuy_count: int | None = None`.
- Produces: `to_dict()`/`from_dict()` gain keys `"rebuy_price"` (string), `"rebuy_stack"` (int), `"rebuy_count"` (int); key `"total_entries"` renamed to `"entries"`.
- Consumed by: Task 2 (`manager.py`'s `_apply`, which calls `set_config`/`set_counts` with these exact parameter names).

- [ ] **Step 1: Write the failing tests**

Replace `backend/tests/test_money.py` entirely with:

```python
from decimal import Decimal

from app.engine import (
    compute_average_stack,
    compute_chips_in_play,
    compute_payouts,
    compute_prize_pool,
)


def test_prize_pool_is_entries_times_buy_in():
    assert compute_prize_pool(9, Decimal("20"), 0, Decimal("0")) == Decimal("180")


def test_prize_pool_with_decimal_buy_in():
    assert compute_prize_pool(3, Decimal("12.50"), 0, Decimal("0")) == Decimal("37.50")


def test_prize_pool_includes_rebuys_at_their_own_price():
    # 9 original entries at 50kr + 4 rebuys at 25kr = 450 + 100 = 550
    assert compute_prize_pool(9, Decimal("50"), 4, Decimal("25")) == Decimal("550")


def test_prize_pool_with_zero_rebuys_ignores_rebuy_price():
    assert compute_prize_pool(9, Decimal("20"), 0, Decimal("25")) == Decimal("180")


def test_payouts_are_exact_no_rounding():
    payouts = compute_payouts(Decimal("225"), [50, 30, 20])
    assert payouts == [Decimal("112.5"), Decimal("67.5"), Decimal("45")]


def test_payouts_sum_to_pool_exactly():
    pool = Decimal("220")
    assert sum(compute_payouts(pool, [50, 30, 20])) == pool


def test_chips_in_play_includes_early_bird_bonus():
    assert compute_chips_in_play(9, 10000, 0, 0, 5, 1000) == 95000


def test_chips_in_play_includes_rebuys_at_their_own_stack():
    # 9 entries * 10000 + 4 rebuys * 8000 + 5 early birds * 1000
    assert compute_chips_in_play(9, 10000, 4, 8000, 5, 1000) == 90000 + 32000 + 5000


def test_average_stack_rounds_to_nearest_chip():
    assert compute_average_stack(95000, 7) == 13571


def test_average_stack_is_none_with_no_players():
    assert compute_average_stack(95000, 0) is None
```

In `backend/tests/test_engine_lifecycle.py`, replace lines 60-78 (the `test_reset_zeroes_counters_but_keeps_config` function) with:

```python
def test_reset_zeroes_counters_but_keeps_config():
    state = make_state()
    state.buy_in = Decimal("20")
    state.currency = "kr"
    state.starting_stack = 10000
    state.early_bird_bonus = 1000
    state.rebuy_price = Decimal("10")
    state.rebuy_stack = 8000
    state.start()
    state.entries = 9
    state.players_remaining = 7
    state.early_bird_count = 5
    state.rebuy_count = 4
    state.end()
    state.reset()
    assert state.status == "setup"
    assert state.current_index == 0 and state.seconds_remaining == 0
    assert state.entries == 0 and state.players_remaining == 0
    assert state.early_bird_count == 0
    assert state.rebuy_count == 0
    assert state.buy_in == Decimal("20") and state.currency == "kr"
    assert state.starting_stack == 10000 and state.early_bird_bonus == 1000
    assert state.rebuy_price == Decimal("10") and state.rebuy_stack == 8000
    assert len(state.structure) == 3
```

Replace `backend/tests/test_engine_serialize.py` entirely with:

```python
from decimal import Decimal

import pytest

from app.engine import EngineError, TournamentState
from tests.helpers import brk, level


def configured_state():
    state = TournamentState(
        structure=[level(25, 50), level(50, 100), brk(10), level(75, 150, ante=25)],
        buy_in=Decimal("20"), entries=11, players_remaining=7,
        starting_stack=10000, early_bird_bonus=1000, early_bird_count=5)
    return state


def test_set_config_partial_update():
    state = TournamentState()
    state.set_config(buy_in=Decimal("25.50"), currency="kr")
    assert state.buy_in == Decimal("25.50")
    assert state.currency == "kr"
    assert state.starting_stack == 0            # untouched


def test_set_config_validation():
    state = TournamentState()
    with pytest.raises(EngineError):
        state.set_config(buy_in=Decimal("-1"))
    with pytest.raises(EngineError):
        state.set_config(currency="")
    with pytest.raises(EngineError):
        state.set_config(currency="toolong")
    with pytest.raises(EngineError):
        state.set_config(starting_stack=-1)


def test_set_config_rebuy_price_and_stack():
    state = TournamentState()
    state.set_config(rebuy_price=Decimal("25"), rebuy_stack=8000)
    assert state.rebuy_price == Decimal("25")
    assert state.rebuy_stack == 8000
    assert state.buy_in == Decimal("0")          # untouched
    with pytest.raises(EngineError):
        state.set_config(rebuy_price=Decimal("-1"))
    with pytest.raises(EngineError):
        state.set_config(rebuy_stack=-1)


def test_set_counts_and_validation():
    state = TournamentState()
    state.set_counts(entries=9, players_remaining=7, early_bird_count=5,
                     rebuy_count=3)
    assert (state.entries, state.players_remaining,
           state.early_bird_count, state.rebuy_count) == (9, 7, 5, 3)
    with pytest.raises(EngineError):
        state.set_counts(players_remaining=-1)
    with pytest.raises(EngineError):
        state.set_counts(entries=True)    # bools are not counts
    with pytest.raises(EngineError):
        state.set_counts(rebuy_count=-1)


def test_set_payouts_validation():
    state = TournamentState()
    state.set_payouts([60, 40])
    assert state.payout_percentages == [60, 40]
    with pytest.raises(EngineError):
        state.set_payouts([])
    with pytest.raises(EngineError):
        state.set_payouts([50, 30, 19])         # sums to 99
    with pytest.raises(EngineError):
        state.set_payouts([100, 0])             # 0 not allowed


def test_to_dict_money_as_strings():
    data = configured_state().to_dict()
    assert data["buy_in"] == "20"
    assert data["rebuy_price"] == "0"            # default, no rebuys configured
    assert data["computed"]["prize_pool"] == "220"
    assert data["computed"]["payouts"] == ["110", "66", "44"]


def test_to_dict_exact_decimal_payouts():
    state = configured_state()
    state.entries = 9                            # pool 180 → 50% = 90; use odd pool
    state.buy_in = Decimal("25")                 # pool 225
    payouts = state.to_dict()["computed"]["payouts"]
    assert payouts == ["112.5", "67.5", "45"]


def test_computed_chip_stats():
    computed = configured_state().to_dict()["computed"]
    assert computed["chips_in_play"] == 11 * 10000 + 5 * 1000
    assert computed["average_stack"] == round(115000 / 7)


def test_computed_includes_rebuys_in_pool_and_chips():
    state = configured_state()
    state.rebuy_price = Decimal("10")
    state.rebuy_stack = 8000
    state.rebuy_count = 3
    computed = state.to_dict()["computed"]
    # pool: 11 entries * 20 + 3 rebuys * 10 = 220 + 30
    assert computed["prize_pool"] == "250"
    # chips: 11*10000 + 3*8000 + 5*1000 = 110000 + 24000 + 5000
    assert computed["chips_in_play"] == 139000


def test_computed_next_entry_vs_next_blinds():
    state = configured_state()
    state.start()
    state.next_level()                          # on index 1; next entry is the break
    computed = state.to_dict()["computed"]
    assert computed["next_entry"]["type"] == "break"
    assert computed["next_blinds"] == level(75, 150, ante=25)


def test_level_number_skips_breaks():
    state = configured_state()
    state.start()
    assert state.to_dict()["computed"]["level_number"] == 1
    state.next_level()
    state.next_level()                          # now on the break
    assert state.to_dict()["computed"]["level_number"] is None
    state.next_level()                          # past the break
    assert state.to_dict()["computed"]["level_number"] == 3


def test_is_final_entry():
    state = configured_state()
    state.start()
    assert state.to_dict()["computed"]["is_final_entry"] is False
    state.next_level(); state.next_level(); state.next_level()
    assert state.to_dict()["computed"]["is_final_entry"] is True


def test_roundtrip_from_dict():
    state = configured_state()
    state.rebuy_price = Decimal("15")
    state.rebuy_stack = 7500
    state.rebuy_count = 2
    state.start()
    state.tick()
    restored = TournamentState.from_dict(state.to_dict())
    assert restored.to_dict() == state.to_dict()
    assert restored.buy_in == Decimal("20")       # real Decimal, not str
    assert restored.rebuy_price == Decimal("15")  # real Decimal, not str
```

- [ ] **Step 2: Run tests to verify they fail**

From `backend/`: `python -m pytest tests/test_money.py tests/test_engine_lifecycle.py tests/test_engine_serialize.py -v`
Expected: FAIL — `TypeError: compute_prize_pool() missing 2 required positional arguments` (test_money.py), and `TypeError: TournamentState.__init__() got an unexpected keyword argument 'entries'` (test_engine_lifecycle.py / test_engine_serialize.py).

- [ ] **Step 3: Replace `backend/app/engine.py` entirely with:**

```python
"""Pure tournament state machine and money math. No I/O here —
persistence and broadcasting live in manager.py."""
from dataclasses import dataclass, field
from decimal import Decimal

LEVEL = "level"
BREAK = "break"


class EngineError(ValueError):
    """Invalid command; the message is safe to show the admin verbatim."""


def compute_prize_pool(entries: int, buy_in: Decimal,
                       rebuy_count: int, rebuy_price: Decimal) -> Decimal:
    return buy_in * entries + rebuy_price * rebuy_count


def compute_payouts(pool: Decimal, percentages: list[int]) -> list[Decimal]:
    # Exact by design: the spec forbids rounding payouts.
    return [pool * pct / Decimal(100) for pct in percentages]


def compute_chips_in_play(entries: int, starting_stack: int,
                          rebuy_count: int, rebuy_stack: int,
                          early_bird_count: int, early_bird_bonus: int) -> int:
    return (entries * starting_stack + rebuy_count * rebuy_stack
            + early_bird_count * early_bird_bonus)


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
    entries: int = 0
    players_remaining: int = 0
    starting_stack: int = 0
    early_bird_bonus: int = 0
    early_bird_count: int = 0
    rebuy_price: Decimal = Decimal("0")
    rebuy_stack: int = 0
    rebuy_count: int = 0
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
        # structure, buy_in, currency, starting_stack, early_bird_bonus,
        # rebuy_price, rebuy_stack and payout_percentages survive a reset so
        # the next game starts configured
        self.status = "setup"
        self.current_index = 0
        self.seconds_remaining = 0
        self.entries = 0
        self.players_remaining = 0
        self.early_bird_count = 0
        self.rebuy_count = 0

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
                   early_bird_bonus: int | None = None,
                   rebuy_price: Decimal | None = None,
                   rebuy_stack: int | None = None) -> None:
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
        if rebuy_price is not None:
            if rebuy_price < 0:
                raise EngineError("Rebuy price cannot be negative")
            self.rebuy_price = rebuy_price
        if rebuy_stack is not None:
            if rebuy_stack < 0:
                raise EngineError("Rebuy stack cannot be negative")
            self.rebuy_stack = rebuy_stack

    def set_counts(self, *, entries: int | None = None,
                   players_remaining: int | None = None,
                   early_bird_count: int | None = None,
                   rebuy_count: int | None = None) -> None:
        for name, value in (("entries", entries),
                            ("players_remaining", players_remaining),
                            ("early_bird_count", early_bird_count),
                            ("rebuy_count", rebuy_count)):
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
            "entries": self.entries,
            "players_remaining": self.players_remaining,
            "starting_stack": self.starting_stack,
            "early_bird_bonus": self.early_bird_bonus,
            "early_bird_count": self.early_bird_count,
            "rebuy_price": str(self.rebuy_price),
            "rebuy_stack": self.rebuy_stack,
            "rebuy_count": self.rebuy_count,
            "payout_percentages": list(self.payout_percentages),
            "computed": self._computed(),
        }

    def _computed(self) -> dict:
        pool = compute_prize_pool(self.entries, self.buy_in,
                                  self.rebuy_count, self.rebuy_price)
        chips = compute_chips_in_play(self.entries, self.starting_stack,
                                      self.rebuy_count, self.rebuy_stack,
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
            entries=data["entries"],
            players_remaining=data["players_remaining"],
            starting_stack=data["starting_stack"],
            early_bird_bonus=data["early_bird_bonus"],
            early_bird_count=data["early_bird_count"],
            rebuy_price=Decimal(data["rebuy_price"]),
            rebuy_stack=data["rebuy_stack"],
            rebuy_count=data["rebuy_count"],
            payout_percentages=list(data["payout_percentages"]),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

From `backend/`: `python -m pytest tests/test_money.py tests/test_engine_lifecycle.py tests/test_engine_serialize.py -v`
Expected: all PASS (10 + 8 + 14 = 32 tests across the three files — exact counts aren't load-bearing, "all pass, zero failures" is).

- [ ] **Step 5: Run the full backend suite to check for collateral breakage**

From `backend/`: `python -m pytest tests -v`
Expected: FAILURES in `tests/test_manager.py` only (it still calls `set_counts`/references `total_entries` under the old name — that's Task 2's job to fix). No failures anywhere else. If you see failures outside `test_manager.py`, stop and re-examine — something in this task's engine.py rewrite doesn't match the file's actual prior content.

- [ ] **Step 6: Commit**

```bash
git add backend/app/engine.py backend/tests/test_money.py backend/tests/test_engine_lifecycle.py backend/tests/test_engine_serialize.py
git commit -m "feat: separate rebuy price/stack from original buy-in in tournament engine"
```

---

### Task 2: Manager command wiring

**Files:**
- Modify: `backend/app/manager.py:14-28` (comment wording only), `:263-280` (the `set_config`/`set_counts` branches of `_apply`)
- Modify: `backend/tests/test_manager.py:284-303`, `:393-403`

**Interfaces:**
- Consumes: `TournamentState.set_config(..., rebuy_price=..., rebuy_stack=...)` and `TournamentState.set_counts(entries=..., ..., rebuy_count=...)` from Task 1 — exact parameter names as defined there.
- Produces: the `set_config` WS command accepts `rebuy_price` (string, parsed via `_parse_decimal`) and `rebuy_stack` (int, via `_require_int`) in its payload; the `set_counts` WS command accepts `entries` (renamed from `total_entries`) and `rebuy_count` (int, via `_require_int`).
- Consumed by: Task 3 (`MoneyPanel.svelte`'s `send('set_config', {...})` / `send('set_counts', {...})` calls must use these exact payload key names).

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_manager.py`, replace lines 284-303 (the `test_set_config_huge_buy_in_does_not_poison_state_with_entries` function) with:

```python
def test_set_config_huge_buy_in_does_not_poison_state_with_entries(clean_db):
    # Defense in depth: with entries > 0, compute_prize_pool's
    # buy_in * entries is actually exercised inside to_dict() (called
    # from persist()). Even if some huge-but-under-the-bound value slipped
    # through, the rollback in handle_command must keep self.state usable —
    # to_dict() must not raise, buy_in must be unchanged, and the connection
    # must keep working for subsequent commands (the server isn't bricked).
    manager = make_manager()
    admin = FakeWebSocket()
    manager.clients = [admin]
    asyncio.run(manager.handle_command(
        admin, "set_counts", {"entries": 10}))
    original_buy_in = manager.state.buy_in

    asyncio.run(manager.handle_command(
        admin, "set_config", {"buy_in": "1e999999999"}))

    assert admin.sent[-1]["type"] == "error"
    assert manager.state.buy_in == original_buy_in
```

(Lines below that function — `# Round 2 Important:` onward through `test_hanging_close_is_pruned_instead_of_blocking_broadcast` — are unchanged; leave them exactly as they are.)

Replace lines 393-403 (the `test_set_counts_rejects_absurdly_large_total_entries` function, at the end of the file) with:

```python
def test_set_counts_rejects_absurdly_large_entries(clean_db):
    manager = make_manager()
    admin = FakeWebSocket()
    original_entries = manager.state.entries

    asyncio.run(manager.handle_command(
        admin, "set_counts", {"entries": 10**12}))

    assert admin.sent[-1]["type"] == "error"
    assert manager.state.entries == original_entries


def test_set_config_rebuy_price_and_stack_applied(clean_db):
    from decimal import Decimal

    manager = make_manager()
    asyncio.run(manager.handle_command(
        FakeWebSocket(), "set_config",
        {"rebuy_price": "12.50", "rebuy_stack": 8000}))
    assert manager.state.rebuy_price == Decimal("12.50")
    assert manager.state.rebuy_stack == 8000


def test_set_counts_rebuy_count_applied(clean_db):
    manager = make_manager()
    asyncio.run(manager.handle_command(
        FakeWebSocket(), "set_counts", {"rebuy_count": 4}))
    assert manager.state.rebuy_count == 4


def test_set_config_rejects_huge_finite_rebuy_price(clean_db):
    # Same magnitude-bound guard as buy_in — rebuy_price goes through the
    # identical _parse_decimal() call, so this proves the wiring rather
    # than re-testing _parse_decimal's own logic (already covered above).
    manager = make_manager()
    original_rebuy_price = manager.state.rebuy_price
    admin = FakeWebSocket()

    asyncio.run(manager.handle_command(
        admin, "set_config", {"rebuy_price": "1e999999999"}))

    assert admin.sent[-1]["type"] == "error"
    assert manager.state.rebuy_price == original_rebuy_price
```

- [ ] **Step 2: Run tests to verify they fail**

From `backend/`: `python -m pytest tests/test_manager.py -v`
Expected: FAIL — the two renamed-payload tests fail with `assert manager.state.entries == 0` type errors (since `entries` isn't being set because `_apply` doesn't pass it through yet — actually these will raise `EngineError`/produce an `"error"` reply from `set_counts`/`set_config` rejecting an unrecognized-but-harmless key, or simply leave state unchanged since `_apply` doesn't forward `"entries"`/`"rebuy_price"`/`"rebuy_count"`/`"rebuy_stack"` to `set_config`/`set_counts` yet). The three new rebuy-specific tests fail similarly — the state's rebuy fields never get set because `_apply` doesn't forward them.

- [ ] **Step 3: Update `backend/app/manager.py`**

Replace lines 14-28 (the `_require_int` function's docstring comment) with:

```python
def _require_int(payload: dict, key: str, *, allow_negative: bool = False) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise EngineError(f"{key} must be a whole number")
    if not allow_negative and value < 0:
        raise EngineError(f"{key} cannot be negative")
    # Mirrors _parse_decimal's magnitude bound: an unbounded int (e.g. a
    # 4000-digit entries count) gets committed to the DB and makes every
    # subsequent to_dict() do 4000-digit arithmetic. A billion is comically
    # beyond any realistic player count, chip stack, or index. Plain ints
    # don't have Decimal's context-bound abs() overflow hazard, so a normal
    # abs() is safe here.
    if abs(value) > 1_000_000_000:
        raise EngineError(f"{key} is too large")
    return value
```

Replace line 51 (inside `_parse_decimal`'s comment block) — the line reading:
```python
        # poison downstream money math (e.g. buy_in * total_entries) forever.
```
with:
```python
        # poison downstream money math (e.g. buy_in * entries) forever.
```

Replace lines 263-280 (the `set_config` and `set_counts` branches inside `_apply`) with:

```python
        elif action == "set_config":
            s.set_config(
                buy_in=_parse_decimal(p["buy_in"]) if "buy_in" in p else None,
                currency=p.get("currency"),
                starting_stack=(_require_int(p, "starting_stack")
                                if "starting_stack" in p else None),
                early_bird_bonus=(_require_int(p, "early_bird_bonus")
                                  if "early_bird_bonus" in p else None),
                rebuy_price=(_parse_decimal(p["rebuy_price"])
                            if "rebuy_price" in p else None),
                rebuy_stack=(_require_int(p, "rebuy_stack")
                            if "rebuy_stack" in p else None),
            )
        elif action == "set_counts":
            s.set_counts(
                entries=(_require_int(p, "entries")
                        if "entries" in p else None),
                players_remaining=(_require_int(p, "players_remaining")
                                   if "players_remaining" in p else None),
                early_bird_count=(_require_int(p, "early_bird_count")
                                  if "early_bird_count" in p else None),
                rebuy_count=(_require_int(p, "rebuy_count")
                            if "rebuy_count" in p else None),
            )
```

- [ ] **Step 4: Run tests to verify they pass**

From `backend/`: `python -m pytest tests/test_manager.py -v`
Expected: all PASS.

- [ ] **Step 5: Run the full backend suite**

From `backend/`: `python -m pytest tests -v`
Expected: all PASS, zero failures (this closes out all backend changes for this feature).

- [ ] **Step 6: Commit**

```bash
git add backend/app/manager.py backend/tests/test_manager.py
git commit -m "feat: wire rebuy price/stack/count through the WebSocket command layer"
```

---

### Task 3: Admin UI — rebuy price/stack fields and split entry counters

**Files:**
- Modify: `frontend/src/lib/admin/MoneyPanel.svelte` (complete replacement — see Step 1)

**Interfaces:**
- Consumes: the `set_config`/`set_counts` WS command payload shapes from Task 2 (`rebuy_price`, `rebuy_stack`, `entries`, `rebuy_count` keys); `conn`/`send` from `frontend/src/lib/connection.svelte.js` (unchanged, from the original implementation); `formatChips`/`formatMoney` from `frontend/src/lib/format.js` (unchanged).
- Produces: nothing consumed by a later task — this is the last task in the plan.

There is no dedicated automated test suite for this component (matches the project's existing pattern for admin sub-components — verified via build + a live check against the running app, same bar as the original `MoneyPanel.svelte` task).

- [ ] **Step 1: Replace `frontend/src/lib/admin/MoneyPanel.svelte` entirely with:**

```svelte
<script>
  import { conn, send } from '../connection.svelte.js';
  import { formatChips, formatMoney } from '../format.js';

  const s = $derived(conn.state);

  let buyIn = $state('');
  let currency = $state('');
  let stack = $state('');
  let bonus = $state('');
  let rebuyPrice = $state('');
  let rebuyStack = $state('');
  let seeded = false;

  $effect(() => {
    if (s && !seeded) {
      seeded = true;
      buyIn = s.buy_in;
      currency = s.currency;
      stack = String(s.starting_stack);
      bonus = String(s.early_bird_bonus);
      rebuyPrice = s.rebuy_price;
      rebuyStack = String(s.rebuy_stack);
    }
  });

  function applyConfig() {
    send('set_config', {
      buy_in: buyIn,
      currency,
      starting_stack: parseInt(stack, 10) || 0,
      early_bird_bonus: parseInt(bonus, 10) || 0,
      rebuy_price: rebuyPrice,
      rebuy_stack: parseInt(rebuyStack, 10) || 0,
    });
  }

  function bump(field, delta) {
    send('set_counts', { [field]: Math.max(0, s[field] + delta) });
  }

  const countRows = [
    ['entries', 'Entries'],
    ['rebuy_count', 'Rebuys'],
    ['players_remaining', 'Players remaining'],
    ['early_bird_count', 'Early birds'],
  ];
</script>

<section class="panel">
  <h3>Money & players</h3>
  <div class="grid2">
    <label>Buy-in <input bind:value={buyIn} inputmode="decimal" /></label>
    <label>Currency <input bind:value={currency} size="4" /></label>
    <label>Starting stack <input bind:value={stack} inputmode="numeric" /></label>
    <label>Early-bird chips <input bind:value={bonus} inputmode="numeric" /></label>
    <label>Rebuy price <input bind:value={rebuyPrice} inputmode="decimal" /></label>
    <label>Rebuy stack <input bind:value={rebuyStack} inputmode="numeric" /></label>
  </div>
  <div class="row"><button onclick={applyConfig}>Apply</button></div>

  {#each countRows as [field, label]}
    <div class="row count-row">
      <span class="count-label">{label}</span>
      <button onclick={() => bump(field, -1)}>−</button>
      <strong class="count-value">{s[field]}</strong>
      <button onclick={() => bump(field, 1)}>+</button>
    </div>
  {/each}

  <p class="summary">
    Pool <strong>{formatMoney(s.computed.prize_pool, s.currency)}</strong>
    · Avg stack
    <strong>
      {s.computed.average_stack === null ? '—' : formatChips(s.computed.average_stack)}
    </strong>
  </p>
</section>

<style>
  .grid2 {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.6rem;
    margin-bottom: 0.8rem;
  }
  .grid2 label {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    font-size: 0.85rem;
    color: #9ca3af;
  }
  .count-row { justify-content: space-between; }
  .count-label { flex: 1; color: #9ca3af; }
  .count-value { min-width: 2ch; text-align: center; font-size: 1.1rem; }
  .summary { color: #9ca3af; margin: 0.6rem 0 0; }
</style>
```

- [ ] **Step 2: Verify the build succeeds**

From `frontend/`: `npm run build`
Expected: succeeds with no errors (Svelte compiler would error on any typo in the `$state`/`$effect`/template wiring).

- [ ] **Step 3: Live verification against the real backend**

Start the backend from `backend/` (venv active): `uvicorn app.main:app --port 8000`
Start the frontend dev server from `frontend/`: `npm run dev`

Open `http://localhost:5173/admin`, log in, and confirm:
- The Money & players panel now shows six config fields: Buy-in, Currency, Starting stack, Early-bird chips, Rebuy price, Rebuy stack.
- The counter rows now read: Entries, Rebuys, Players remaining, Early birds (four rows, each with its own `+`/`−`).
- Set Buy-in to `50`, Rebuy price to `25`, click Apply. Click `+` on Entries three times and `+` on Rebuys twice. Confirm the Pool summary at the bottom reads exactly `$200` (3 entries × $50 = $150, plus 2 rebuys × $25 = $50, total $200 — matching `entries × buy_in + rebuy_count × rebuy_price`).
- Open `http://localhost:5173/` (the display page) in a second tab and confirm the Pool figure there matches the admin panel's Pool figure exactly.

Stop both dev servers when done (find the listening PIDs via `netstat -ano | grep LISTENING | grep :8000` / `:5173` and stop them; verify with a `curl` to each port failing to connect afterward — Windows/uvicorn processes have been unreliable to kill by other means in this project before, so always re-verify the port is actually free).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/admin/MoneyPanel.svelte
git commit -m "feat: admin UI for separate rebuy price and stack"
```

---

## Self-Review Notes (for the plan author, already applied above)

- **Spec coverage:** data model (Task 1), money math (Task 1), reset behavior (Task 1), WS protocol (Task 2), admin UI (Task 3) — every section of the spec maps to a task. The spec's "What does NOT change" section (`Display.svelte`, `PayoutEditor.svelte`, `StructureEditor.svelte`, `TemplateBar.svelte`, `ClockControls.svelte`, `compute_payouts`) is correctly untouched by all three tasks.
- **Placeholder scan:** none found — every step has complete, runnable code.
- **Type consistency:** `entries`/`rebuy_count`/`rebuy_price`/`rebuy_stack` are named identically across `engine.py` (Task 1), `manager.py` (Task 2), and `MoneyPanel.svelte` (Task 3) — verified by construction, since Task 2 and Task 3 were written against Task 1's exact produced interface.
