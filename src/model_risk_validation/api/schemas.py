"""API request/response schemas (Pydantic) mapped to/from the pure-domain models."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from ..domain.battery.runner import BatterySample
from ..domain.inventory import InventoryRecord
from ..domain.models import ValidationOutcome, ValidationRequest
from ..domain.taxonomy import ModelClass


class SampleModel(BaseModel):
    """Optional validation samples; a metric whose inputs are absent is reported as a gap."""

    scores: list[float] | None = None
    labels: list[int] | None = None
    predicted: list[float] | None = None
    outcomes: list[int] | None = None
    psi_expected: list[float] | None = None
    psi_actual: list[float] | None = None
    exceptions: list[int] | None = None

    def to_domain(self) -> BatterySample:
        def _floats(seq: Sequence[float] | None) -> tuple[float, ...] | None:
            return tuple(float(v) for v in seq) if seq is not None else None

        def _ints(seq: Sequence[int] | None) -> tuple[int, ...] | None:
            return tuple(int(v) for v in seq) if seq is not None else None

        return BatterySample(
            scores=_floats(self.scores),
            labels=_ints(self.labels),
            predicted=_floats(self.predicted),
            outcomes=_ints(self.outcomes),
            psi_expected=_floats(self.psi_expected),
            psi_actual=_floats(self.psi_actual),
            exceptions=_ints(self.exceptions),
        )


class ValidationRequestModel(BaseModel):
    """A model validation request: the inventory record plus optional samples and monitoring."""

    # ``model_id`` / ``model_class`` are domain field names, not Pydantic's protected namespace.
    model_config = ConfigDict(protected_namespaces=())

    model_id: str
    name: str
    model_class: str
    owner: str
    dimensions: dict[str, str] = Field(default_factory=dict)
    sample: SampleModel = Field(default_factory=SampleModel)
    observed: dict[str, float] = Field(default_factory=dict)

    def to_domain(self) -> ValidationRequest:
        record = InventoryRecord(
            model_id=self.model_id,
            name=self.name,
            model_class=ModelClass(self.model_class),
            owner=self.owner,
            dimensions=dict(self.dimensions),
        )
        return ValidationRequest(
            record=record, sample=self.sample.to_domain(), observed=dict(self.observed)
        )


class CitationModel(BaseModel):
    source_id: str
    title: str
    snippet: str = ""


class FindingModel(BaseModel):
    id: str
    severity: str
    summary: str
    detail: str = ""


class TestOutcomeModel(BaseModel):
    metric: str
    value: float
    bar: float
    passed: bool


class ValidationResponse(BaseModel):
    # ``model_name`` is a domain field name, not Pydantic's protected namespace.
    model_config = ConfigDict(protected_namespaces=())

    subject: str
    model_name: str
    tier: str
    severity: str
    decision: str
    summary: str
    requires_human_review: bool
    #: Where the escalation WENT (rule R8): the Hrz7 review id, or the local queue reference.
    #: Empty only when the result did not escalate. A caller can tell a routed escalation from
    #: a flag that stopped here, which is the whole point of the rule.
    review_ref: str = ""
    battery: list[TestOutcomeModel] = []
    findings: list[FindingModel] = []
    citations: list[CitationModel] = []

    @classmethod
    def from_domain(cls, result: ValidationOutcome, *, review_ref: str = "") -> ValidationResponse:
        return cls(
            subject=result.subject,
            model_name=result.model_name,
            tier=result.tier.value,
            severity=result.severity.value,
            decision=result.decision.value,
            summary=result.summary,
            requires_human_review=result.requires_human_review,
            review_ref=review_ref,
            battery=[
                TestOutcomeModel(metric=o.metric, value=o.value, bar=o.bar, passed=o.passed)
                for o in result.battery.outcomes
            ],
            findings=[
                FindingModel(id=f.id, severity=f.severity.value, summary=f.summary, detail=f.detail)
                for f in result.findings
            ],
            citations=[
                CitationModel(source_id=c.source_id, title=c.title, snippet=c.snippet)
                for c in result.citations
            ],
        )


class HealthResponse(BaseModel):
    status: str
    profile: str
    region: str
    #: Provenance the UI banner states on every page: where the runtime sits and which model
    #: answers. Both are read off the service because the browser cannot know either.
    runtime: str = "local"  # "gcp" | "local"
    generator_model: str = "deterministic-offline-stub"
