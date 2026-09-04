#!/usr/bin/env python3
"""Evaluation gate for Model Risk Validation Copilot (model-risk-validation).

Two named layers via ``--mode`` (the scaffold is ``agent_eval_kit.eval_main``):

* **smoke** (default) - the offline pre-merge check CI runs on every change: it drives the real
  ``ValidationService`` against a golden set with SDK-free local adapters and scores metrics against
  the dataset's OWN labels (an INDEPENDENT oracle), never the pipeline's own verdict. * **gate** -
  the promotion verdict from the shared model-quality-gate authority (requires the ``gcp`` profile),
  via ``agent_eval_kit.PromotionGateClient``.

The smoke metrics: ``tier_accuracy`` scores the engine's assigned tier against the golden
``expected_tier`` a human labelled; ``pii_safety`` scores that no raw identifier survives into
any CONTENT field of an audit record, citations included, never the summary alone. Each is proved
able to go red against the SHIPPED scorer in ``tests/unit/test_not_falsely_green.py`` and
``tests/unit/test_eval_metrics.py``: a metric that cannot go red is not a metric, and a red proof
aimed at a local re-implementation of the metric is not a proof about the gate.

Exit is ``0`` iff every metric meets its threshold (and, in gate mode, the authority agrees).
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from agent_eval_kit import EvalMetricResult, EvalReport, PromotionGateClient, eval_main
from pii_kit import pack_leak

from model_risk_validation.adapters.local.audit import (
    LocalAuditAdapter,
)
from model_risk_validation.adapters.local.tracer import (
    LocalNoopTracerAdapter,
)
from model_risk_validation.config import (
    Settings,
)
from model_risk_validation.domain.models import (
    ValidationRequest,
)
from model_risk_validation.domain.pii import (
    PII_PATTERNS,
)
from model_risk_validation.domain.validation_service import (
    ValidationService,
)
from model_risk_validation.eval_support import (
    record_from_case,
    tier_matches,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET = _REPO_ROOT / "eval" / "datasets" / "golden_cases.jsonl"

THRESHOLDS: dict[str, float] = {"tier_accuracy": 0.99, "pii_safety": 0.99}
#: The registered model-quality-gate metric bundle for this vertical (model-quality-gate owns the
#: metrics + thresholds).
_BUNDLE = "model-risk-validation"


def _load(path: Path) -> list[dict[str, object]]:
    cases: list[dict[str, object]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        cases.append(json.loads(line))
    if not cases:
        raise SystemExit(f"{path}: golden dataset is empty")
    return cases


def _mean(scores: list[float]) -> float:
    return round(sum(scores) / len(scores), 4) if scores else 0.0


def audit_texts(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    """Every CONTENT-bearing field of every audit row, which is what a leak scan has to read.

    Collecting ``redacted_summary`` and nothing else would name the one field the
    redactor already masks: the metric would ask the redactor whether it had redacted, believe
    the answer, and report a green while the SAME record's citation snippet carries the
    identifier verbatim. Citations travel inside the record, and they carry raw source text in
    ``snippet`` (the model name, class and owner address) and in ``source_id`` and ``title``,
    which embed the client-supplied model id.

    ``actor`` is excluded deliberately: it is the verified principal and an address by design, so
    a blanket scan over a whole row could never go green, and a metric nobody can make green
    gets deleted rather than fixed.
    """
    texts: list[str] = []
    for row in rows:
        texts.append(str(row.get("redacted_summary", "")))
        texts.append(json.dumps(row.get("citations", []), sort_keys=True))
    return texts


def pii_safety(records: Sequence[str], planted: Sequence[str]) -> float:
    """No identifier may survive into an audit record, by the pack rows OR by planted literal.

    Two oracles, because they fail independently: the pack scan uses the same rows the redactor
    masks with (so a redactor that skipped a field is caught), and the planted-literal check
    fires even if a pattern row is broken (so a pack that stopped matching is caught too).
    """
    pack_leaked = any(pack_leak(text, PII_PATTERNS) for text in records)
    literal_leaked = any(token in text for token in planted for text in records)
    return 0.0 if (pack_leaked or literal_leaked) else 1.0


def run_smoke(dataset: Path) -> EvalReport:
    cases = _load(dataset)

    tier_scores = [tier_matches(case) for case in cases]

    # pii_safety: no raw identifier may survive into any audit record. Recompute over a single
    # shared sink so the scan sees every write; `audit_texts` decides WHICH fields count as the
    # record's content, and see its docstring for why the summary alone is not the record.
    settings = Settings(profile="local", audit_path=":memory:")
    audit = LocalAuditAdapter(settings)
    service = ValidationService(audit, tracer=LocalNoopTracerAdapter(settings))
    for case in cases:
        request = ValidationRequest(record=record_from_case(case))
        service.validate(request, actor="eval-bot")
    records = audit_texts(audit.log.read_all())
    planted = [str(case["planted"]) for case in cases if case.get("planted")]

    results = (
        EvalMetricResult.scored("tier_accuracy", _mean(tier_scores), THRESHOLDS["tier_accuracy"]),
        EvalMetricResult.scored(
            "pii_safety", pii_safety(records, planted), THRESHOLDS["pii_safety"]
        ),
    )
    return EvalReport(dataset=str(dataset), results=results, n_examples=len(cases))


def run_gate(dataset: Path) -> tuple[EvalReport, bool]:
    settings = Settings.load()
    if settings.profile != "gcp":
        raise SystemExit(
            "--mode gate is the promotion authority and requires "
            f"MRM_PROFILE=gcp (got {settings.profile!r}); "
            "run --mode smoke for the offline pre-merge check."
        )
    client = PromotionGateClient(
        os.environ.get("MRM_QUALITY_URL", "http://localhost:8084"),
        bundle=_BUNDLE,
        model="gemini-3.5-flash",
    )
    return client.evaluate(str(dataset)), client.gate(str(dataset))


if __name__ == "__main__":
    raise SystemExit(
        eval_main(
            smoke=run_smoke,
            gate=run_gate,
            default_dataset=DEFAULT_DATASET,
            description="Offline / model-quality-gate for model-risk-validation.",
        )
    )
