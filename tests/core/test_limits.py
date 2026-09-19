"""Tests for the rate limit helpers."""

import pytest

from apps.core.limits import LimitState, user_text_limit


def test_remaining_counts_down() -> None:
    state = LimitState(limit=5, used=2, seconds_left=600)

    assert state.remaining == 3


def test_remaining_never_goes_below_zero() -> None:
    """Past the limit the count keeps growing, but "-2 left" tells nobody anything."""
    state = LimitState(limit=5, used=8, seconds_left=600)

    assert state.remaining == 0


@pytest.mark.parametrize(
    ("seconds", "minutes"),
    [(600, 10), (61, 2), (1, 1), (0, 1)],
)
def test_minutes_left_rounds_up_and_stops_at_one(seconds: int, minutes: int) -> None:
    """«Через 0 минут» читается как ошибка, даже когда формально верно."""
    assert LimitState(limit=5, used=1, seconds_left=seconds).minutes_left == minutes


def test_user_limit_is_read_from_settings() -> None:
    assert user_text_limit() == 30
