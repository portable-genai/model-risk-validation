"""The validation path opens ONE span, and that span carries no content.

A trace backend is not the WORM audit trail. It has no redaction stage, no retention policy
written against a regulator's requirement, and a far wider read audience than the audit store.
So the value of tracing the validation path depends entirely on the span carrying structural
attributes only: which action, whose, which model class. A model id, a model name, a finding's
wording or a planted identifier reaching a span has left the boundary the service's ``redact``
call exists to hold, and it has left it silently.

The content case drives the request whose model record carries a planted NRIC in its name, so
the check runs against input that would actually leak if any attribute were content-shaped.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest

from model_risk_validation.config import build_container
from model_risk_validation.domain.models import ValidationRequest
from model_risk_validation.domain.validation_service import ValidationService

from tests.conftest import local_settings
from tests.fixtures import sample_cases

#: The complete set of attribute keys a validation span may carry. Adding to this is a decision
#: about what leaves the trust boundary, so it is made here rather than at the call site.
_ALLOWED_KEYS = {"action", "actor", "model_class"}


class _RecordingTracer:
    """Captures every span name and attribute so the test can inspect what was emitted."""

    def __init__(self) -> None:
        self.spans: list[tuple[str, dict[str, str]]] = []

    @contextmanager
    def span(self, name: str, **attributes: str) -> Iterator[None]:
        self.spans.append((name, dict(attributes)))
        yield

    def record_token_usage(self, usage: object, model: str) -> None:
        return None


def _validate(request: ValidationRequest) -> _RecordingTracer:
    """The REAL local audit adapter from the container, with only the tracer recorded."""
    container = build_container(local_settings())
    tracer = _RecordingTracer()
    service = ValidationService(container.audit, tracer=tracer)  # type: ignore[arg-type]
    service.validate(request, actor=sample_cases.ACTOR)
    return tracer


def _emitted(tracer: _RecordingTracer) -> str:
    """Every attribute KEY and VALUE that was emitted, as one searchable blob."""
    parts: list[str] = []
    for name, attributes in tracer.spans:
        parts.append(name)
        parts.extend(attributes)
        parts.extend(attributes.values())
    return " ".join(parts)


def test_validating_a_model_opens_exactly_one_named_span() -> None:
    tracer = _validate(sample_cases.ROUTINE_REQUEST)
    assert [name for name, _ in tracer.spans] == ["mrm.validate"]


def test_the_span_carries_the_structural_attributes_an_operator_needs() -> None:
    """Enough to answer "whose validation is slow, on which model class", and nothing more."""
    _, attributes = _validate(sample_cases.ROUTINE_REQUEST).spans[0]
    assert attributes["action"] == "validate"
    assert attributes["actor"] == sample_cases.ACTOR
    assert attributes["model_class"] == sample_cases.ROUTINE_RECORD.model_class.value


@pytest.mark.parametrize(
    "request_",
    [sample_cases.ROUTINE_REQUEST, sample_cases.ESCALATING_REQUEST, sample_cases.PII_REQUEST],
    ids=["routine", "escalating", "pii"],
)
def test_the_attribute_set_is_a_fixed_allowlist_whatever_the_verdict(
    request_: ValidationRequest,
) -> None:
    """An escalating run must not start attaching its findings to the span to explain itself."""
    tracer = _validate(request_)
    for _, attributes in tracer.spans:
        assert set(attributes) == _ALLOWED_KEYS, (
            "a new span attribute appeared; confirm it is structural, then widen "
            "_ALLOWED_KEYS here deliberately"
        )


def test_no_span_attribute_carries_model_content_or_the_planted_identifier() -> None:
    """The request used here has an NRIC planted in the model name, so a leak would show."""
    tracer = _validate(sample_cases.PII_REQUEST)
    emitted = _emitted(tracer)

    forbidden = [
        sample_cases.PLANTED_NRIC,
        sample_cases.PII_RECORD.model_id,
        sample_cases.PII_RECORD.name,
        "ops@gamma.example",
    ]
    for literal in forbidden:
        assert literal, "an empty needle would pass this test for the wrong reason"
        assert literal.lower() not in emitted.lower(), f"a span attribute carried {literal!r}"


def test_every_emitted_attribute_value_is_a_string_the_port_declares() -> None:
    """``span(name, **attributes: str)``: a non-string would serialise however the SDK felt."""
    tracer = _validate(sample_cases.ESCALATING_REQUEST)
    values: list[Any] = [v for _, attributes in tracer.spans for v in attributes.values()]
    assert values
    assert all(isinstance(value, str) for value in values)
