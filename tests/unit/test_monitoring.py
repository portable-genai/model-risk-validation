"""The monitoring engine: the amber/red ladder, worst-wins, and gaps that escalate."""

from __future__ import annotations

from model_risk_validation.domain.kernel import Severity
from model_risk_validation.domain.monitoring import BreachLevel, MonitoringEngine
from model_risk_validation.domain.taxonomy import Tier


def _report(tier: Tier, **observed: float):
    return MonitoringEngine().evaluate("M-1", tier, observed)


def test_a_clear_reading_produces_no_breach() -> None:
    report = _report(Tier.TIER_1, psi=0.05, auc=0.80, exception_rate=0.01)
    assert report.has_breach is False
    assert report.severity is Severity.LOW


def test_an_amber_reading_is_a_medium_breach() -> None:
    report = _report(Tier.TIER_1, psi=0.15, auc=0.80, exception_rate=0.01)
    amber = next(b for b in report.breaches if b.metric == "psi")
    assert amber.level == BreachLevel.AMBER
    assert amber.severity is Severity.MEDIUM


def test_a_red_reading_on_a_tier_1_model_is_critical() -> None:
    report = _report(Tier.TIER_1, psi=0.30, auc=0.80, exception_rate=0.01)
    assert report.severity is Severity.CRITICAL


def test_a_red_reading_below_tier_1_is_high_not_critical() -> None:
    report = _report(Tier.TIER_2, psi=0.35, auc=0.80)
    assert report.severity is Severity.HIGH


def test_worst_wins_across_metrics() -> None:
    # psi amber (medium) and auc red (critical at tier_1): the composed severity is the worst.
    report = _report(Tier.TIER_1, psi=0.15, auc=0.60, exception_rate=0.01)
    assert report.severity is Severity.CRITICAL


def test_a_watched_metric_with_no_observation_is_a_gap_that_escalates() -> None:
    report = _report(Tier.TIER_1, psi=0.05)  # auc and exception_rate not supplied
    assert report.escalates is True
    assert any(f.id.startswith("monitoring:gap:") for f in report.findings)
