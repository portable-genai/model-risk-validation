"""Each smoke-eval metric is provably able to go RED (a metric that cannot is not a metric).

The metrics score against the dataset's OWN labels (an independent oracle), so a red proof feeds
a mislabelled or degraded case and asserts the metric catches it. This is the provable-red
discipline the plan requires for slice 2 and slice 5.

Both proofs aim at the SHIPPED scorer, imported from ``run_eval`` the way the gate imports it.
The pii_safety proof here used to score a four-line local helper defined above the assertion, so
it stayed green while the shipped metric read only ``redacted_summary`` and could not see a leak
in the citation beside it. The mutant here is a leak in the SUMMARY;
``tests/unit/test_not_falsely_green.py`` carries the complementary mutant that leaks only in the
CITATION, which is the field the old metric was blind to.
"""

from __future__ import annotations

from typing import Any

import run_eval as ev
from agent_eval_kit import assert_can_go_red

from model_risk_validation.eval_support import tier_matches

from tests.fixtures import sample_cases

_PLANTED = (sample_cases.PLANTED_NRIC,)


def test_tier_accuracy_can_go_red() -> None:
    # green: the golden label matches the engine tier; red: a wrong label the engine contradicts.
    assert_can_go_red(
        tier_matches,
        green={"model_class": "irb", "expected_tier": "tier_1"},
        red={"model_class": "irb", "expected_tier": "tier_3"},
        threshold=0.99,
        metric="tier_accuracy",
    )


def _score(rows: list[dict[str, Any]]) -> float:
    """The gate's own scorer over the gate's own field selection. No re-implementation here."""
    return ev.pii_safety(ev.audit_texts(rows), _PLANTED)


def test_pii_safety_can_go_red_on_a_summary_leak() -> None:
    clean: dict[str, Any] = {
        "actor": sample_cases.ACTOR,
        "redacted_summary": "M-IRB-009 Gamma model: owner NRIC [REDACTED:SG_NRIC_FIN] on file",
        "citations": [],
    }
    leaky: dict[str, Any] = {
        **clean,
        "redacted_summary": (
            f"M-IRB-009 Gamma model: owner NRIC {sample_cases.PLANTED_NRIC} on file"
        ),
    }
    assert_can_go_red(
        _score,
        green=[clean],
        red=[leaky],
        threshold=ev.THRESHOLDS["pii_safety"],
        metric="pii_safety",
    )
