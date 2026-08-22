"""Canonical synthetic models, shared by the unit and contract suites.

Every party is obviously fictional and every identifier is a synthetic literal. One canonical
escalating model and one canonical routine model are enough for the contract suite: parity means
the SAME request through every implementation, so the request has one home rather than being
retyped per test.
"""

from __future__ import annotations

from model_risk_validation.adapters.local.audit import LocalAuditAdapter
from model_risk_validation.adapters.local.tracer import LocalNoopTracerAdapter
from model_risk_validation.config import Settings
from model_risk_validation.domain.battery.runner import BatterySample
from model_risk_validation.domain.inventory import InventoryRecord
from model_risk_validation.domain.models import ValidationOutcome, ValidationRequest
from model_risk_validation.domain.taxonomy import ModelClass
from model_risk_validation.domain.validation_service import ValidationService

#: The verified principal the tests attribute work to (never a client-asserted actor).
ACTOR = "analyst@bank.example"

#: A tenant partition, so the outbound-review assertions are not all on the empty string.
TENANT = "demo-bank"

#: A planted identifier, so a redaction assertion has an independent literal to look for
#: rather than trusting the pattern pack to agree with itself.
PLANTED_NRIC = "S1234567D"

#: A planted address, so the universal rows have an independent literal of their own.
PLANTED_EMAIL = "kai.tan@delta.example"

#: A model that MUST escalate: an IRB (regulatory-capital) class floors at tier_1, and with no
#: validation samples every required battery test is a gap, so rule R8 routing applies.
ESCALATING_RECORD = InventoryRecord(
    model_id="M-IRB-001",
    name="Acme IRB PD model (FICTIONAL)",
    model_class=ModelClass.IRB,
    owner="model.owner@bank.example",
)

ESCALATING_REQUEST = ValidationRequest(record=ESCALATING_RECORD)

#: A model that must NOT escalate: a low-materiality pricing model, tier_3, with a passing
#: battery and a clear monitoring reading. A router that manufactured a review here would lie.
ROUTINE_RECORD = InventoryRecord(
    model_id="M-PRC-014",
    name="Beta options pricing model (FICTIONAL)",
    model_class=ModelClass.PRICING,
    owner="model.owner@bank.example",
    dimensions={
        "materiality": "low",
        "complexity": "low",
        "usage": "low",
        "regulatory_exposure": "low",
    },
)

ROUTINE_REQUEST = ValidationRequest(
    record=ROUTINE_RECORD,
    sample=BatterySample(
        predicted=(0.02, 0.02, 0.98, 0.98),
        outcomes=(0, 0, 1, 1),
        exceptions=(0, 0, 0, 0, 0),
    ),
    observed={"psi": 0.05},
)

#: An escalating model that also carries personal data in its record, for the redaction proofs.
PII_RECORD = InventoryRecord(
    model_id="M-IRB-009",
    name=f"Gamma IRB model (FICTIONAL), owner NRIC {PLANTED_NRIC}, mail ops@gamma.example",
    model_class=ModelClass.IRB,
    owner="model.owner@bank.example",
)

PII_REQUEST = ValidationRequest(record=PII_RECORD)

#: The same, with the identifier in the MODEL ID as well. Every citation LOCATOR and TITLE this
#: vertical builds embeds the client-supplied model id (``inventory:<id>``, ``battery:<id>:<t>``,
#: ``Inventory record <id>``), and ``domain.inventory`` builds a locator straight from a legacy
#: document's ``source_ref``, so a redactor that masks only the summary writes the identifier
#: back into the WORM record from a field nobody was looking at.
PII_LOCATOR_RECORD = InventoryRecord(
    model_id=f"M-IRB-{PLANTED_NRIC}",
    name=f"Delta IRB model (FICTIONAL), contact {PLANTED_EMAIL}",
    model_class=ModelClass.IRB,
    owner=PLANTED_EMAIL,
)

PII_LOCATOR_REQUEST = ValidationRequest(record=PII_LOCATOR_RECORD)


def outcome_for(request: ValidationRequest, *, actor: str = ACTOR) -> ValidationOutcome:
    """Run the deterministic service on an in-memory audit sink and return the outcome."""
    settings = Settings(profile="local", audit_path=":memory:")
    audit = LocalAuditAdapter(settings)
    return ValidationService(audit, tracer=LocalNoopTracerAdapter(settings)).validate(
        request, actor=actor
    )


def escalating_outcome() -> ValidationOutcome:
    """The canonical escalated ValidationOutcome (rule R8's payload)."""
    return outcome_for(ESCALATING_REQUEST)
