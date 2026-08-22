# Adoption FAQ

For an engineering lead forking this repo as their institution's model-risk base. The
step-by-step is [`../ADOPTING.md`](../ADOPTING.md); this answers the "will it hurt later?"
questions.

### How do I rebrand it for my organisation?

`scripts/rename_fork.py` rewrites the package name (`model_risk_validation`, which is also the console
script), the `MRM_` env prefix (including the bare token that
`infra/terraform/render.tf.json` carries, so Terraform sets the same variable names on the
service), the Terraform `name_prefix` resource stem (`mrm1-svc`) and the distribution / git id in
one pass. Preview with `--dry-run`, apply with `--yes`, then recreate the venv, `make install`,
and run `make gate`. The catalog id `Mrm1` is left alone unless you pass `--catalog-id`, so a fork
stays traceable to the entry it descends from. The script does the mechanical rename; the human
decisions (region, IdP, the taxonomy, the packs, the eval golden set) are the checklist in
`ADOPTING.md`.

### If several institutions fork this, how does each take upstream fixes?

Track upstream via **git tags**. The repo declares a core-vs-adopter-owned boundary
(`ADOPTING.md` section 2): upstream owns `domain/kernel.py`, `domain/battery/stats.py`, `ports/`,
`tests/contract/`, the eval harness mechanics, CI and the Terraform stack; you own
`config/settings.yaml` values, every pack in `domain/packs.py`, the taxonomy, the fixtures and the
golden set, `adapters/onprem/*`, UI theming and `terraform.tfvars`. Rebase your adopter-owned
changes onto each release rather than merging `main` continuously, so conflicts stay in files you
were told to expect.

### Can I retune the policy without touching engine code?

Mostly yes, and this is the repo's best-kept property. `domain/packs.py` is packs-as-data in the
same named-bundle shape Hrz4 uses: `TIERING_PACKS` holds how each model class scores the four
dimensions and where the bands fall, the `BatteryPack` holds which statistics are required and at
what bar, and the `MonitoringPack` holds the severity ladder. A policy change is a data edit
there, not a code edit in an engine.

The honest limit: the packs are module-level constants rather than a `policy:` block in
`config/settings.yaml` with a `from_policy(...)` constructor, so a deployment cannot carry its own
pack without a code change, and the eval thresholds and PII jurisdictions are constants too. That
is the open B4 item in [`../practices-audit.md`](../practices-audit.md).

### What do we have to supply that is not in this repo?

Three things, and none of them is code here:

1. **The model inventory.** Real records, with the four tiering dimensions declared.
2. **The validation samples.** The battery scores what it is given; supplying the model's real
   samples, and vouching for them, is yours.
3. **The endpoints.** An Rgc7 register at `RGC7_OBLIGATIONS_URL` for the proposed edges, and an
   Hrz7 console at `HRZ_HUMAN_REVIEW_URL`. The managed router REFUSES to swallow an escalation
   when the console is unset, so a fork cannot ship rule R8 unwired and green.

### How do I add a new outbound dependency (a new port)?

There is a fixed touch list and a contract test that enforces it. A port must be registered in
FIVE places or it runs with no enforcement at all: `ports/__init__.py` (`PORT_PROTOCOLS`),
`config.DEFAULT_BINDINGS`, a `Container` accessor, `config/settings.yaml`, and a `PortCase` in
`tests/contract/canonical.py`. Then bind it in all three families.
`tests/contract/test_port_parity.py` asserts set equality across the five. Two ports a real
deployment will want are exactly this job: a generation seam for the drafting contract, and the
model-documentation extraction seam the inventory engine's docstring anticipates. See
[`../../CONTRIBUTING.md`](../../CONTRIBUTING.md).

### There is a drafting contract but no model. Is that a bug?

It is a deliberate half-build, and it is worth understanding before you plan.
`domain/prompts.py` defines the allowed-figure set, the prompt facts and a validator that discards
any draft introducing a number the engine did not produce. What does not exist is a
`GenerationPort` or any adapter, so nothing calls a model and the contract is exercised only by
its unit test. The upside is that the service is fully deterministic today; the work to finish it
is one port plus three adapters plus the controls in [`../model-card.md`](../model-card.md).

### Does the gate run for my fork out of the box?

Yes. `make gate` is offline, credential-free and network-free (ruff, ruff format, mypy strict, the
whole suite except integration, and the eval), and the CI workflow references no `secrets.`, so a
fork's build is green immediately. You add secrets only when you wire the `gcp` profile. Note the
eval measures the REFERENCE packs and golden cases until you rebuild them for your own standard;
that is an explicit adoption step, not a silent pass.

### The eval reports high scores. Should we believe them?

Only because each metric is proved able to report something else.
`tests/unit/test_not_falsely_green.py` hands the metrics planted mutants and fails the build if
they still pass. The battery's own statistics are held separately, by reference values in
`tests/unit/test_battery_stats.py` computed independently of the implementation, each proved able
to move off its figure.

### Will the demo rot after I diverge?

It is guarded, and the guard is inside the gate. A demo step lives in `demo.STEPS` and in
`walkthrough.CHECKS`, and `tests/unit/test_demo_surface.py` holds the two equal, so a claim the
demo makes but nobody verifies cannot exist. `make demo-selftest` runs the whole arc headless over
the real loopback server and exits non-zero when a claim stops being true. If you diverge, keep
the step keys and the `facts` dict the checks read.

### What is still open?

[`../practices-audit.md`](../practices-audit.md) carries the per-check verdict and the work list.
The largest items before production: the drafting seam and its controls, the model-documentation
extraction port, and registering this repo's metric bundle with Hrz4 so `eval/run_eval.py --mode
gate` has an authority to ask. The Terraform stack is written, validated and tested against a
mocked provider; it has never been applied.
