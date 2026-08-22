"""The battery statistics, pinned to independently-computed reference values (slice 3 proof).

Each reference figure was computed by hand (or from a textbook identity), NOT by capturing this
code's output, so the test is an independent oracle rather than a change-detector. Each statistic
is also shown to MOVE with its input, so a constant would not pass.
"""

from __future__ import annotations

import math

import pytest

from model_risk_validation.domain.battery.stats import (
    StatInputError,
    auc,
    calibration_error,
    exception_rate,
    gini,
    psi,
)


def test_auc_matches_the_hand_computed_concordance() -> None:
    # pos scores {0.35, 0.8}, neg scores {0.1, 0.4}; 3 of 4 pairs concordant -> 0.75.
    assert auc([0.1, 0.4, 0.35, 0.8], [0, 0, 1, 1]) == pytest.approx(0.75)


def test_auc_averages_ties() -> None:
    # A tie between a positive and a negative at the same score contributes half.
    assert auc([0.5, 0.5], [0, 1]) == pytest.approx(0.5)


def test_gini_is_two_auc_minus_one() -> None:
    assert gini([0.1, 0.4, 0.35, 0.8], [0, 0, 1, 1]) == pytest.approx(0.5)


def test_calibration_error_is_the_worst_bin_gap() -> None:
    # bins of width 0.2: worst bin gap is |0.6 - 1.0| = 0.4.
    assert calibration_error([0.2, 0.4, 0.6, 0.8], [0, 0, 1, 1]) == pytest.approx(0.4)


def test_psi_matches_the_closed_form() -> None:
    expected = 0.1 * math.log(1.2) + (-0.1) * math.log(0.8)
    assert psi([50, 50], [60, 40]) == pytest.approx(expected)


def test_exception_rate_is_the_breach_fraction() -> None:
    assert exception_rate([0, 0, 1, 0, 0]) == pytest.approx(0.2)


def test_each_statistic_moves_with_its_input() -> None:
    """A constant would pass a single reference check; prove each figure actually varies."""
    assert auc([0.1, 0.2, 0.3, 0.9], [0, 0, 1, 1]) != auc([0.1, 0.4, 0.35, 0.8], [0, 0, 1, 1])
    assert calibration_error([0.5, 0.5], [0, 1]) != calibration_error([0.2, 0.8], [0, 1])
    assert psi([50, 50], [90, 10]) > psi([50, 50], [60, 40])
    assert exception_rate([1, 1, 1]) != exception_rate([0, 0, 0])


def test_statistics_refuse_dishonest_inputs_rather_than_guessing() -> None:
    with pytest.raises(StatInputError):
        auc([0.1, 0.2], [1, 1])  # single class: ROC undefined
    with pytest.raises(StatInputError):
        psi([50, 50], [60])  # mismatched buckets
    with pytest.raises(StatInputError):
        exception_rate([])  # nothing to score
    with pytest.raises(StatInputError):
        calibration_error([1.5], [1])  # probability out of range
