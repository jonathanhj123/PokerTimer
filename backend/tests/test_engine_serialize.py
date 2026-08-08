from decimal import Decimal

import pytest

from app.engine import EngineError, TournamentState
from tests.helpers import brk, level


def configured_state():
    state = TournamentState(
        structure=[level(25, 50), level(50, 100), brk(10), level(75, 150, ante=25)],
        buy_in=Decimal("20"), total_entries=11, players_remaining=7,
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


def test_set_counts_and_validation():
    state = TournamentState()
    state.set_counts(total_entries=9, players_remaining=7, early_bird_count=5)
    assert (state.total_entries, state.players_remaining, state.early_bird_count) == (9, 7, 5)
    with pytest.raises(EngineError):
        state.set_counts(players_remaining=-1)
    with pytest.raises(EngineError):
        state.set_counts(total_entries=True)    # bools are not counts


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
    assert data["computed"]["prize_pool"] == "220"
    assert data["computed"]["payouts"] == ["110", "66", "44"]


def test_to_dict_exact_decimal_payouts():
    state = configured_state()
    state.total_entries = 9                     # pool 180 → 50% = 90; use odd pool
    state.buy_in = Decimal("25")                # pool 225
    payouts = state.to_dict()["computed"]["payouts"]
    assert payouts == ["112.5", "67.5", "45"]


def test_computed_chip_stats():
    computed = configured_state().to_dict()["computed"]
    assert computed["chips_in_play"] == 11 * 10000 + 5 * 1000
    assert computed["average_stack"] == round(115000 / 7)


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
    state.start()
    state.tick()
    restored = TournamentState.from_dict(state.to_dict())
    assert restored.to_dict() == state.to_dict()
    assert restored.buy_in == Decimal("20")     # real Decimal, not str
