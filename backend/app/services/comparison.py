"""Compare a measure on nights with an item against nights without it.

Confidence comes from a permutation test: how rarely a gap this big turns up
when the same nights are shuffled at random.
"""

import random
import statistics
from dataclasses import dataclass

MIN_NIGHTS = 5
STRONG_MIN_NIGHTS = 8
CONFIDENCE_ORDER = {"strong": 0, "some": 1, "weak": 2}


@dataclass
class Comparison:
    with_n: int
    without_n: int
    with_mean: float | None
    without_mean: float | None
    effect: float | None
    p_value: float | None
    confidence: str


def _permutation_p(with_values: list[float], without_values: list[float], iterations: int, seed: int) -> float:
    pooled = list(with_values) + list(without_values)
    n_with, n_without = len(with_values), len(without_values)
    total = sum(pooled)

    def gap(with_sum: float) -> float:
        return abs(with_sum / n_with - (total - with_sum) / n_without)

    observed = gap(sum(with_values))
    rng = random.Random(seed)
    as_extreme = 0
    for _ in range(iterations):
        if gap(sum(rng.sample(pooled, n_with))) >= observed - 1e-9:
            as_extreme += 1
    return (as_extreme + 1) / (iterations + 1)


def compare(
    with_values: list[float], without_values: list[float], *, iterations: int = 2000, seed: int = 0
) -> Comparison:
    with_n, without_n = len(with_values), len(without_values)
    if with_n < MIN_NIGHTS or without_n < MIN_NIGHTS:
        return Comparison(with_n, without_n, None, None, None, None, "too_early")

    with_mean = statistics.fmean(with_values)
    without_mean = statistics.fmean(without_values)
    p_value = _permutation_p(with_values, without_values, iterations, seed)

    confidence = level_for(p_value, with_n, without_n)
    return Comparison(with_n, without_n, with_mean, without_mean, with_mean - without_mean, p_value, confidence)


def level_for(p_value: float, with_n: int, without_n: int) -> str:
    if p_value < 0.05 and min(with_n, without_n) >= STRONG_MIN_NIGHTS:
        return "strong"
    if p_value < 0.20:
        return "some"
    return "weak"


def bh_adjust(p_values: list[float]) -> list[float]:
    """Benjamini-Hochberg adjustment, so testing many items at once doesn't manufacture findings."""
    m = len(p_values)
    order = sorted(range(m), key=lambda i: p_values[i])
    adjusted = [0.0] * m
    running_min = 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        running_min = min(running_min, p_values[i] * m / rank)
        adjusted[i] = running_min
    return adjusted


def is_negligible(effect: float, all_values: list[float]) -> bool:
    if len(all_values) < 2:
        return True
    spread = statistics.pstdev(all_values)
    if spread == 0:
        return True
    return abs(effect) < 0.2 * spread
