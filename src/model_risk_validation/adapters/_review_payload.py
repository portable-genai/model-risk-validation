"""Shared conversion from an escalated result to an ``review-kit`` Review payload.

Lives in the adapter layer, not the pure domain, because it depends on the kit. The subject,
summary and every citation snippet are redacted BEFORE they leave the process (the same
redact-before-anything rule the audit write obeys), using the shared ``pii-kit``, so no raw
identifier reaches Hrz7 over the wire; Hrz7 redacts again before its own audit write (defence in
depth). ``maker`` and ``tenant`` are asserted here and trusted by Hrz7 because the caller is an
authenticated S2S service; per-hop on-behalf-of token exchange is the deferred next layer.
"""

from __future__ import annotations

import re

from pii_kit import NATIONAL_ID_PATTERNS, UNIVERSAL_PATTERNS, national_patterns_for
from pii_kit import redact as pii_redact
from review_kit import Citation as KitCitation
from review_kit import Review

from ..domain.kernel import Severity
from ..domain.models import ValidationOutcome

#: Cap the citations carried on the wire: enough for a reviewer to trace the decision without
#: copying the whole evidence set into the console.
_MAX_CITATIONS = 8

#: The console is a SHARED sink: a case filed in one market may still quote another market's
#: national id, so the payload is scrubbed against every jurisdiction's rows plus the universal
#: email/phone rows, whatever this deployment's own ``domain.pii.JURISDICTIONS`` selects.
_ALL_PATTERNS = (
    *national_patterns_for(tuple(NATIONAL_ID_PATTERNS.keys())),
    *UNIVERSAL_PATTERNS,
)

#: Bands that demand dual control (two approvals) rather than a single checker.
_DUAL_CONTROL = (Severity.CRITICAL,)


def _redact(text: str) -> str:
    """Mask every jurisdiction's identifiers plus email/phone, and normalise whitespace."""
    return re.sub(r"\s+", " ", pii_redact(text, _ALL_PATTERNS)).strip()


def _kit_citations(result: ValidationOutcome) -> tuple[KitCitation, ...]:
    """Every field of every citation is masked, not only the snippet.

    A locator is routinely built from client text (``inventory:<the client-supplied model id>``,
    and ``domain.inventory`` builds one straight from a legacy document's ``source_ref``), so
    masking only the snippet let an identifier cross to the shared console in the field named
    like a key. De-duplication keys off the REDACTED locator, so two rows that differ only in a
    masked identifier collapse to one citation rather than both crossing the wire.
    """
    seen: set[str] = set()
    out: list[KitCitation] = []
    for citation in result.citations:
        source_id = _redact(citation.source_id)
        if source_id in seen:
            continue
        seen.add(source_id)
        out.append(
            KitCitation(
                source_id=source_id,
                title=_redact(citation.title),
                snippet=_redact(citation.snippet),
            )
        )
        if len(out) >= _MAX_CITATIONS:
            break
    return tuple(out)


def result_to_review(result: ValidationOutcome, *, maker: str, tenant: str = "") -> Review:
    """Build the review a producer submits to Hrz7 when a validation run escalates.

    The subject is redacted ONCE and reused for the case reference and the idempotency key, so no
    raw identifier reaches the wire through a derived field. Masking it in ``subject``
    and passing it raw into ``case_ref`` and ``source_key`` beside it puts the identifier on the
    shared console in the two fields whose structural names make them look like keys rather than
    content. Here the subject is the inventory model id, which is client-supplied text; a model id
    should never carry personal data, and the redaction has to hold whether or not it does.

    The cost is named rather than hidden: two runs whose subjects differ ONLY in a masked
    identifier now share a source key and collapse to one review at the console. That is the
    right trade against publishing the identifier, and a model id distinguished solely by a
    national id is not a key anyone should be routing on. The key stays stable across retries
    because ``pii_kit.redact`` substitutes a fixed token per pattern; checked, not assumed
    (200 calls over a planted subject, one distinct output).
    """
    subject = _redact(result.subject)
    return Review(
        action="model_risk_validation:validate",
        subject=subject,
        maker=maker,
        tenant=tenant,
        summary=_redact(result.summary),
        severity=result.severity.value,
        required_approvals=2 if result.severity in _DUAL_CONTROL else 1,
        sod_group="model_risk_validation-maker-checker",
        case_ref=subject,
        # Producer-owned, tenant-scoped key so a retried delivery is idempotent at the console.
        source_key=f"Mrm1:{subject}:{result.severity.value}",
        citations=_kit_citations(result),
    )
