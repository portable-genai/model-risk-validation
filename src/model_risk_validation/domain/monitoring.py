"""Ongoing performance monitoring and breach handling (slice 4).

Deterministic breach classification over the latest observed metric values, against the tier's
:class:`~.packs.MonitoringPack`. Each metric is classified on a severity LADDER (clear, amber, red),
red escalates a further step at TIER_1 (a red breach on a tier-1 model is a critical, dual-control
event), and the case severity is the WORST across metrics. Every breach sets the result to require
human review and is routed to human-review-console under rule R8 by the caller: a breach is a
consequential second-line outcome, never an auto-executed one.

The engine owns the classification. A metric the pack watches but the series does not supply is a
named gap, not a silent clear: monitoring that skips the metric it cannot see is monitoring that
passes everything.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .kernel import Citation, Finding, Severity, worst_severity
from .packs import MonitoringBand, monitoring_pack
from .taxonomy import Tier


class BreachLevel:
    """The three rungs of the ladder, as plain strings on the finding id (not a wire enum)."""

    CLEAR = "clear"
    AMBER = "amber"
    RED = "red"


@dataclass(frozen=True, slots=True)
class MetricBreach:
    """One metric's classification against its band."""

    metric: str
    value: float
    level: str
    severity: Severity


@dataclass(frozen=True, slots=True)
class MonitoringReport:
    """The monitoring outcome for one model at one tier: breaches, gaps and composed severity."""

    model_id: str
    tier: Tier
    breaches: tuple[MetricBreach, ...]
    findings: tuple[Finding, ...]

    @property
    def severity(self) -> Severity:
        return worst_severity(tuple(b.severity for b in self.breaches))

    @property
    def has_breach(self) -> bool:
        return any(b.level != BreachLevel.CLEAR for b in self.breaches)

    @property
    def escalates(self) -> bool:
        """Every breach requires human review; a gap does too (it hides a possible breach)."""
        return self.has_breach or any(f.id.startswith("monitoring:gap:") for f in self.findings)


class MonitoringEngine:
    """Classify the latest metric values into breaches on the tier's bands. Pure."""

    def evaluate(
        self, model_id: str, tier: Tier, observed: Mapping[str, float]
    ) -> MonitoringReport:
        pack = monitoring_pack(tier)
        breaches: list[MetricBreach] = []
        findings: list[Finding] = []
        for band in pack.bands:
            if band.metric not in observed:
                findings.append(
                    Finding(
                        id=f"monitoring:gap:{band.metric}",
                        severity=Severity.MEDIUM,
                        summary=f"No current value for monitored metric {band.metric}",
                        detail="A watched metric with no observation is a gap, not a clear read.",
                        citations=(_series_citation(model_id, band.metric),),
                    )
                )
                continue
            breach = self._classify(model_id, tier, band, observed[band.metric])
            breaches.append(breach)
            if breach.level != BreachLevel.CLEAR:
                findings.append(
                    Finding(
                        id=f"monitoring:breach:{band.metric}:{breach.level}",
                        severity=breach.severity,
                        summary=f"{band.metric} {breach.value}: {breach.level} at {tier.value}",
                        detail=self._detail(band),
                        citations=(_series_citation(model_id, band.metric),),
                    )
                )
        return MonitoringReport(
            model_id=model_id,
            tier=tier,
            breaches=tuple(breaches),
            findings=tuple(sorted(findings, key=lambda f: f.sort_key)),
        )

    @staticmethod
    def _classify(model_id: str, tier: Tier, band: MonitoringBand, value: float) -> MetricBreach:
        red = value >= band.red if band.higher_is_worse else value <= band.red
        amber = value >= band.amber if band.higher_is_worse else value <= band.amber
        if red:
            severity = Severity.CRITICAL if tier is Tier.TIER_1 else Severity.HIGH
            level = BreachLevel.RED
        elif amber:
            severity = Severity.MEDIUM
            level = BreachLevel.AMBER
        else:
            severity = Severity.LOW
            level = BreachLevel.CLEAR
        return MetricBreach(metric=band.metric, value=value, level=level, severity=severity)

    @staticmethod
    def _detail(band: MonitoringBand) -> str:
        direction = "rising" if band.higher_is_worse else "falling"
        return f"{direction} value; amber at {band.amber}, red at {band.red}"


def _series_citation(model_id: str, metric: str) -> Citation:
    return Citation(
        source_id=f"series:{model_id}:{metric}",
        title=f"Performance series {metric}",
        snippet=f"model {model_id}",
    )
