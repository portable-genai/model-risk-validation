"""The inventory reconciliation engine: adopt, confirm, conflict, and never invent."""

from __future__ import annotations

from model_risk_validation.domain.inventory import (
    CandidateAttribute,
    InventoryEngine,
    InventoryRecord,
)
from model_risk_validation.domain.kernel import Severity
from model_risk_validation.domain.taxonomy import ModelClass


def _record(**dims: str) -> InventoryRecord:
    return InventoryRecord(
        model_id="M-1",
        name="Test (FICTIONAL)",
        model_class=ModelClass.SCORECARD,
        owner="owner@bank.example",
        dimensions=dims,
    )


def test_a_candidate_fills_an_undeclared_dimension_but_flags_it() -> None:
    result = InventoryEngine().reconcile(_record(), (CandidateAttribute("materiality", "high"),))
    assert result.record.dimensions["materiality"] == "high"
    assert any(f.id == "inventory:document_sourced:materiality" for f in result.findings)


def test_a_conflicting_candidate_does_not_overwrite_and_escalates() -> None:
    result = InventoryEngine().reconcile(
        _record(materiality="low"), (CandidateAttribute("materiality", "high"),)
    )
    # The declared value is RETAINED; the engine never lets a document rewrite a declaration.
    assert result.record.dimensions["materiality"] == "low"
    assert result.escalates is True
    assert any(f.severity is Severity.HIGH for f in result.findings)


def test_an_agreeing_candidate_produces_no_finding() -> None:
    result = InventoryEngine().reconcile(
        _record(materiality="high"), (CandidateAttribute("materiality", "high"),)
    )
    assert result.findings == ()


def test_an_unknown_dimension_or_unparseable_value_is_surfaced_not_adopted() -> None:
    result = InventoryEngine().reconcile(
        _record(),
        (CandidateAttribute("made_up", "high"), CandidateAttribute("complexity", "enormous")),
    )
    assert "made_up" not in result.record.dimensions
    assert "complexity" not in result.record.dimensions
    ids = {f.id for f in result.findings}
    assert "inventory:unknown_dimension:made_up" in ids
    assert "inventory:unparseable_candidate:complexity" in ids
