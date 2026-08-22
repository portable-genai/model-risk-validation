# Portability FAQ

For architecture, cloud governance and exit planning. The question underneath all of these is
"how do we leave, and how do we know the answer is true today rather than on the day it was
written?"

### What is the lock-in surface?

Small, and smaller than most systems in the catalog. Every outbound dependency is a
`@runtime_checkable` Protocol in `ports/` (audit, identity, obligations, observability, review
router), bound per profile from `config/settings.yaml`. There is no cloud SDK import anywhere in
`domain/`, and the managed adapters import their SDK LAZILY inside the method, so the other two
families import with no SDK installed at all. There is also no model: the statistics are pure
stdlib, so the consequential part of this service depends on nothing but Python.

### What are the three profiles?

| Profile | What it is | Who it is for |
|---|---|---|
| `local` | SDK-free offline stack: seeded dev personas, a hash-chained SQLite WORM audit log, in-process obligation and review sinks | dev, test, CI, and the offline demo |
| `gcp` | the managed stack: IAP identity, Cloud Logging WORM, HTTP clients to the Rgc7 register and the Hrz7 console | a managed deployment |
| `onprem` | fail-fast `NotImplementedError` placeholders | the sovereign exit: a client binds its own in-country implementations here |

`MRM_PROFILE` selects the family. Unset means the offline adapters bind but nobody chose them,
which withdraws every relaxation rather than granting one.

### Is the portability claim tested, or just documented?

Tested, three ways, all in the offline gate or one command:

- `tests/contract/test_port_parity.py` asserts set equality across all five homes of a port (the
  `PORT_PROTOCOLS` map, `config.DEFAULT_BINDINGS`, the `Container` accessor, `settings.yaml` and
  the canonical-call table), so a port cannot be added in four places and run unenforced.
- `tests/contract/test_behavioral_parity.py` proves the offline family ANSWERS, the on-premises
  family RAISES and the managed family REFUSES rather than silently succeeding. A placeholder that
  quietly returned a default would make the exit claim false while looking green.
- `make portability` is the executable claim: named checks with a pass or fail each, exiting
  non-zero on any failure. The stronger SDK-free proof lives in
  `tests/contract/_sdk_free_probe.py`, which BLOCKS the `google` import in a fresh interpreter
  rather than hoping the machine has none installed.

### Do the statistics move unchanged?

Yes, and that is the point of writing them in stdlib. `domain/battery/stats.py` uses no numpy and
no scipy, so the authoritative mathematics is a file you can read, port and re-verify anywhere.
Its reference values are pinned in `tests/unit/test_battery_stats.py` against independently
computed figures, so a move during a migration is caught by the test rather than noticed later in
a validation report.

### How do we actually exit?

[`../onprem-migration.md`](../onprem-migration.md) is the path. The short version: the domain is
pure stdlib and moves unchanged; the audit trail exports to and restores from JSON Lines, so the
record of every validation run is a file copy; what you implement is one adapter per port under
`adapters/onprem/`, each of which currently raises with a message naming what to bind. Nothing in
`domain/` has to change, which is the point of the split.

### Is there a model to migrate?

No. Nothing in this service calls a model, so a sovereign exit does not have to find an in-country
inference endpoint before it can run. If you later bind a drafting model, that becomes one more
port and one more exit decision; the conditions are in [`../model-card.md`](../model-card.md).

### Is the data residency claim portable too?

The region is chosen once and shared by the runtime and Terraform:
`config/settings.yaml:region`, `infra/terraform/render.tf.json:render_region`, and the Terraform
`region` / `allowed_regions` pair, which refuses an unapproved region at plan time. Changing
jurisdiction is a configuration change in those three places plus a re-run of
`infra/terraform/production_edge.tftest.hcl`, not a code change.
