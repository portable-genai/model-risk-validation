# Compliance FAQ

For model risk, compliance and the second line. The mapping table with a file reference on every
row is [`../../COMPLIANCE.md`](../../COMPLIANCE.md); this page answers the questions that come
back after reading it.

### Is a tier from this system defensible in front of a regulator?

That is the reason it is pure code. The four declared dimensions are scored by the model class's
`TieringPack`, summed with the pack's weights and banded, with the score recorded on the
assessment, so the same record always produces the same tier and the decision can be replayed
years later from the audit record. Two fail-closed rules make it trustworthy under incomplete
data: an undeclared or unparseable dimension scores at `FAILSAFE_LEVEL` (HIGH), so a thin record
cannot tier itself down; and a red breach on a tier-1 model escalates a further step because a red
on a material model is a critical, dual-control event.

### And a battery verdict?

Same principle, plus one rule that matters more than the arithmetic: **a missing input is a named
GAP, never a pass.** The battery does not go GREEN while a required test has no data, and
`domain/battery/stats.py` raises rather than returning a plausible number on an input it cannot
honestly score. A fabricated statistic in a validation report is worse than an admitted gap, and
the code is written so that the honest outcome is the only reachable one. The reference values are
pinned in `tests/unit/test_battery_stats.py` against independently computed figures, each proved
able to move off its figure.

### Who signs off?

A human, always, for anything consequential. `requires_human_review` and the call to
`ReviewRouterPort.route` are one act, not a flag plus an intention: the API, the CLI and the agent
tool all route in the same call that produced the result, and `tests/unit/test_review_routing.py`
asserts the routing rather than the flag. Under the managed profile the router REFUSES when no
console is configured, so a deployment cannot swallow an escalation silently. The proposed Rgc7
edges follow the same discipline: they are `PROPOSED`, and coverage in Rgc7 counts only edges a
human accepted.

### Where does this stop and Hrz4 start?

This repo governs **quantitative, non-AI** models. Hrz4, the AI-quality and model-risk platform,
governs **AI and agent** models and owns the promotion gate. Keeping one model in both inventories
is the failure the boundary exists to prevent, so the population split has to be an explicit,
recorded decision in your model-risk policy rather than an implementation detail. Note that Hrz4
is also this service's own promotion authority, which is a separate relationship.

### Where does the data live, and is residency enforced or just documented?

Enforced at deploy time. The region is chosen once (`asia-southeast1`) and shared by the runtime
and Terraform: `infra/terraform/variables.tf` validates the region against the residency allowlist
at plan, `org_policy.tf` pins `gcp.resourceLocations` to that region's location group, and every
regional resource (the CMEK key ring, the WORM log bucket, the Cloud Run service) is created in
it. `infra/terraform/production_edge.tftest.hcl` is the standing proof: its
`reject_region_outside_the_residency_allowlist` and `residency_defaults_are_in_country` runs fail
if the allowlist stops refusing or a resource drifts off region, and they run against a mocked
provider so they need no project and no credentials.

### What about key management and least privilege?

One REGIONAL CMEK key with a 90-day rotation, and an explicit key binding for EACH service agent
that encrypts under it, because CMEK does not cascade (`infra/terraform/kms.tf`). One serving
identity holding only the roles a request needs, each traceable to a bound adapter, with
`logging.logWriter` write only so the process cannot read back the WORM trail it writes
(`iam.tf`). Exportable service-account keys are forbidden by org policy rather than merely
avoided, and a key creation raises an alert if one happens anyway (`org_policy.tf`,
`monitoring.tf`).

### How long is the audit trail kept, and can it be edited?

180 days by default, and the variable refuses anything below 180. The Cloud Logging bucket is
LOCKED by default, which is irreversible: once applied, retention cannot be reduced and the bucket
cannot be deleted for the full window, not even with project-owner rights. Confirm
`retention_days` before the first apply. DATA_READ audit logging is enabled too, so a read of a
validation record is itself recorded. Offline the same guarantee is earned by a hash-chained,
externally anchored log. The retention schedule and the legal basis are adopter-owned, and for a
model-risk function they usually need to outlast 180 days: set `retention_days` to your own
standard before the first apply, because the lock cannot be loosened afterwards.

### What model-risk evidence exists for this system itself?

[`../model-card.md`](../model-card.md), and its headline is that there is no model in the path: no
generation port, no generation adapter, no prompt sent anywhere. Every number this service
produces is deterministic stdlib. That makes the model-risk question about THIS service unusually
simple today, and it is the state to preserve deliberately rather than to drift out of: the card
lists what must be true before a drafting model is bound.

### Which regulations does this claim to satisfy?

None, on your behalf. The mapping in `COMPLIANCE.md` is to the CATALOG's own principles (P-01 to
P-13) and platform rules (R1 to R8). The crosswalk from those to SR 11-7, MAS TRM, CPS 234 or your
own model-risk standard, and the judgement that a control is SUFFICIENT, is explicitly
adopter-owned. No row should be quoted as regulatory assurance, and the second-line review of the
packs in `domain/packs.py` is bank-owned policy rather than a vendor default to inherit
unexamined.

### What is still open at go-live?

The `Partial` and `TODO (repo owner)` rows in `COMPLIANCE.md`, each of which names exactly what is
missing. The ones that need a risk acceptance if you go live without them: rule R5 and P-08 (the
Hrz4 metric bundle), P-10 (timeouts, circuit breaker and a documented kill switch for the outbound
register and console calls), and P-01's private-egress rule, which depends on your own network
rather than on this repo.
