"""Tests for the russian plural filter."""

import pytest

from apps.core.templatetags.plural import plural_ru

FORMS = "предложение,предложения,предложений"


@pytest.mark.parametrize(
    ("number", "expected"),
    [
        (1, "предложение"),
        (2, "предложения"),
        (3, "предложения"),
        (4, "предложения"),
        (5, "предложений"),
        (10, "предложений"),
        (21, "предложение"),
        (22, "предложения"),
        (25, "предложений"),
        (101, "предложение"),
        (0, "предложений"),
    ],
)
def test_picks_the_right_form(number: int, expected: str) -> None:
    assert plural_ru(number, FORMS) == expected


@pytest.mark.parametrize("number", [11, 12, 13, 14, 111, 112])
def test_teens_use_the_many_form(number: int) -> None:
    """11-14 are the exception: they end in 1-4 but decline as many."""
    assert plural_ru(number, FORMS) == "предложений"
