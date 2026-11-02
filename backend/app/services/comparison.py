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
    observed = abs(statistics.fmean(with_values) - statistics.fmean(without_values))
    pooled = list(with_values) + list(without_values)
    n_with = len(with_values)
    rng = random.Random(seed)
    as_extreme = 0
    for _ in range(iterations):
        rng.shuffle(pooled)
        gap = abs(statistics.fmean(pooled[:n_with]) - statistics.fmean(pooled[n_with:]))
        if gap >= observed - 1e-12:
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

    if p_value < 0.05 and min(with_n, without_n) >= STRONG_MIN_NIGHTS:
        confidence = "strong"
    elif p_value < 0.20:
        confidence = "some"
    else:
        confidence = "weak"

    return Comparison(with_n, without_n, with_mean, without_mean, with_mean - without_mean, p_value, confidence)


def is_negligible(effect: float, all_values: list[float]) -> bool:
    if len(all_values) < 2:
        return True
    spread = statistics.pstdev(all_values)
    if spread == 0:
        return True
    return abs(effect) < 0.2 * spread
