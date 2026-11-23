import random
from collections import Counter

import pytest

from app.engine import EngineError, TournamentState


# --- state, layout config, toggle, serialization ----------------------------

def test_seating_defaults():
    s = TournamentState()
    assert (s.players, s.table_count, s.seats_per_table, s.show_seating) == ([], 1, 9, False)


def test_set_seating_config_validates():
    s = TournamentState()
    s.set_seating_config(2, 8)
    assert (s.table_count, s.seats_per_table) == (2, 8)
    for bad in [(0, 8), (2, 0), (True, 8)]:
        with pytest.raises(EngineError):
            s.set_seating_config(*bad)


def test_set_seating_config_rejects_stranding_seated_players():
    s = TournamentState(table_count=2, seats_per_table=9,
                        players=[{"name": "Anna", "table": 2, "seat": 9}])
    with pytest.raises(EngineError):
        s.set_seating_config(1, 9)
    with pytest.raises(EngineError):
        s.set_seating_config(2, 8)
    assert (s.table_count, s.seats_per_table) == (2, 9)


def test_set_show_seating():
    s = TournamentState()
    s.set_show_seating(True)
    assert s.show_seating is True
    with pytest.raises(EngineError):
        s.set_show_seating("yes")


def test_reset_clears_players_keeps_layout():
    s = TournamentState(table_count=2, seats_per_table=8, show_seating=True,
                        players=[{"name": "Anna", "table": 1, "seat": 3}])
    s.reset()
    assert s.players == [] and s.show_seating is False
    assert (s.table_count, s.seats_per_table) == (2, 8)


def test_seating_roundtrip():
    s = TournamentState(table_count=2, seats_per_table=8, show_seating=True,
                        players=[{"name": "Anna", "table": 1, "seat": 3}])
    restored = TournamentState.from_dict(s.to_dict())
    assert restored.players == s.players
    assert (restored.table_count, restored.seats_per_table, restored.show_seating) == (2, 8, True)


def test_from_dict_without_seating_keys_uses_defaults():
    data = TournamentState().to_dict()
    for key in ("players", "table_count", "seats_per_table", "show_seating"):
        del data[key]
    restored = TournamentState.from_dict(data)
    assert (restored.players, restored.table_count, restored.seats_per_table,
            restored.show_seating) == ([], 1, 9, False)
