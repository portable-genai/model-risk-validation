"""Model inventory: the record shape and the deterministic candidate-validation engine (slice 2).

Mrm1 OWNS the inventory of quantitative (non-AI) models. A record declares the model's class,
owner and the four tiering dimensions; legacy model documentation may also arrive extracted
(through ``ports/model_docs.py``) as CANDIDATE attributes, which this engine validates against
the record rather than trusting. A candidate that agrees confirms; one that conflicts is a
finding for a human; one that fills an undeclared dimension is adopted but flagged as
document-sourced. The engine is pure: same record plus same candidates, same result, and it
NEVER invents a value, because a fabricated attribute would flow straight into the tier.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date

from .kernel import Citation, Finding, Severity
from .taxonomy import DIMENSIONS, FAILSAFE_LEVEL, Level, ModelClass, coerce_level

# Detail strings hoisted to module constants: inside a deeply-nested Finding(...) call the same
# prose would run past the line-length limit, and a reused message belongs in one place anyway.
_DETAIL_UNKNOWN = "Ignored for tiering; a reviewer confirms the taxonomy."
_DETAIL_UNPARSEABLE = "Not adopted; the declared value or the failsafe stands."
_DETAIL_ADOPTED = "Document-sourced; a reviewer confirms the declaration."
_DETAIL_CONFLICT = "Declared value kept; a reviewer resolves before tiering."
_DETAIL_UNDECLARED = "Declare the level or accept the onerous default."


@dataclass(frozen=True, slots=True)
class InventoryRecord:
    """One quantitative model in the firm's inventory.

    ``dimensions`` declares a :class:`~.taxonomy.Level` per tiering dimension. A dimension left
    out is not an error here (the tiering engine fails it closed to the onerous level and records
    a gap); declaring one at a value that is not a known level IS surfaced, because a typo that
    silently became "high" would be indistinguishable from a deliberate declaration.
    """

    model_id: str
    name: str
    model_class: ModelClass
    owner: str
    dimensions: Mapping[str, str] = field(default_factory=dict)
    as_of: date = field(default_factory=date.today)

    def level(self, dimension: str) -> Level | None:
        """The parsed level for a dimension, or ``None`` when absent or unparseable."""
        if dimension not in self.dimensions:
            return None
        return coerce_level(self.dimensions[dimension])

    def citation(self) -> Citation:
        """Provenance pointing at this inventory row."""
        return Citation(
            source_id=f"inventory:{self.model_id}",
            title=f"Inventory record {self.model_id}",
            snippet=f"{self.name} [{self.model_class.value}] owner {self.owner}",
        )


@dataclass(frozen=True, slots=True)
class CandidateAttribute:
    """An attribute extracted from legacy documentation, awaiting validation.

    ``dimension`` is the tiering dimension it purports to fill, ``value`` the extracted level and
    ``source_ref`` a locator into the source document, so an adopted candidate stays traceable.
    """

    dimension: str
    value: str
    source_ref: str = ""


@dataclass(frozen=True, slots=True)
class ReconciledInventory:
    """A record after document candidates have been reconciled against it, plus the findings."""

    record: InventoryRecord
    findings: tuple[Finding, ...] = ()

    @property
    def escalates(self) -> bool:
        """Any conflict finding means a human reconciles before the tier is trusted."""
        return any(f.severity in (Severity.HIGH, Severity.CRITICAL) for f in self.findings)


class InventoryEngine:
    """Reconcile extracted document candidates against a declared inventory record.

    Pure and deterministic. Adopting a candidate only fills a dimension the record LEFT BLANK;
    it never overrides a declared value, and a candidate that contradicts a declaration is a
    finding, not an edit. An unknown dimension name or an unparseable value is also a finding.
    """

    def reconcile(
        self, record: InventoryRecord, candidates: tuple[CandidateAttribute, ...]
    ) -> ReconciledInventory:
        findings: list[Finding] = []
        adopted: dict[str, str] = dict(record.dimensions)
        for candidate in candidates:
            findings.extend(self._one(record, candidate, adopted))
        merged = InventoryRecord(
            model_id=record.model_id,
            name=record.name,
            model_class=record.model_class,
            owner=record.owner,
            dimensions=adopted,
            as_of=record.as_of,
        )
        ordered = tuple(sorted(findings, key=lambda f: f.sort_key))
        return ReconciledInventory(record=merged, findings=ordered)

    def _one(
        self, record: InventoryRecord, candidate: CandidateAttribute, adopted: dict[str, str]
    ) -> list[Finding]:
        cite = (
            Citation(
                source_id=candidate.source_ref or f"doc:{record.model_id}",
                title="Extracted model documentation",
                snippet=f"{candidate.dimension}={candidate.value}",
            ),
        )
        if candidate.dimension not in DIMENSIONS:
            return [
                Finding(
                    id=f"inventory:unknown_dimension:{candidate.dimension}",
                    severity=Severity.MEDIUM,
                    summary=f"Document names an undefined dimension: {candidate.dimension}",
                    detail=_DETAIL_UNKNOWN,
                    citations=cite,
                )
            ]
        parsed = coerce_level(candidate.value)
        if parsed is None:
            return [
                Finding(
                    id=f"inventory:unparseable_candidate:{candidate.dimension}",
                    severity=Severity.MEDIUM,
                    summary=f"Extracted {candidate.dimension} not a level: {candidate.value!r}",
                    detail=_DETAIL_UNPARSEABLE,
                    citations=cite,
                )
            ]
        declared = record.level(candidate.dimension)
        if declared is None:
            adopted[candidate.dimension] = parsed.value
            return [
                Finding(
                    id=f"inventory:document_sourced:{candidate.dimension}",
                    severity=Severity.LOW,
                    summary=f"Adopted {candidate.dimension}={parsed.value} from docs",
                    detail=_DETAIL_ADOPTED,
                    citations=cite,
                )
            ]
        if declared != parsed:
            return [
                Finding(
                    id=f"inventory:conflict:{candidate.dimension}",
                    severity=Severity.HIGH,
                    summary=f"Conflict {candidate.dimension}: {declared.value}/{parsed.value}",
                    detail=_DETAIL_CONFLICT,
                    citations=cite,
                )
            ]
        return []


def failsafe_note(record: InventoryRecord) -> tuple[Finding, ...]:
    """A gap finding per undeclared dimension, since tiering will fail it closed to HIGH.

    Surfacing the failsafe as a finding is the point: a tier that is onerous BECAUSE a dimension
    was never declared must be visibly attributable to the omission, not read as a genuine
    high-materiality assessment.
    """
    out: list[Finding] = []
    for dimension in DIMENSIONS:
        if record.level(dimension) is None:
            out.append(
                Finding(
                    id=f"inventory:undeclared_dimension:{dimension}",
                    severity=Severity.MEDIUM,
                    summary=f"{dimension} undeclared; failed closed to {FAILSAFE_LEVEL.value}",
                    detail=_DETAIL_UNDECLARED,
                    citations=(record.citation(),),
                )
            )
    return tuple(out)
