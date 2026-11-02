"""Comparing nights with an item against nights without it."""

import pytest

from app.services.comparison import compare, is_negligible

LOW = [58, 60, 61, 59, 62, 60, 57, 61, 60, 59]
HIGH = [74, 76, 75, 73, 77, 75, 74, 76, 75, 77]


def test_too_early_below_five():
    result = compare([60, 61, 62, 63], HIGH * 2)
    assert result.confidence == "too_early"
    assert result.effect is None
    assert result.with_n == 4


def test_clear_difference_is_strong():
    result = compare(LOW, HIGH)
    assert result.confidence == "strong"
    assert result.effect == pytest.approx(59.7 - 75.2, abs=0.01)


def test_no_difference_is_weak():
    result = compare(LOW, list(reversed(LOW)))
    assert result.confidence == "weak"


def test_deterministic():
    assert compare(LOW[:6], LOW[4:]).p_value == compare(LOW[:6], LOW[4:]).p_value


def test_negligible():
    assert is_negligible(0.5, [60, 70, 80, 90]) is True
    assert is_negligible(10, [60, 70, 80, 90]) is False
    assert is_negligible(1, [70, 70, 70]) is True
