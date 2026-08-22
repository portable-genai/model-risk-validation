"""Rule R8: an escalated result is ROUTED to Hrz7, not left in a per-repo boolean.

This is the standing gate for the failure the rule exists to prevent. A repo can set
``requires_human_review = True``, pass every other test, and still auto-execute in practice
because nothing ever reads the flag. So the assertions here are about the ROUTING, not the flag:
an escalation produces an outbound review, a non-escalation produces none, the payload leaves
redacted, and the on-prem placeholder refuses rather than swallowing the escalation.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from model_risk_validation.adapters.gcp.review_router import (
    CloudReviewRouter,
)
from model_risk_validation.adapters.local.review_router import (
    LocalReviewRouter,
)
from model_risk_validation.adapters.onprem.review_router import (
    OnPremReviewRouter,
)
from model_risk_validation.api.app import (
    app,
)
from model_risk_validation.config import (
    Settings,
    build_container,
)
from model_risk_validation.domain.inventory import (
    InventoryRecord,
)
from model_risk_validation.domain.kernel import (
    Severity,
)
from model_risk_validation.domain.models import (
    ValidationOutcome,
    ValidationRequest,
)
from model_risk_validation.domain.taxonomy import (
    ModelClass,
)
from model_risk_validation.domain.validation_service import (
    ValidationService,
)


def _settings(profile: str = "local") -> Settings:
    return Settings(profile=profile, audit_path=":memory:", tenant="demo-bank")


def _service() -> ValidationService:
    container = build_container(_settings())
    return ValidationService(container.audit, tracer=container.tracer)


def _outcome(*, observed: dict[str, float] | None = None) -> ValidationOutcome:
    record = InventoryRecord(
        model_id="M-IRB-001",
        name="Acme IRB model (FICTIONAL)",
        model_class=ModelClass.IRB,
        owner="owner@bank.example",
    )
    request = ValidationRequest(record=record, observed=observed or {})
    return _service().validate(request, actor="analyst@bank.example")


def test_an_escalated_result_produces_an_outbound_review() -> None:
    router = LocalReviewRouter(_settings())
    ref = router.route(_outcome(), maker="analyst@bank.example")
    assert ref, "routing must return a reference, so the caller can record where it went"
    pending = router.outbox.pending()
    assert len(pending) == 1
    review = pending[0].review
    assert review.maker == "analyst@bank.example"
    assert review.tenant == "demo-bank"
    assert review.source_key, "a durable outbox needs an idempotency key"


def test_a_critical_result_demands_dual_control() -> None:
    router = LocalReviewRouter(_settings())
    # A tier_1 model with a red PSI breach composes to CRITICAL, which demands two approvals.
    outcome = _outcome(observed={"psi": 0.30})
    assert outcome.severity is Severity.CRITICAL
    router.route(outcome, maker="analyst@bank.example")
    assert router.outbox.pending()[0].review.required_approvals == 2


def test_the_payload_is_redacted_before_it_leaves_the_process() -> None:
    """Hrz7 is a shared sink; a raw identifier must never reach the wire."""
    router = LocalReviewRouter(_settings())
    record = InventoryRecord(
        model_id="M-IRB-009",
        name="Gamma IRB model (FICTIONAL), owner NRIC S1234567D on file",
        model_class=ModelClass.IRB,
        owner="owner@bank.example",
    )
    result = _service().validate(ValidationRequest(record=record), actor="analyst@bank.example")
    router.route(result, maker="analyst@bank.example")
    review = router.outbox.pending()[0].review
    wire = repr(review.to_payload())
    assert "S1234567D" not in wire
    assert "REDACTED" in wire


def test_the_managed_router_refuses_when_no_console_is_configured() -> None:
    """An escalation with nowhere to go must fail loudly, not return as if it were reviewed."""
    router = CloudReviewRouter(Settings(profile="gcp", audit_path=":memory:", review_url=""))
    with pytest.raises(RuntimeError, match="R8"):
        router.route(_outcome(), maker="analyst@bank.example")


def test_the_onprem_placeholder_refuses_rather_than_dropping_the_escalation() -> None:
    router = OnPremReviewRouter(_settings("onprem"))
    with pytest.raises(NotImplementedError, match="R8"):
        router.route(_outcome(), maker="analyst@bank.example")


def test_the_api_routes_the_escalation_in_the_same_request() -> None:
    """The serving path, not just the adapter: an escalation must not depend on a later job."""
    client = TestClient(app, client=("127.0.0.1", 50000))
    escalated = client.post(
        "/v1/validate",
        json={
            "model_id": "M-IRB-001",
            "name": "Acme IRB model (FICTIONAL)",
            "model_class": "irb",
            "owner": "owner@bank.example",
        },
        headers={"X-Dev-Persona": "auditor"},
    ).json()
    assert escalated["requires_human_review"] is True
    assert escalated["review_ref"], "an escalation with no routing reference went nowhere"

    routine = client.post(
        "/v1/validate",
        json={
            "model_id": "M-PRC-014",
            "name": "Beta pricing model (FICTIONAL)",
            "model_class": "pricing",
            "owner": "owner@bank.example",
            "dimensions": {
                "materiality": "low",
                "complexity": "low",
                "usage": "low",
                "regulatory_exposure": "low",
            },
            "sample": {
                "predicted": [0.02, 0.02, 0.98, 0.98],
                "outcomes": [0, 0, 1, 1],
                "exceptions": [0, 0, 0, 0, 0],
            },
            "observed": {"psi": 0.05},
        },
        headers={"X-Dev-Persona": "auditor"},
    ).json()
    assert routine["requires_human_review"] is False
    assert routine["review_ref"] == "", "a non-escalation must not manufacture a review"
