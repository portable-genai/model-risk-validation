# Features FAQ

For a product owner, a model-risk lead or a delivery manager deciding what this system does, what
it refuses to do, and where its responsibility ends.

### What does it actually do?

It runs the second line's model-risk lifecycle for a quantitative model, in four deterministic
steps plus a feed:

1. **Inventory** (`domain/inventory.py`): the record shape, plus a candidate-validation engine.
   Attributes extracted from legacy model documentation arrive as CANDIDATES and are validated
   against the record rather than trusted: a candidate that agrees confirms, one that conflicts is
   a finding for a human, and one that fills an undeclared dimension is adopted but flagged as
   document-sourced.
2. **Tiering** (`domain/tiering.py`): the four declared dimensions are scored by the model class's
   `TieringPack`, summed with the pack's weights, and banded into a materiality tier.
3. **Validation battery** (`domain/battery/`): the pack names the required statistics and their
   bars; `stats.py` computes them in pure stdlib and `runner.py` returns a pass or fail per test.
4. **Ongoing monitoring** (`domain/monitoring.py`): observed metric values are classified on a
   severity ladder (clear, amber, red) against the tier's `MonitoringPack`, and the case severity
   is the worst across metrics.
5. **The Rgc7 feed** (`domain/obligations.py`): typed graph edges saying "this model answers this
   model-risk obligation", proposed into the register.

`domain/validation_service.py` composes them into one consequential result.

### What makes a tier or a battery verdict defensible?

Four rules, all pure code:

- **Fail closed on thin data.** An undeclared or unparseable tiering dimension is scored at
  `FAILSAFE_LEVEL` (HIGH), so a sparse record cannot tier itself down by saying less.
- **A red breach on a tier-1 model escalates a further step**, because a red on a material model
  is a critical, dual-control event rather than one more amber.
- **A missing input is a named GAP, never a pass.** The battery does not go GREEN while a required
  test has no data: a test that cannot be run has not been passed.
- **The statistics refuse rather than guess.** `stats.py` raises `StatInputError` on an input it
  cannot honestly score, because a fabricated statistic is worse than a named gap. Its reference
  values are pinned in `tests/unit/test_battery_stats.py` against independently computed figures,
  and each is proved able to move off that figure.

### Does a model write any of this?

No. Nothing in this service calls a model today: there is no generation port and no generation
adapter in any profile. `domain/prompts.py` holds the drafting CONTRACT for the day one is added
(the allowed-figure set, the prompt facts, and a validator that discards any draft introducing a
number the engine did not produce), and it is exercised only by its unit test. See
[`../model-card.md`](../model-card.md), which says this plainly rather than describing a model
that is not there.

### What will it refuse to do?

- **It will not pass a test it could not run.**
- **It will not trust an extracted attribute over the record.**
- **It will not auto-execute a consequential result.** A tier change, a failing battery or a
  breach sets `requires_human_review` and is ROUTED to the Hrz7 console in the same call that
  produced it (rule R8).
- **It will not inflate an Rgc7 coverage figure.** Every edge it proposes is in the `PROPOSED`
  state, and Rgc7 counts only human-accepted edges.

### Which surfaces expose it?

The FastAPI app (`POST /v1/validate`), the argparse CLI (`model_risk_validation validate`), the agent tools
(`validate_model`, `verify_audit_trail`, advertised on the A2A card at
`/.well-known/agent-card.json`), the embeddable `ui/` micro-frontend, and the eval harness. Each
routes escalations in the same call, so rule R8 does not hold on some surfaces and not others.

### What does this repo own, and what does it integrate?

| Concern | Owner | How this repo touches it |
|---|---|---|
| Quantitative, non-AI model risk: inventory, tiering, battery, monitoring | **this repo (Mrm1)** | it IS the system of record for that population. |
| AI and agent model risk, and the promotion gate | **Hrz4** AI quality and model risk | a separate population with a separate inventory. Two inventories for the same model is the failure the boundary exists to prevent. `eval/run_eval.py --mode gate` still asks Hrz4 about THIS service's own promotion. |
| The obligation to control graph | **Rgc7** obligations and control mapping | this repo PROPOSES typed edges into it (`RGC7_OBLIGATIONS_URL`), always in the `PROPOSED` state. It does not keep a register. |
| Agent discovery and entitlements | **Hrz3** agent registry | this agent publishes a card; the registry owns discovery. |
| Traces and the immutable audit sink | **Hrz5** agent observability | `AuditSinkPort` and `ObservabilityTracerPort`. |
| Human review and maker-checker | **Hrz7** human review console | `ReviewRouterPort` over the shared `review-kit`. This repo produces escalations; it does not render a queue. |
| Prompt-injection defence and output filtering | **Hrz1** agent guardrail gateway | not wired, and nothing to wire it to yet: no model call happens here. |
| Grounded retrieval over an enterprise corpus | **Hrz2** enterprise knowledge base | not wired; this service reasons over declared records and supplied samples. |

### Can I demo it without a cloud project?

Yes, and the demo is code rather than a deck. `make demo` runs a presenter-paced walkthrough on
its own loopback server; `make demo-selftest` runs the same arc headless and asserts every
narrated claim, so a claim that stops being true fails a build rather than a meeting;
`make demo-static` renders the same audit-first panels to static HTML for screenshots.

### What is not built yet?

The honest list is [`../practices-audit.md`](../practices-audit.md) and the `TODO (repo owner)`
rows in [`../../COMPLIANCE.md`](../../COMPLIANCE.md). The largest items: no drafting model is
wired (the contract exists, the seam does not), the model-documentation extraction port the
inventory docstring anticipates is not defined, and this repo's metric bundle is not yet
registered with Hrz4 so `--mode gate` has no authority to ask.
