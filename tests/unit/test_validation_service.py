"""The deterministic validation service: composed verdict, escalation, redact-before-audit."""

from __future__ import annotations

from model_risk_validation.adapters.local.audit import (
    LocalAuditAdapter,
)
from model_risk_validation.adapters.local.tracer import (
    LocalNoopTracerAdapter,
)
from model_risk_validation.config import (
    Settings,
)
from model_risk_validation.domain.battery.runner import (
    BatterySample,
)
from model_risk_validation.domain.inventory import (
    InventoryRecord,
)
from model_risk_validation.domain.kernel import (
    Decision,
)
from model_risk_validation.domain.models import (
    ValidationRequest,
)
from model_risk_validation.domain.taxonomy import (
    ModelClass,
    Tier,
)
from model_risk_validation.domain.validation_service import (
    ValidationService,
)


def _service() -> tuple[ValidationService, LocalAuditAdapter]:
    settings = Settings(profile="local", audit_path=":memory:")
    audit = LocalAuditAdapter(settings)
    return ValidationService(audit, tracer=LocalNoopTracerAdapter(settings)), audit


def _record(model_class: ModelClass, **dims: str) -> InventoryRecord:
    return InventoryRecord(
        model_id="M-1",
        name="Test model (FICTIONAL)",
        model_class=model_class,
        owner="owner@bank.example",
        dimensions=dims,
    )


def test_a_regulatory_capital_class_floors_at_tier_1_and_escalates() -> None:
    service, _ = _service()
    result = service.validate(ValidationRequest(record=_record(ModelClass.IRB)), actor="a")
    assert result.tier is Tier.TIER_1
    assert result.requires_human_review is True
    assert result.decision is Decision.ESCALATED


def test_a_low_materiality_model_with_a_passing_battery_does_not_escalate() -> None:
    service, _ = _service()
    request = ValidationRequest(
        record=_record(
            ModelClass.PRICING,
            materiality="low",
            complexity="low",
            usage="low",
            regulatory_exposure="low",
        ),
        sample=BatterySample(
            predicted=(0.02, 0.02, 0.98, 0.98),
            outcomes=(0, 0, 1, 1),
            exceptions=(0, 0, 0, 0, 0),
        ),
        observed={"psi": 0.05},
    )
    result = service.validate(request, actor="a")
    assert result.tier is Tier.TIER_3
    assert result.requires_human_review is False
    assert result.decision is Decision.ALLOWED


def test_a_battery_gap_escalates_rather_than_passing_quietly() -> None:
    service, _ = _service()
    # A pricing model at tier_3 but with no calibration/backtesting samples: the required tests
    # are gaps, so the run must escalate rather than reporting a clear battery.
    request = ValidationRequest(
        record=_record(
            ModelClass.PRICING,
            materiality="low",
            complexity="low",
            usage="low",
            regulatory_exposure="low",
        ),
        observed={"psi": 0.05},
    )
    result = service.validate(request, actor="a")
    assert result.tier is Tier.TIER_3
    assert result.battery.has_gap is True
    assert result.requires_human_review is True


def test_the_result_is_deterministic() -> None:
    service, _ = _service()
    request = ValidationRequest(record=_record(ModelClass.IRB))
    first = service.validate(request, actor="a")
    second = service.validate(request, actor="a")
    assert first.tier == second.tier
    assert first.severity == second.severity
    assert [f.id for f in first.findings] == [f.id for f in second.findings]


def test_pii_is_redacted_before_the_audit_write() -> None:
    service, audit = _service()
    record = InventoryRecord(
        model_id="M-9",
        name="Gamma model (FICTIONAL), owner NRIC S1234567D on file",
        model_class=ModelClass.IRB,
        owner="owner@bank.example",
    )
    service.validate(ValidationRequest(record=record), actor="analyst@bank.example")
    records = audit.log.read_all()
    assert records, "an audit event should have been recorded"
    summary = records[-1]["redacted_summary"]
    assert "S1234567D" not in summary
    assert "REDACTED" in summary
    assert records[-1]["actor"] == "analyst@bank.example"
    assert audit.log.verify_chain().ok
