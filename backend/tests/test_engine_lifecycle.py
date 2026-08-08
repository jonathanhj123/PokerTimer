from decimal import Decimal

import pytest

from app.engine import EngineError, TournamentState
from tests.helpers import brk, level


def make_state():
    return TournamentState(structure=[level(25, 50), level(50, 100), level(75, 150)])


def test_initial_state_is_setup():
    state = TournamentState()
    assert state.status == "setup"
    assert state.payout_percentages == [50, 30, 20]


def test_start_runs_first_level():
    state = make_state()
    state.start()
    assert state.status == "running"
    assert state.current_index == 0
    assert state.seconds_remaining == 15 * 60


def test_start_requires_structure():
    with pytest.raises(EngineError):
        TournamentState().start()


def test_start_twice_raises():
    state = make_state()
    state.start()
    with pytest.raises(EngineError):
        state.start()


def test_pause_resume_end_transitions():
    state = make_state()
    state.start()
    state.pause()
    assert state.status == "paused"
    state.resume()
    assert state.status == "running"
    state.end()
    assert state.status == "finished"


def test_invalid_transitions_raise():
    state = make_state()
    with pytest.raises(EngineError):
        state.pause()      # not running
    with pytest.raises(EngineError):
        state.resume()     # not paused
    with pytest.raises(EngineError):
        state.end()        # nothing in progress


def test_reset_zeroes_counters_but_keeps_config():
    state = make_state()
    state.buy_in = Decimal("20")
    state.currency = "kr"
    state.starting_stack = 10000
    state.early_bird_bonus = 1000
    state.start()
    state.total_entries = 9
    state.players_remaining = 7
    state.early_bird_count = 5
    state.end()
    state.reset()
    assert state.status == "setup"
    assert state.current_index == 0 and state.seconds_remaining == 0
    assert state.total_entries == 0 and state.players_remaining == 0
    assert state.early_bird_count == 0
    assert state.buy_in == Decimal("20") and state.currency == "kr"
    assert state.starting_stack == 10000 and state.early_bird_bonus == 1000
    assert len(state.structure) == 3


def test_tick_decrements_only_when_running():
    state = make_state()
    assert state.tick() is None            # setup: no-op
    state.start()
    assert state.tick() is None
    assert state.seconds_remaining == 15 * 60 - 1
    state.pause()
    state.tick()
    assert state.seconds_remaining == 15 * 60 - 1   # paused: no-op


def test_tick_advances_to_next_level_at_zero():
    state = make_state()
    state.start()
    state.seconds_remaining = 1
    assert state.tick() == "level_change"
    assert state.current_index == 1
    assert state.seconds_remaining == 15 * 60


def test_tick_advances_through_breaks():
    state = TournamentState(structure=[level(25, 50), brk(10), level(50, 100)])
    state.start()
    state.seconds_remaining = 1
    state.tick()
    assert state.structure[state.current_index]["type"] == "break"
    assert state.seconds_remaining == 10 * 60
    state.seconds_remaining = 1
    assert state.tick() == "level_change"
    assert state.current_index == 2


def test_tick_parks_on_final_entry():
    state = TournamentState(structure=[level(25, 50, minutes=1)])
    state.start()
    state.seconds_remaining = 1
    assert state.tick() is None
    assert state.seconds_remaining == 0
    assert state.current_index == 0
    assert state.tick() is None            # stays parked, no crash, no loop
    assert state.seconds_remaining == 0


def test_tick_advances_from_zero_when_next_exists():
    # covers "admin set the clock to 0 manually": next tick moves on
    state = make_state()
    state.start()
    state.seconds_remaining = 0
    assert state.tick() == "level_change"
    assert state.current_index == 1
