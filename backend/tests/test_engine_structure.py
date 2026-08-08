import pytest

from app.engine import EngineError, TournamentState
from tests.helpers import brk, level


def running_state():
    state = TournamentState(
        structure=[level(25, 50), level(50, 100), level(75, 150)])
    state.start()
    return state


def test_update_noncurrent_entry_replaces_it():
    state = running_state()
    state.update_entry(2, level(100, 200, ante=25))
    assert state.structure[2] == level(100, 200, ante=25)
    assert state.seconds_remaining == 15 * 60   # clock untouched


def test_update_current_entry_preserves_elapsed_time():
    state = running_state()
    state.seconds_remaining = 3 * 60            # 12 min elapsed of 15
    state.update_entry(0, level(25, 50, minutes=20))
    assert state.seconds_remaining == 8 * 60    # 20 - 12


def test_update_current_entry_shorter_than_elapsed_advances():
    state = running_state()
    state.seconds_remaining = 3 * 60            # 12 min elapsed
    state.update_entry(0, level(25, 50, minutes=10))
    assert state.current_index == 1
    assert state.seconds_remaining == 15 * 60


def test_update_final_entry_shorter_than_elapsed_parks():
    state = TournamentState(structure=[level(25, 50)])
    state.start()
    state.seconds_remaining = 3 * 60
    state.update_entry(0, level(25, 50, minutes=10))
    assert state.current_index == 0
    assert state.seconds_remaining == 0


def test_update_in_setup_never_touches_clock():
    state = TournamentState(structure=[level(25, 50)])
    state.update_entry(0, level(100, 200, minutes=30))
    assert state.seconds_remaining == 0
    assert state.structure[0]["sb"] == 100


def test_insert_before_current_shifts_index():
    state = running_state()
    state.next_level()                          # current_index == 1
    state.insert_entry(0, brk(5))
    assert state.current_index == 2
    assert state.structure[state.current_index] == level(50, 100)


def test_insert_after_current_keeps_index():
    state = running_state()
    state.insert_entry(3, brk(5))
    assert state.current_index == 0


def test_insert_in_setup_keeps_index_zero():
    state = TournamentState(structure=[level(25, 50)])
    state.insert_entry(0, brk(5))
    assert state.current_index == 0


def test_delete_before_current_shifts_index_down():
    state = running_state()
    state.next_level()
    state.delete_entry(0)
    assert state.current_index == 0
    assert state.structure[0] == level(50, 100)


def test_delete_current_jumps_to_start_of_next():
    state = running_state()
    state.seconds_remaining = 100
    state.delete_entry(0)
    assert state.current_index == 0
    assert state.structure[0] == level(50, 100)
    assert state.seconds_remaining == 15 * 60   # full duration of what slid in


def test_delete_current_final_entry_parks():
    state = running_state()
    state.next_level()
    state.next_level()                          # on index 2, the last
    state.delete_entry(2)
    assert state.current_index == 1
    assert state.seconds_remaining == 0


def test_delete_only_entry_raises():
    state = TournamentState(structure=[level(25, 50)])
    with pytest.raises(EngineError):
        state.delete_entry(0)


def test_move_current_entry_follows_it():
    state = running_state()
    state.move_entry(0, 2)
    assert state.current_index == 2
    assert state.structure[2] == level(25, 50)


def test_move_other_entry_around_current_adjusts_index():
    state = running_state()
    state.next_level()                          # current_index == 1
    state.move_entry(0, 2)                      # entry before current moved after
    assert state.current_index == 0
    assert state.structure[0] == level(50, 100)
    state.move_entry(2, 0)                      # moved back
    assert state.current_index == 1


def test_load_structure_only_in_setup():
    state = TournamentState(structure=[level(25, 50)])
    state.load_structure([level(100, 200), brk(10)])
    assert len(state.structure) == 2
    state.start()
    with pytest.raises(EngineError):
        state.load_structure([level(25, 50)])


def test_load_empty_structure_raises():
    with pytest.raises(EngineError):
        TournamentState().load_structure([])


def test_index_out_of_range_raises():
    state = running_state()
    for bad_call in (lambda: state.update_entry(9, level(1, 2)),
                     lambda: state.delete_entry(9),
                     lambda: state.insert_entry(9, brk()),
                     lambda: state.move_entry(0, 9)):
        with pytest.raises(EngineError):
            bad_call()
