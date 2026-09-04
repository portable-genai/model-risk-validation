"""The deterministic validation service: compose the engines into one consequential result.

The consequential outputs (the tier, every battery verdict, every breach and whether the run
escalates) are pure stdlib and replayable; an LLM would only narrate them, never produce them. PII
is redacted BEFORE anything is written to the audit sink (R1 / P-04), every result carries
citations, and a consequential result sets ``requires_human_review`` and is ROUTED to
human-review-console by the caller (rule R8) rather than auto-executing.

Escalation is the default, not the exception: a run escalates when it lands at the highest
materiality tier, when any required validation test failed or could not run, or when monitoring
shows any breach. A run that cannot be fully evaluated escalates rather than passing quietly.
"""

from __future__ import annotations

from pii_kit import redact

from ..ports.audit import AuditSinkPort
from ..ports.observability import ObservabilityTracerPort
from .battery.runner import BatteryReport, BatteryRunner
from .kernel import AuditEvent, Citation, Decision, Finding, Severity, utcnow, worst_severity
from .models import ValidationOutcome, ValidationRequest
from .monitoring import MonitoringEngine, MonitoringReport
from .pii import PII_PATTERNS
from .taxonomy import Tier
from .tiering import TierAssessment, TieringEngine

#: One span per validated model. Structural attributes only: see :meth:`ValidationService.validate`.
_VALIDATE_SPAN = "mrm.validate"


class ValidationService:
    """Run tiering, the battery and monitoring for one model and record a redacted audit event."""

    def __init__(self, audit: AuditSinkPort, *, tracer: ObservabilityTracerPort) -> None:
        self._audit = audit
        # REQUIRED, and deliberately not an optional with a no-op default. A default would let a
        # new surface construct a service that emits nothing, and the deployment would look
        # traced because the exporter was bound. A surface that forgets the tracer fails to
        # construct instead, which is a failure somebody sees.
        self._tracer = tracer
        self._tiering = TieringEngine()
        self._battery = BatteryRunner()
        self._monitoring = MonitoringEngine()

    def validate(self, request: ValidationRequest, *, actor: str) -> ValidationOutcome:
        """Validate one model end to end and record the already-redacted audit event.

        The whole path runs inside one span, and its attributes are STRUCTURAL only: the
        action, the actor and the model class, an enum. Never the model id, never the model
        name, never a finding's wording or a battery figure. A trace backend is not the WORM
        audit trail: it has no redaction stage, a wider read audience and no retention rule
        written against a regulator's requirement, so anything content-shaped that reaches a
        span has left the boundary the ``redact`` call below exists to hold, and it has left
        it silently.
        """
        with self._tracer.span(
            _VALIDATE_SPAN,
            action="validate",
            actor=actor,
            model_class=request.record.model_class.value,
        ):
            record = request.record
            tier_assessment = self._tiering.assess(record)
            battery = self._battery.run(record.model_id, record.model_class, request.sample)
            monitoring = self._monitoring.evaluate(
                record.model_id, tier_assessment.tier, request.observed
            )

            findings = self._findings(tier_assessment, battery, monitoring)
            severity = self._severity(tier_assessment.tier, findings, monitoring)
            escalate = self._escalates(tier_assessment.tier, battery, monitoring, severity)
            decision = Decision.ESCALATED if escalate else Decision.ALLOWED
            citations = self._citations(record.citation(), findings)
            summary = self._summary(record.name, tier_assessment.tier, battery, monitoring)

            self._audit.record(
                AuditEvent(
                    action="validate",
                    actor=actor,
                    decision=decision,
                    severity=severity,
                    redacted_summary=redact(
                        f"{record.model_id} {record.name}: {summary}", PII_PATTERNS
                    ),
                    citations=citations,
                    timestamp=utcnow(),
                )
            )

            return ValidationOutcome(
                subject=record.model_id,
                model_name=record.name,
                tier=tier_assessment.tier,
                severity=severity,
                decision=decision,
                summary=summary,
                requires_human_review=escalate,
                tier_assessment=tier_assessment,
                battery=battery,
                monitoring=monitoring,
                findings=findings,
                citations=citations,
            )

    @staticmethod
    def _findings(
        tier: TierAssessment, battery: BatteryReport, monitoring: MonitoringReport
    ) -> tuple[Finding, ...]:
        merged = (*tier.findings, *battery.findings, *monitoring.findings)
        return tuple(sorted(merged, key=lambda f: f.sort_key))

    @staticmethod
    def _severity(
        tier: Tier, findings: tuple[Finding, ...], monitoring: MonitoringReport
    ) -> Severity:
        finding_severities = tuple(f.severity for f in findings)
        return worst_severity((*finding_severities, monitoring.severity))

    @staticmethod
    def _escalates(
        tier: Tier, battery: BatteryReport, monitoring: MonitoringReport, severity: Severity
    ) -> bool:
        return (
            tier is Tier.TIER_1
            or not battery.passed
            or monitoring.escalates
            or severity in (Severity.HIGH, Severity.CRITICAL)
        )

    @staticmethod
    def _summary(
        model_name: str, tier: Tier, battery: BatteryReport, monitoring: MonitoringReport
    ) -> str:
        fails = len(battery.failed)
        battery_state = "battery clear" if battery.passed else f"{fails} battery failure(s)"
        breach_state = (
            f"{sum(1 for b in monitoring.breaches if b.level != 'clear')} breach(es)"
            if monitoring.has_breach
            else "no breach"
        )
        gap = " with gaps" if battery.has_gap else ""
        return f"tier {tier.value}, {battery_state}{gap}, {breach_state}"

    @staticmethod
    def _citations(base: Citation, findings: tuple[Finding, ...]) -> tuple[Citation, ...]:
        seen: dict[str, Citation] = {base.source_id: base}
        for finding in findings:
            for citation in finding.citations:
                seen.setdefault(citation.source_id, citation)
        return tuple(seen.values())
