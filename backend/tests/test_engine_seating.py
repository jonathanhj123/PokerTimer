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


# --- players, draw, late joiners --------------------------------------------

def names(n):
    return [f"P{i}" for i in range(n)]


def seeded(**kw):
    s = TournamentState(**kw)
    s.rng = random.Random(1)
    return s


def test_add_player_counts_as_entry():
    s = seeded(entries=2, players_remaining=2)
    s.add_player("  Anna ")
    assert s.players == [{"name": "Anna", "table": None, "seat": None}]
    assert (s.entries, s.players_remaining) == (3, 3)


def test_add_player_rejects_bad_names():
    s = seeded()
    s.add_player("Anna")
    for bad in ["anna ", "", "   ", "x" * 31, 5]:
        with pytest.raises(EngineError):
            s.add_player(bad)
    assert s.entries == 1


def test_remove_player_case_insensitive_and_floored():
    s = seeded()
    s.add_player("Anna")
    s.set_counts(entries=0, players_remaining=0)
    s.remove_player(" ANNA")
    assert s.players == [] and (s.entries, s.players_remaining) == (0, 0)
    with pytest.raises(EngineError):
        s.remove_player("Nobody")


def test_draw_even_and_unique():
    s = seeded()
    for n in names(14):
        s.add_player(n)
    s.draw_seats(2, 9)
    per_table = Counter(p["table"] for p in s.players)
    assert per_table == {1: 7, 2: 7}
    spots = {(p["table"], p["seat"]) for p in s.players}
    assert len(spots) == 14 and all(1 <= seat <= 9 for _, seat in spots)
    assert (s.table_count, s.seats_per_table) == (2, 9)


def test_draw_uneven_differs_by_at_most_one():
    s = seeded()
    for n in names(13):
        s.add_player(n)
    s.draw_seats(3, 9)
    sizes = Counter(p["table"] for p in s.players).values()
    assert max(sizes) - min(sizes) <= 1


def test_draw_rejects_too_many_players_without_mutating():
    s = seeded()
    for n in names(4):
        s.add_player(n)
    s.draw_seats(1, 9)
    before = [dict(p) for p in s.players]
    with pytest.raises(EngineError):
        s.draw_seats(1, 3)                     # 4 players, 3 seats
    assert s.players == before and s.seats_per_table == 9


def test_draw_requires_players():
    with pytest.raises(EngineError):
        seeded().draw_seats(1, 9)


def test_late_joiner_goes_to_shortest_table_nobody_moves():
    s = seeded()
    for n in names(5):
        s.add_player(n)
    s.draw_seats(2, 9)            # 3 + 2
    before = [dict(p) for p in s.players]
    s.add_player("Late")
    assert s.players[:5] == before
    late = s.players[-1]
    assert late["table"] == min(Counter(p["table"] for p in before).items(),
                                key=lambda kv: kv[1])[0]
    assert (late["table"], late["seat"]) not in {(p["table"], p["seat"]) for p in before}


def test_late_joiner_when_full_fails_without_counting():
    s = seeded()
    for n in names(2):
        s.add_player(n)
    s.draw_seats(1, 2)
    with pytest.raises(EngineError, match="No empty seats"):
        s.add_player("Late")
    assert len(s.players) == 2 and s.entries == 2


def test_layout_is_capped():
    s = seeded()
    s.add_player("Anna")
    for bad in [(21, 9), (2, 21)]:
        with pytest.raises(EngineError):
            s.set_seating_config(*bad)
        with pytest.raises(EngineError):
            s.draw_seats(*bad)
    s.draw_seats(20, 20)
    assert (s.table_count, s.seats_per_table) == (20, 20)
