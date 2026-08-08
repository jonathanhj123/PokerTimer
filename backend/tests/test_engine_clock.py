import pytest

from app.engine import EngineError, TournamentState
from tests.helpers import level


def running_state():
    state = TournamentState(structure=[level(25, 50), level(50, 100, minutes=20)])
    state.start()
    return state


def test_next_level_resets_clock_to_full_duration():
    state = running_state()
    state.next_level()
    assert state.current_index == 1
    assert state.seconds_remaining == 20 * 60


def test_next_level_at_end_raises():
    state = running_state()
    state.next_level()
    with pytest.raises(EngineError):
        state.next_level()


def test_prev_level_goes_back_with_full_duration():
    state = running_state()
    state.next_level()
    state.prev_level()
    assert state.current_index == 0
    assert state.seconds_remaining == 15 * 60


def test_prev_level_at_start_raises():
    with pytest.raises(EngineError):
        running_state().prev_level()


def test_adjust_time_adds_and_subtracts():
    state = running_state()
    state.adjust_time(60)
    assert state.seconds_remaining == 15 * 60 + 60
    state.adjust_time(-120)
    assert state.seconds_remaining == 15 * 60 - 60


def test_adjust_time_clamps_at_zero():
    state = running_state()
    state.adjust_time(-99999)
    assert state.seconds_remaining == 0


def test_set_time_exact():
    state = running_state()
    state.set_time(432)
    assert state.seconds_remaining == 432


def test_set_time_negative_raises():
    with pytest.raises(EngineError):
        running_state().set_time(-1)


def test_clock_commands_require_active_tournament():
    state = TournamentState(structure=[level(25, 50)])
    for command in (state.next_level, state.prev_level,
                    lambda: state.adjust_time(60), lambda: state.set_time(60)):
        with pytest.raises(EngineError):
            command()


def test_clock_commands_work_while_paused():
    state = running_state()
    state.pause()
    state.adjust_time(60)
    state.next_level()
    assert state.current_index == 1
