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
