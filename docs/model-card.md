# Model card: Model Risk Validation Copilot (Mrm1)

This is a STARTER model card, and its headline is unusual: **this system has no model in its
path.** It is recorded here explicitly rather than left to be inferred, because a repo whose
subject matter is model risk is exactly the one where a reader will assume otherwise.

## The current state: deterministic end to end

There is **no `GenerationPort`** in `src/model_risk_validation/ports/`, and **no generation adapter** in any
of the three profiles (`adapters/local/`, `adapters/gcp/`, `adapters/onprem/` hold audit,
evaluation, identity, obligations, review_router and tracer, and nothing else). No prompt is built
at runtime, no request leaves the process for an inference endpoint, and no model output is
parsed. Every consequential output is pure stdlib:

| Output | Produced by |
|---|---|
| Materiality tier and its score | `domain/tiering.py` over the class's `TieringPack` |
| Each battery statistic and its pass or fail | `domain/battery/stats.py` and `domain/battery/runner.py` |
| Each monitoring breach and the case severity | `domain/monitoring.py` over the tier's `MonitoringPack` |
| Whether the run escalates | `domain/validation_service.py` |
| The edges proposed into the Rgc7 register | `domain/obligations.py`, always in the `PROPOSED` state |

The statistics deliberately use no numpy and no scipy, and they raise `StatInputError` rather than
returning a plausible number on an input they cannot honestly score. A missing input is a named
GAP, never a pass.

## The drafting contract, built ahead of the seam

`domain/prompts.py` is a contract with no counterparty yet. It defines what a drafting model would
be allowed to say, and it is complete and unit-tested (`tests/unit/test_prompts.py`):

- `allowed_figures(outcome)` is the closed set of numeric tokens the engine produced: the tier
  score, each battery statistic and its bar, each breach value. A draft may restate any of these
  and no others, so a model that rounds differently or invents a number is caught.
- `build_prompt_facts(outcome)` is the structured fact block a model would narrate.
- `validate_draft(raw_sections, outcome)` requires every section to be present, non-empty and
  fully grounded, and raises `DraftValidationError` otherwise. The caller discards the draft and
  escalates; an ungrounded narrative never reaches a user or the audit record.

Because nothing calls it, none of that is currently exercised in production behaviour. Treat it as
a design commitment, not as a control that is running.

## What must be true before a drafting model is bound

1. **A port, three adapters, five registrations.** Define `ports/generation.py`, bind it in
   `local` (a deterministic stub that restates the facts, never a silent empty return), `gcp` and
   `onprem` (fail-fast), and register it in all five homes the contract test checks. See
   `CONTRIBUTING.md`.
2. **The validator on the hot path.** `validate_draft` must run on every reply, with the discard
   and the escalation wired, before any draft reaches a surface or the audit record.
3. **Model id, version and region** (P-07): pin the exact model and record it here. Gemini model
   ids are regional and an unavailable one fails at call time rather than at boot.
4. **Budget, rate limit and a kill switch** (P-10, P-11): a per-tenant token budget, a request
   rate limit, and a switch that forces deterministic-only operation.
5. **Prompt-injection screening** (rule R1): bind the Hrz1 guardrail gateway before any untrusted
   free text (a model owner's narrative, an extracted document section) reaches the fact block,
   and fail closed to deterministic-only when the screen is unavailable.
6. **Evaluation of the live model**: add a managed-profile eval run registered with the Hrz4
   promotion gate (P-08, rule R5) that scores draft groundedness against the same golden cases.
7. **A reasoning trace in the audit record** (P-07): today the audit record carries the engine's
   figures; a drafted document needs its prompt and reply pair recorded alongside them.

## Related but separate: the model-documentation extraction seam

`domain/inventory.py` describes candidate attributes arriving "through `ports/model_docs.py`",
which does not exist either. If that extraction is implemented with a model, it is a SECOND model
surface and needs its own row in this card, its own guardrail screening, and the same
candidate-validation discipline the inventory engine already applies: a candidate is validated
against the record, never trusted over it.

## Until then

The system is safe to run as built, because it is deterministic: the same record and the same
samples always produce the same tier, the same verdicts and the same escalation. That is the
property to preserve deliberately rather than to drift out of.
