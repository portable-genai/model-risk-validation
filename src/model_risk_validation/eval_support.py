"""Shared scoring helpers for the offline eval, importable from both the runner and the tests.

Keeping the metric bodies here (rather than only in ``eval/run_eval.py``) lets the red-proof
tests import and exercise them directly, so ``tests/unit/test_eval_metrics.py`` proves the same
function the gate runs can go red, not a re-implementation of it.

Only ``tier_accuracy`` lives here: ``pii_safety`` needs the audit rows a run wrote, so it stays
in ``eval/run_eval.py`` as ``audit_texts`` plus ``pii_safety``, and the red proofs import
``run_eval`` (``pythonpath`` carries ``eval`` for exactly that). They must not re-implement it
locally: a local four-line copy is what let the shipped metric read only ``redacted_summary``
and stay green while the citation beside it carried the identifier.
"""

from __future__ import annotations

from collections.abc import Mapping

from .adapters.local.audit import LocalAuditAdapter
from .adapters.local.tracer import LocalNoopTracerAdapter
from .config import Settings
from .domain.inventory import InventoryRecord
from .domain.models import ValidationRequest
from .domain.taxonomy import ModelClass
from .domain.validation_service import ValidationService


def record_from_case(case: Mapping[str, object]) -> InventoryRecord:
    """Build an inventory record from a golden-dataset row."""
    raw_dims = case.get("dimensions")
    dimensions = (
        {str(k): str(v) for k, v in raw_dims.items()} if isinstance(raw_dims, Mapping) else {}
    )
    return InventoryRecord(
        model_id=str(case.get("model_id", "M-EVAL")),
        name=str(case.get("name", "Eval model (FICTIONAL)")),
        model_class=ModelClass(str(case["model_class"])),
        owner=str(case.get("owner", "owner@bank.example")),
        dimensions=dimensions,
    )


def engine_tier(case: Mapping[str, object]) -> str:
    """The tier the deterministic engine assigns to a case (SDK-free, in-memory audit)."""
    settings = Settings(profile="local", audit_path=":memory:")
    audit = LocalAuditAdapter(settings)
    result = ValidationService(audit, tracer=LocalNoopTracerAdapter(settings)).validate(
        ValidationRequest(record=record_from_case(case)), actor="eval-bot"
    )
    return result.tier.value


def tier_matches(case: Mapping[str, object]) -> float:
    """1.0 when the engine's tier equals the golden ``expected_tier`` label, else 0.0.

    The label is the INDEPENDENT oracle; this never reads the engine's own verdict as truth.
    """
    return 1.0 if engine_tier(case) == case["expected_tier"] else 0.0
