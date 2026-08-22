"""The LLM drafting grounding contract: a draft may restate engine figures and no others."""

from __future__ import annotations

import pytest

from model_risk_validation.adapters.local.audit import LocalAuditAdapter
from model_risk_validation.adapters.local.tracer import LocalNoopTracerAdapter
from model_risk_validation.config import Settings
from model_risk_validation.domain.battery.runner import BatterySample
from model_risk_validation.domain.inventory import InventoryRecord
from model_risk_validation.domain.models import ValidationRequest
from model_risk_validation.domain.prompts import (
    DRAFT_SECTIONS,
    DraftValidationError,
    validate_draft,
)
from model_risk_validation.domain.taxonomy import ModelClass
from model_risk_validation.domain.validation_service import ValidationService


def _outcome():
    settings = Settings(profile="local", audit_path=":memory:")
    audit = LocalAuditAdapter(settings)
    request = ValidationRequest(
        record=InventoryRecord(
            model_id="M-IRB-001",
            name="Acme IRB (FICTIONAL)",
            model_class=ModelClass.IRB,
            owner="owner@bank.example",
        ),
        sample=BatterySample(
            scores=(0.1, 0.4, 0.35, 0.8),
            labels=(0, 0, 1, 1),
            predicted=(0.1, 0.2, 0.7, 0.9),
            outcomes=(0, 0, 1, 1),
            exceptions=(0, 0, 0, 0),
        ),
    )
    return ValidationService(audit, tracer=LocalNoopTracerAdapter(settings)).validate(
        request, actor="a"
    )


def _sections(text: str) -> dict[str, str]:
    return {section: text for section in DRAFT_SECTIONS}


def test_a_draft_that_only_restates_engine_figures_is_accepted() -> None:
    outcome = _outcome()
    score = outcome.tier_assessment.score
    draft = validate_draft(_sections(f"The tiering score is {score}."), outcome)
    assert set(draft.sections) == set(DRAFT_SECTIONS)


def test_a_draft_that_invents_a_figure_is_discarded() -> None:
    outcome = _outcome()
    with pytest.raises(DraftValidationError, match="figures"):
        validate_draft(_sections("The AUC came out at 0.999 this quarter."), outcome)


def test_a_draft_missing_a_required_section_is_discarded() -> None:
    outcome = _outcome()
    with pytest.raises(DraftValidationError, match="missing"):
        validate_draft({"validation_report": "text"}, outcome)


def test_an_empty_section_is_discarded() -> None:
    outcome = _outcome()
    sections = _sections("text")
    sections["breach_narration"] = "   "
    with pytest.raises(DraftValidationError, match="empty"):
        validate_draft(sections, outcome)
