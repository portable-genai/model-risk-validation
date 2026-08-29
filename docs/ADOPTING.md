# Adopting this repo as your base

This repository (Mrm1, the Model Risk Validation Copilot) is a **common base** that a bank or
other regulated institution forks to build its own **second-line model-risk function for
quantitative, non-AI models**: the inventory, the materiality tiering, the validation battery, the
ongoing performance monitoring, and the documentation draft that comes out of them. It ships a
reusable hexagonal core (a pure-stdlib domain, typed ports, three swappable adapter profiles, a
green offline gate) plus a fully worked validation vertical you can keep, retune, or replace with
your own model-risk standard.

This guide is the step-by-step for making it yours. It has two halves: a **mechanical rebrand**
(one script) and the **human decisions** the script cannot make for you.

> Related reading: [`ARCHITECTURE.md`](../ARCHITECTURE.md) (the port table and topology),
> [`CONTRIBUTING.md`](../CONTRIBUTING.md) (adding an adapter, adding a port), the
> [`faq/`](faq/) directory, [`model-card.md`](model-card.md) (the model boundary, which for this
> repo is mostly a statement about what is NOT there), [`practices-audit.md`](practices-audit.md).

---

## 1. What you keep vs what you rewrite

The core is hexagonal, and the boundary between reusable machinery and the model-risk vertical is
a physical module split with an enforced dependency direction (practices-audit check A7).
`domain/kernel.py` owns the vertical-neutral contracts; `domain/taxonomy.py` and
`domain/models.py` hold this vertical's nouns.

| Layer | Where | For your own model-risk standard |
|---|---|---|
| **Vertical-neutral machinery** | `domain/kernel.py` (`Citation`, `AuditEvent`, `Severity`, `Decision`), every Protocol in `ports/`, the container wiring in `config.py` | keep untouched |
| **The statistics** | `domain/battery/stats.py`: pure-stdlib, deterministic, total on its documented domain, raising `StatInputError` rather than returning a plausible number | keep untouched, and keep the reference values pinned in `tests/unit/test_battery_stats.py` |
| **Policy (your numbers)** | `domain/packs.py`: `TIERING_PACKS` (how a model class scores the four dimensions and where the tier bands fall), the `BatteryPack` bars, the `MonitoringPack` ladders. Plus the jurisdiction list in `domain/pii.py` and the thresholds in `eval/run_eval.py` | change deliberately (see section 4) |
| **Vertical (the nouns and the flow)** | `domain/taxonomy.py` (model classes, tiers, levels), `domain/models.py`, `domain/inventory.py`, `domain/tiering.py`, `domain/battery/runner.py`, `domain/monitoring.py`, `domain/prompts.py`, `domain/obligations.py`, the fixtures and the eval golden set | rewrite for your standard |

If your product is another *tier then test then monitor* second-line engine, the hexagon, the
three profiles, the packs-as-data mechanism, the eval gate and the Hrz7 review routing transfer
directly; you replace the taxonomy and the packs.

## 2. Core-vs-adopter-owned files (so upstream merges stay mechanical)

Upstream keeps evolving these; avoid diverging from them so you can pull fixes cleanly:

- **Upstream-owned** (take our changes): `domain/kernel.py`, `domain/battery/stats.py`, `ports/`,
  `tests/contract/`, the eval harness mechanics (`eval/run_eval.py`), the CI workflows, the
  hexagon wiring (`config.py` `Container`) and the deploy stack in `infra/terraform/`.
- **Adopter-owned** (yours; expect to edit): `config/settings.yaml` *values*, every pack in
  `domain/packs.py`, the taxonomy, the fixtures and the golden eval dataset,
  `adapters/onprem/*`, UI theming and branding, `infra/terraform/terraform.tfvars`, and the
  regulator crosswalk section of `COMPLIANCE.md`.

Track upstream via git tags; rebase your adopter-owned changes onto each release rather than
merging `main` continuously.

## 3. The mechanical rebrand (one script)

`scripts/rename_fork.py` rewrites the package name (`model_risk_validation`, which is also the console
script), the `MRM_` env prefix (including the bare token that
`infra/terraform/render.tf.json` carries so Terraform sets the same variable names on the
service), the cloud resource stem (`mrm1-svc`, the Terraform `name_prefix`) and the distribution
/ git id in one pass. Preview first, then apply:

```bash
# Preview (writes nothing):
python scripts/rename_fork.py --package acme_mrm_copilot --env-prefix ACME \
    --resource acme-mrm --dry-run

# Apply:
python scripts/rename_fork.py --package acme_mrm_copilot --env-prefix ACME \
    --resource acme-mrm --yes

# Then recreate the environment (the distribution name changed) and prove it is green:
python3.12 -m venv .venv && source .venv/bin/activate
make install
make gate
```

`--dist` defaults to the `--resource` value; pass it explicitly when your git id differs from your
resource stem. `--resource` is validated against the same regex the Terraform `name_prefix`
variable enforces, so a stem the stack would refuse fails here instead of at plan time. Add
`--include-docs` to sweep Markdown prose too. The catalog id `Mrm1` is left alone unless you pass
`--catalog-id`, so a fork stays traceable to the entry it descends from. The script deliberately
does NOT touch the human decisions below.

## 4. The human decisions (the script can't make these)

1. **Region / residency.** The build defaults to `asia-southeast1` (MAS / Singapore), chosen once
   and shared: `config/settings.yaml:region`, `infra/terraform/render.tf.json:render_region` and
   the Terraform `region` / `allowed_regions` pair. Set all of them to your in-country region and
   re-run `infra/terraform/production_edge.tftest.hcl`, which refuses a region outside the
   allowlist at plan time. See [`runbook.md`](runbook.md).
2. **Identity / IdP.** This repo owns no login flow: the `gcp` profile verifies the IAP-injected
   assertion at the edge, `local` uses seeded dev personas, and `onprem` is a client IdP
   placeholder. Wire your issuer on the deployed service and set `MRM_IAP_AUDIENCE`. An unset or
   emptied audience refuses every caller rather than verifying without one.
3. **The taxonomy.** `domain/taxonomy.py` names the CLASSES of quantitative model your second line
   governs, the TIER a model can land in, and the LEVEL vocabulary the tiering dimensions are
   declared in. Every member is a `LenientStrEnum`, so a value from a future release does not
   crash the reader and you extend the vocabulary without editing an engine.
4. **The packs, which are the policy.** `domain/packs.py` is the single home for the numbers, in
   the same named-bundle shape Hrz4 uses: per model class, how the four tiering dimensions score
   and where the bands fall (`TIERING_PACKS`); which statistics the battery requires and at what
   bar (`BatteryPack`); and the monitoring severity ladder (`MonitoringPack`). Your model-risk
   policy owner sets these. Keep the two fail-closed rules the tiering engine encodes: an
   undeclared or unparseable dimension scores at `FAILSAFE_LEVEL` (HIGH), so a thin record cannot
   tier itself down, and a red breach on a tier-1 model escalates a further step.
5. **The battery's honesty rules.** A missing input is a named GAP, never a pass, and the battery
   does not go GREEN while a required test has no data; `stats.py` raises rather than returning a
   plausible number. Keep both. They are the reason a validation result can be shown to a
   regulator.
6. **Reference data is fictional.** Every fixture and the golden set use obviously fake model
   names and `.example` domains. Replace them with your own synthetic data. **Do not run against a
   real model inventory without your own security and model-risk sign-off.**
7. **Eval golden set.** Rebuild the golden dataset for your taxonomy and packs: a fork inherits a
   green gate that measures the WRONG standard until you do. The metrics (`tier_accuracy`,
   `pii_safety`) and their thresholds are generic; the golden cases are yours. The battery's
   reference statistics in `tests/unit/test_battery_stats.py` are pinned to independently computed
   figures and each is proved able to move: keep that property.
8. **Deployment posture.** Review the Dockerfile (digest-pinned base, non-root uid 10001),
   `infra/terraform/` (Org Policy, CMEK, a dry-run-first VPC-SC perimeter, the locked WORM log
   bucket) and the loopback-by-default binding before you expose anything. The WORM lock is
   irreversible: confirm `retention_days` before the first apply.

## 5. Do not duplicate the platform

This repo is one system in a catalog of composable GRC systems, and its scope boundary is the
important one to get right (see [`faq/features-faq.md`](faq/features-faq.md) for the full map):

- **Hrz4** AI quality and model risk owns **AI and agent** model risk and the promotion gate. This
  repo owns **quantitative, non-AI** models. Two inventories for the same model is the failure
  both systems exist to prevent, so decide which side of that line each model sits on and record
  it once. `eval/run_eval.py --mode gate` still asks Hrz4 about THIS service's own promotion.
- **Rgc7** obligations and control mapping owns the obligation graph. `domain/obligations.py`
  builds the typed edges this repo PROPOSES into it (`RGC7_OBLIGATIONS_URL`), always in the
  `PROPOSED` state, because Rgc7 counts only human-accepted edges. A machine proposal from here
  must never inflate a coverage figure.
- **Hrz7** human-review / maker-checker console: every `requires_human_review` result is routed to
  it over the shared `review-kit` (rule R8); you wire your endpoint
  (`HUMAN_REVIEW_URL`), you do not re-implement the console.
- **Hrz5** observability plus immutable WORM audit: audit events and trace spans go to it.
- **Hrz3** agent registry: this agent publishes its A2A card at
  `/.well-known/agent-card.json`; register it rather than inventing a discovery mechanism.

The guardrail gateway (Hrz1) and the enterprise knowledge base (Hrz2) are **not** integrated, and
today there is nothing to integrate them with: no model call happens in this service at all. See
[`model-card.md`](model-card.md).

## 6. Adoption checklist

- [ ] Ran `scripts/rename_fork.py`, recreated the venv, `make gate` green.
- [ ] Set the region in all three places (settings, `render.tf.json`, tfvars) and re-ran the
      Terraform residency tests.
- [ ] Wired your IdP audience on the deployed service (this repo owns no login flow).
- [ ] Replaced the taxonomy with your model classes, tiers and level vocabulary.
- [ ] Owned every pack in `domain/packs.py` with your model-risk policy owner, keeping the
      fail-closed tiering rules and the missing-input-is-a-gap rule.
- [ ] Agreed the Hrz4 boundary: which models are AI (theirs) and which are quantitative (yours).
- [ ] Replaced every synthetic fixture and re-pinned the battery reference statistics.
- [ ] Rebuilt the eval golden set for your standard.
- [ ] Reviewed the deploy posture (Dockerfile, Terraform, `retention_days`, bind address).
- [ ] Wired your Hrz7 review endpoint and your Rgc7 register endpoint.
- [ ] Read [`model-card.md`](model-card.md) before wiring any drafting model, and met its
      conditions first.
- [ ] Recorded your baseline upstream tag so you can take future fixes.
