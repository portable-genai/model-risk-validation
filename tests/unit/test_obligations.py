"""Slice 6: the model-to-obligation feed edges are typed by the kit and complete per model.

Freezes the contract model-risk-validation emits against obligations-control-mapping: the edges are
``OBLIGATION_TO_CONTROL``, PROPOSED (never auto-accepted, so coverage in obligations-control-mapping
rests on human acceptance), one per model-risk obligation (export completeness), and the model is
the control vertex.
"""

from __future__ import annotations

from obligation_register import EdgeKind, EdgeStatus, NodeKind

from model_risk_validation.domain.obligations import MODEL_RISK_OBLIGATIONS, model_obligation_edges

from tests.fixtures import sample_cases


def test_every_model_yields_one_edge_per_obligation() -> None:
    outcome = sample_cases.escalating_outcome()
    edges = model_obligation_edges(outcome)
    assert len(edges) == len(MODEL_RISK_OBLIGATIONS), "export completeness: a model missed the feed"


def test_the_edges_propose_the_model_as_a_control_answering_each_obligation() -> None:
    outcome = sample_cases.escalating_outcome()
    for edge in model_obligation_edges(outcome):
        assert edge.kind is EdgeKind.OBLIGATION_TO_CONTROL
        assert edge.src.kind is NodeKind.OBLIGATION
        assert edge.dst.kind is NodeKind.CONTROL
        assert edge.dst.id == outcome.subject


def test_the_edges_are_proposed_not_accepted() -> None:
    """A machine proposal must never count toward obligations-control-mapping coverage until a human
    accepts it.
    """
    for edge in model_obligation_edges(sample_cases.escalating_outcome()):
        assert edge.status is EdgeStatus.PROPOSED
        assert edge.counts_for_coverage is False


def test_the_edge_ids_are_deterministic() -> None:
    outcome = sample_cases.escalating_outcome()
    first = [e.id for e in model_obligation_edges(outcome)]
    second = [e.id for e in model_obligation_edges(outcome)]
    assert first == second
