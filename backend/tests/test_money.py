from decimal import Decimal

from app.engine import (
    compute_average_stack,
    compute_chips_in_play,
    compute_payouts,
    compute_prize_pool,
)


def test_prize_pool_is_entries_times_buy_in():
    assert compute_prize_pool(9, Decimal("20")) == Decimal("180")


def test_prize_pool_with_decimal_buy_in():
    assert compute_prize_pool(3, Decimal("12.50")) == Decimal("37.50")


def test_payouts_are_exact_no_rounding():
    payouts = compute_payouts(Decimal("225"), [50, 30, 20])
    assert payouts == [Decimal("112.5"), Decimal("67.5"), Decimal("45")]


def test_payouts_sum_to_pool_exactly():
    pool = Decimal("220")
    assert sum(compute_payouts(pool, [50, 30, 20])) == pool


def test_chips_in_play_includes_early_bird_bonus():
    assert compute_chips_in_play(9, 10000, 5, 1000) == 95000


def test_average_stack_rounds_to_nearest_chip():
    assert compute_average_stack(95000, 7) == 13571


def test_average_stack_is_none_with_no_players():
    assert compute_average_stack(95000, 0) is None
