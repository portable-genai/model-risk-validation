"""LLM drafting surfaces under a strict grounding contract (slice 5).

The model NARRATES; it never computes. This module builds the prompt facts from the
deterministic :class:`~.models.ValidationOutcome` and validates whatever the model returns
against those facts, DISCARDING any draft that introduces a figure the engine did not produce.
Restating a verdict is allowed; inventing or altering a number is not, and the check is
deterministic: every numeric token in the draft must appear in the engine's own figures, else
the draft is rejected and the caller escalates rather than shipping an ungrounded document.

Kept pure: no model client here. The drafter PORT calls the model, redacts its inputs through
``pii-kit`` first, and hands the raw text to :func:`validate_draft`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import ValidationOutcome

#: The drafting surfaces this vertical produces, keyed for the schema check.
DRAFT_SECTIONS: tuple[str, ...] = (
    "development_documentation",
    "validation_report",
    "monitoring_writeup",
    "breach_narration",
)

_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


class DraftValidationError(ValueError):
    """A draft that is malformed or introduces an ungrounded figure. Discard, do not ship."""


@dataclass(frozen=True, slots=True)
class DraftDocument:
    """A model-authored, schema-validated, fully-grounded set of drafting sections."""

    subject: str
    sections: dict[str, str]


def allowed_figures(outcome: ValidationOutcome) -> frozenset[str]:
    """Every numeric token the engine produced, as strings, that a draft may mention.

    The draft may restate any of these and no others. The set is deliberately the engine's own
    figures (tier score, each battery statistic and bar, each breach value), so a model that
    rounds differently or invents a number is caught.
    """
    figures: set[str] = {str(outcome.tier_assessment.score)}
    for outcome_test in outcome.battery.outcomes:
        figures.add(_norm(outcome_test.value))
        figures.add(_norm(outcome_test.bar))
    for breach in outcome.monitoring.breaches:
        figures.add(_norm(breach.value))
    return frozenset(figures)


def build_prompt_facts(outcome: ValidationOutcome) -> dict[str, object]:
    """The structured facts handed to the model. It narrates THESE and adds no numbers."""
    return {
        "model_id": outcome.subject,
        "tier": outcome.tier.value,
        "tier_score": outcome.tier_assessment.score,
        "battery": [
            {"metric": o.metric, "value": o.value, "bar": o.bar, "passed": o.passed}
            for o in outcome.battery.outcomes
        ],
        "breaches": [
            {"metric": b.metric, "value": b.value, "level": b.level}
            for b in outcome.monitoring.breaches
        ],
        "findings": [f.summary for f in outcome.findings],
        "sections_required": list(DRAFT_SECTIONS),
    }


def validate_draft(raw_sections: dict[str, str], outcome: ValidationOutcome) -> DraftDocument:
    """Validate model output: every required section present, non-empty, and fully grounded.

    Raises :class:`DraftValidationError` on any violation. The caller discards the draft and
    escalates; an ungrounded narrative never reaches a user or the audit record.
    """
    missing = [s for s in DRAFT_SECTIONS if s not in raw_sections]
    if missing:
        raise DraftValidationError(f"draft is missing required sections: {missing}")
    allowed = allowed_figures(outcome)
    clean: dict[str, str] = {}
    for section in DRAFT_SECTIONS:
        text = raw_sections[section].strip()
        if not text:
            raise DraftValidationError(f"section {section!r} is empty")
        ungrounded = [tok for tok in _NUMBER.findall(text) if _norm(tok) not in allowed]
        if ungrounded:
            raise DraftValidationError(
                f"section {section!r} cites figures the engine did not produce: {ungrounded}"
            )
        clean[section] = text
    return DraftDocument(subject=outcome.subject, sections=clean)


def _norm(value: object) -> str:
    """Normalise a number to a canonical string so 0.70 and 0.7 compare equal."""
    text = str(value)
    match = _NUMBER.fullmatch(text)
    if match is None:
        return text
    number = float(text)
    if number == int(number):
        return str(int(number))
    return repr(round(number, 6)).rstrip("0").rstrip(".")
