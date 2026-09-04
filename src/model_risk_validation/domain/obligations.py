"""Model-to-obligation records for the obligations-control-mapping feed (slice 6), typed by
obligation-register-kit.

model-risk-validation does not own obligation record shapes; the shared kernel does. This module
builds, from a :class:`~.models.ValidationOutcome`, the typed graph edges model-risk-validation
PROPOSES into the obligations-control-mapping register: each says "this quantitative model answers
this model-risk obligation", as an ``OBLIGATION_TO_CONTROL`` edge in the ``PROPOSED`` state.
Proposed, never accepted: coverage in obligations-control-mapping counts only human-accepted edges,
so a machine proposal from here never inflates a coverage figure until a reviewer accepts it. Pure:
it constructs kit dataclasses and performs no I/O.

The model is the ``CONTROL`` vertex (the governed thing whose validation answers the obligation);
the obligations are a fixed set of second-line model-risk duties (SR 11-7 validation, PRA SS1/23
documentation, ongoing monitoring). A firm swaps this set for its own register ids without
touching the edge-building logic.
"""

from __future__ import annotations

from obligation_register import Citation as KitCitation
from obligation_register import Edge, EdgeKind, EdgeStatus, NodeKind, NodeRef

from .models import ValidationOutcome

#: The model-risk obligations every tiered model is proposed against. Synthetic register ids; a
#: firm maps these to its own obligations-control-mapping obligation nodes. The tuple is the frozen
#: contract this feed
#: emits against, and ``tests`` freeze the edge shape it produces.
MODEL_RISK_OBLIGATIONS: tuple[tuple[str, str], ...] = (
    ("OBL-MRM-VALIDATION", "SR 11-7 independent validation of the model"),
    ("OBL-MRM-DOCUMENTATION", "PRA SS1/23 model development documentation"),
    ("OBL-MRM-MONITORING", "Ongoing performance monitoring of the model"),
)


def model_obligation_edges(outcome: ValidationOutcome) -> tuple[Edge, ...]:
    """One PROPOSED obligation-to-control edge per model-risk obligation for this model.

    Deterministic and complete: every tiered model yields exactly ``len(MODEL_RISK_OBLIGATIONS)``
    edges, which is what the export-completeness metric checks. The model's tier and validation
    summary ride on the edge note and citation, so obligations-control-mapping shows why the
    proposal was made.
    """
    control = NodeRef(NodeKind.CONTROL, outcome.subject)
    citation = KitCitation(
        source_id=f"mrm:{outcome.subject}",
        title=f"model-risk-validation of {outcome.model_name}",
        snippet=outcome.summary,
    )
    edges: list[Edge] = []
    for obligation_id, _title in MODEL_RISK_OBLIGATIONS:
        edges.append(
            Edge(
                src=NodeRef(NodeKind.OBLIGATION, obligation_id),
                dst=control,
                kind=EdgeKind.OBLIGATION_TO_CONTROL,
                status=EdgeStatus.PROPOSED,
                citations=(citation,),
                note=f"tier {outcome.tier.value}; {outcome.summary}",
            )
        )
    return tuple(edges)
