"""Pure-stdlib validation statistics: the authoritative math for the battery (slice 3).

No numpy, no scipy, no cloud. Every function is deterministic and total on its documented
domain, and raises :class:`StatInputError` on an input it cannot honestly score rather than
returning a plausible number, because a fabricated statistic is worse than a named gap. The
committed reference values in ``tests/unit/test_battery_stats.py`` pin each of these to a figure
computed independently, and each is proved able to move off that figure.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


class StatInputError(ValueError):
    """An input a statistic cannot be computed over (empty, single-class, mismatched length)."""


def _check_pairs(scores: Sequence[float], labels: Sequence[int]) -> None:
    if len(scores) != len(labels):
        raise StatInputError("scores and labels must have equal length")
    if not scores:
        raise StatInputError("cannot score an empty sample")
    if any(label not in (0, 1) for label in labels):
        raise StatInputError("labels must be binary 0/1")


def auc(scores: Sequence[float], labels: Sequence[int]) -> float:
    """Area under the ROC curve via the rank-sum (Mann-Whitney U) identity, ties averaged.

    ``scores`` are model outputs (higher means more likely positive); ``labels`` are 0/1. Both
    classes must be present, else the ROC is undefined and this raises rather than guessing 0.5.
    """
    _check_pairs(scores, labels)
    n_pos = sum(labels)
    n_neg = len(labels) - n_pos
    if n_pos == 0 or n_neg == 0:
        raise StatInputError("AUC needs at least one positive and one negative label")
    order = sorted(range(len(scores)), key=lambda i: scores[i])
    ranks = [0.0] * len(scores)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and scores[order[j + 1]] == scores[order[i]]:
            j += 1
        average_rank = (i + j) / 2.0 + 1.0  # ranks are 1-based
        for k in range(i, j + 1):
            ranks[order[k]] = average_rank
        i = j + 1
    rank_sum_pos = sum(ranks[i] for i in range(len(labels)) if labels[i] == 1)
    return (rank_sum_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def gini(scores: Sequence[float], labels: Sequence[int]) -> float:
    """The Gini coefficient, ``2 * AUC - 1`` (the accuracy-ratio form used in credit risk)."""
    return 2.0 * auc(scores, labels) - 1.0


def calibration_error(
    predicted: Sequence[float], outcomes: Sequence[int], *, bins: int = 5
) -> float:
    """Maximum absolute gap between mean predicted probability and observed rate, per bin.

    Equal-width bins over [0, 1]; empty bins are skipped. This is a deterministic worst-bin
    calibration error: 0.0 is perfect calibration, larger is worse.
    """
    _check_pairs(predicted, outcomes)
    if bins < 1:
        raise StatInputError("bins must be a positive integer")
    if any(p < 0.0 or p > 1.0 for p in predicted):
        raise StatInputError("predicted probabilities must lie in [0, 1]")
    sums: list[float] = [0.0] * bins
    counts: list[int] = [0] * bins
    hits: list[int] = [0] * bins
    for p, o in zip(predicted, outcomes, strict=True):
        idx = min(int(p * bins), bins - 1)
        sums[idx] += p
        counts[idx] += 1
        hits[idx] += o
    worst = 0.0
    for b in range(bins):
        if counts[b] == 0:
            continue
        worst = max(worst, abs(sums[b] / counts[b] - hits[b] / counts[b]))
    return worst


def psi(expected: Sequence[float], actual: Sequence[float], *, floor: float = 1e-4) -> float:
    """Population Stability Index between two bucketed distributions.

    ``expected`` and ``actual`` are per-bucket counts or proportions over the SAME buckets. Each
    is normalised to proportions; a zero proportion is floored to ``floor`` so the logarithm is
    finite (the standard practitioner guard). PSI is non-negative; higher means more shift.
    """
    if len(expected) != len(actual):
        raise StatInputError("expected and actual must share the same buckets")
    if not expected:
        raise StatInputError("cannot compute PSI over zero buckets")
    if any(v < 0 for v in expected) or any(v < 0 for v in actual):
        raise StatInputError("bucket weights must be non-negative")
    e_total = sum(expected)
    a_total = sum(actual)
    if e_total <= 0 or a_total <= 0:
        raise StatInputError("each distribution must have positive total mass")
    total = 0.0
    for e, a in zip(expected, actual, strict=True):
        e_prop = max(e / e_total, floor)
        a_prop = max(a / a_total, floor)
        total += (a_prop - e_prop) * math.log(a_prop / e_prop)
    return total


def exception_rate(exceptions: Sequence[int]) -> float:
    """Backtesting exception rate: the fraction of observations that breached (a 0/1 series)."""
    if not exceptions:
        raise StatInputError("cannot compute an exception rate over zero observations")
    if any(e not in (0, 1) for e in exceptions):
        raise StatInputError("exceptions must be a 0/1 series")
    return sum(exceptions) / len(exceptions)
