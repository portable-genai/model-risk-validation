"""Vertical artifact models: the request and the consequential result this service produces.

A fork building a different vertical rewrites this module and keeps ``kernel.py`` untouched. The
service's own name is deliberately not substituted into this docstring: a rendered line whose
length depends on ``friendly_name`` would fail the repo's own format check for no reason but the
length of its name.

:class:`ValidationOutcome` is the consequential result the whole spine carries: the API returns it,
the CLI prints it, the agent tool wraps it, and rule R8 routes it to human-review-console when it
escalates. It composes the per-engine reports (tier, battery, monitoring) and exposes the flat
fields the review payload and the API schema read.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .battery.runner import BatteryReport, BatterySample
from .inventory import InventoryRecord
from .kernel import Citation, Decision, Finding, Severity
from .monitoring import MonitoringReport
from .taxonomy import Tier
from .tiering import TierAssessment


@dataclass(frozen=True, slots=True)
class ValidationRequest:
    """One model validation run: the inventory record plus the samples the battery scores.

    ``sample`` carries whatever validation data is available; the battery reports a gap for any
    required test whose input is absent. ``observed`` is the latest monitoring metric values.
    """

    record: InventoryRecord
    sample: BatterySample = field(default_factory=BatterySample)
    observed: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ValidationOutcome:
    """The consequential result of a validation run (the payload rule R8 routes).

    ``subject`` is the flat identifier the shared review payload and API schema read; here it is
    the model's inventory id. ``severity``, ``decision`` and ``requires_human_review`` are the
    composed verdict, and ``findings`` is the severity-ranked union across every engine.
    """

    subject: str
    model_name: str
    tier: Tier
    severity: Severity
    decision: Decision
    summary: str
    requires_human_review: bool
    tier_assessment: TierAssessment
    battery: BatteryReport
    monitoring: MonitoringReport
    findings: tuple[Finding, ...] = ()
    citations: tuple[Citation, ...] = ()
