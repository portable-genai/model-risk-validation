"""Vertical-neutral domain kernel: pure-stdlib types the service reasons over.

Taxonomies are ``StrEnum``s from the commons (a member IS its wire value), citations carry
provenance, and the WORM audit record is stored already-redacted. Nothing here imports a web
framework or a cloud SDK (the commons packages it uses are themselves stdlib).

"Already redacted" is ENFORCED here rather than asked of every call site: see
:class:`AuditEvent`. The pattern selection comes from the sibling ``domain.pii``, which is the
one vertical-specific thing this otherwise vertical-neutral module knows, because a boundary
that cannot name the rows it masks with is not a boundary. ``domain.pii`` imports only
``pii_kit``, so there is no cycle, and ``pii_kit`` is on the core-purity allowlist.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from hex_service_kit.enums import LenientStrEnum
from pii_kit import redact

from .pii import PII_PATTERNS


def utcnow() -> datetime:
    """Timezone-aware UTC now (the single clock the domain uses)."""
    return datetime.now(UTC)


class Severity(LenientStrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Decision(LenientStrEnum):
    ALLOWED = "allowed"
    ESCALATED = "escalated"  # routed to a human (maker-checker, P-06)


@dataclass(frozen=True, slots=True)
class Citation:
    """Provenance attached to a generated claim (source + optional locator)."""

    source_id: str
    title: str
    snippet: str = ""


def redacted_citations(citations: tuple[Citation, ...]) -> tuple[Citation, ...]:
    """Mask EVERY field of every citation: the locator and the title as well as the snippet.

    A snippet is a slice of its source (the inventory citation's snippet is the model name, its
    class and its owner address) and a locator is routinely built from client text too
    (``inventory:<the client-supplied model id>``, and ``domain.inventory`` builds one straight
    from a legacy document's ``source_ref``). Both are raw client text wearing a
    structural-looking name. No sink can tell an engine-built citation from an extractor-built
    one by inspection, so this masks unconditionally: redacting text that carries no identifier
    is a no-op, while deciding per caller is how one caller ends up forgetting.
    """
    return tuple(
        Citation(
            source_id=redact(c.source_id, PII_PATTERNS),
            title=redact(c.title, PII_PATTERNS),
            snippet=redact(c.snippet, PII_PATTERNS),
        )
        for c in citations
    )


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """An immutable, already-redacted record of one interaction (P-04 / rule R2).

    "Already redacted" as a convention each call site has to remember is not enough, and
    ``ValidationService.validate`` masked ``redacted_summary`` and passed its citations through
    untouched, so the identifier the summary no longer carried was written into the WORM record
    anyway, one field away, into a store that is immutable and long-retained by design. So
    construction masks every CONTENT field: the summary, and each citation's locator, title and
    snippet. Redaction is idempotent, so a caller that already redacted loses nothing by the
    second pass, and a surface added later cannot leak by forgetting.

    ``actor`` is NOT masked. It is the verified principal and is an address by design: it is
    attribution, not content, and masking it would erase the only column that says who acted.
    That is also why a leak scan runs over the content fields rather than over a whole row.
    """

    action: str
    actor: str
    decision: Decision
    severity: Severity
    redacted_summary: str
    citations: tuple[Citation, ...] = ()
    timestamp: datetime = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        object.__setattr__(self, "redacted_summary", redact(self.redacted_summary, PII_PATTERNS))
        object.__setattr__(self, "citations", redacted_citations(tuple(self.citations)))


#: Numeric rank per severity, most severe first, so findings sort deterministically without an
#: LLM and a "worst wins" composition is a plain ``max``. The values are an implementation
#: detail of the ordering, never a wire value: the wire value is the ``StrEnum`` member itself.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.CRITICAL: 3,
    Severity.HIGH: 2,
    Severity.MEDIUM: 1,
    Severity.LOW: 0,
}


def severity_rank(severity: Severity) -> int:
    """The sort key for a severity: higher is more severe (CRITICAL is 3, LOW is 0)."""
    return _SEVERITY_RANK[severity]


def worst_severity(
    severities: tuple[Severity, ...], *, default: Severity = Severity.LOW
) -> Severity:
    """Compose severities with worst-wins; ``default`` when the tuple is empty."""
    return max(severities, key=severity_rank) if severities else default


@dataclass(frozen=True, slots=True)
class Finding:
    """One severity-ranked, explainable finding from a deterministic engine.

    ``id`` is a stable machine key (engine-scoped, e.g. ``battery:auc:below_bar``), ``summary``
    is a one-line human label, ``detail`` carries the specifics, and ``citations`` tie the
    finding to the evidence it was derived from. Findings sort by severity then ``id``, so the
    ordering is reproducible and never depends on a model.
    """

    id: str
    severity: Severity
    summary: str
    detail: str = ""
    citations: tuple[Citation, ...] = ()

    @property
    def sort_key(self) -> tuple[int, str]:
        """Most severe first, ties broken by the stable id."""
        return (-severity_rank(self.severity), self.id)
