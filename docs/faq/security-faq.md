# Security FAQ

For AppSec and security architecture. Every answer names the file that is the evidence, so the
review can read the control rather than the claim.

### Who is the actor on a decision, and can a caller assert it?

A server-verified `Principal`, always. The request schemas carry no `actor` field: the audit actor
and the review maker both come from the identity adapter, and every client-supplied actor, tenant,
role, ACL and authorization header is discarded at the browser boundary
(`ui/lib/embed-policy.mjs`). Under the `gcp` profile the adapter verifies the IAP-injected
assertion against the configured audience, against IAP's own key set and against the issuer
(`adapters/gcp/identity.py`); an unset or emptied `MRM_IAP_AUDIENCE` REFUSES every caller, because
`audience=None` means google-auth does not verify the audience at all and would accept any
Google-signed token from any project.

### How large is the model attack surface?

Zero today, and that is a design statement rather than an accident. There is no generation port
and no generation adapter in any profile, so no prompt is ever sent anywhere and no model output
is ever parsed. The drafting contract in `domain/prompts.py` exists for the day a seam is added
and is exercised only by its unit test. Prompt injection, output filtering and token exhaustion
are therefore not live risks here; they become live the moment a `GenerationPort` is bound, and
[`../model-card.md`](../model-card.md) lists what must be true first.

### What happens if the profile variable goes missing in production?

The process still binds the SDK-free adapters (the alternative is importing cloud SDKs that are
not installed), but nobody chose them, so every relaxation is withdrawn: the seeded dev personas
refuse to construct, no service-to-service scheme is selected, the dev CORS allowlist and the
`X-Dev-Persona` header are gone, the interactive docs are not registered, and the loopback
exposure guard refuses every route to any non-loopback peer. An emptied or mis-capitalised value
raises AT IMPORT, so the process fails to boot rather than serving on a posture nobody chose
(`config.py`, `tests/unit/test_profile_single_source.py`).

### Does setting the service-to-service token open anything?

No, and this is enforced rather than intended. The exposure guard's posture is derived from the
identity BINDING (the adapter declares `VERIFIED` / `CLIENT_ASSERTED` / `UNIMPLEMENTED`), never
from a credential. `MRM_S2S_TOKEN` authenticates a calling SERVICE and no end user.
`tests/unit/test_end_user_auth_posture.py` walks the guard's argument through the constants it
names and fails the build if a credential reappears at any depth, because it did once: setting the
token switched the guard off for the end-user routes it was protecting.

### Where does personal data go?

This service reasons over model records, statistics samples and metric values rather than customer
records, so the personal-data surface is small by construction. What does appear (an owner name,
say) is masked before it crosses any boundary: before the audit write in
`domain/validation_service.py`, before a review payload leaves the process, and before a tool
result returns from `agent/tools.py`. The pattern set and its ORDER are this vertical's
(`domain/pii.py`), drawn from the shared `pii-kit`. The `pii_safety` eval metric holds this at
`>= 0.99` and `tests/unit/test_not_falsely_green.py` proves the metric can go red.

### Can a caller manipulate a tier or a verdict by shaping its input?

Only in the direction that is safe. The tiering engine scores an undeclared or unparseable
dimension at `FAILSAFE_LEVEL` (HIGH), so withholding information makes a model MORE material, not
less; and the battery treats a missing sample as a named gap that keeps the result off GREEN
rather than as a pass. An extracted attribute is validated against the record rather than trusted
(`domain/inventory.py`). What a caller can do is supply samples, so the integrity of the sample
feed is an adopter control rather than an in-repo one.

### How is the audit trail protected?

Append-only and hash-chained, AND externally anchored. The chain catches an edit, a deletion or a
reorder; only the anchor catches a TRUNCATED TAIL, because dropping the newest rows leaves a
shorter chain that verifies perfectly. `audit_anchor_path` (`MRM_AUDIT_ANCHOR`) writes the chain
head to a file on another volume, and `tests/unit/test_audit_anchor.py` proves the detection,
proves the control case goes UNDETECTED without an anchor, and proves an append after truncation
refuses rather than re-anchoring. Under the managed profile the sink is a locked Cloud Logging
bucket (`infra/terraform/logging_worm.tf`), which provides non-rewritability itself.

### What about supply chain?

Both lockfiles are committed and pin every dependency exactly; the catalog commons are pinned to
40-character COMMIT shas rather than tags, because a re-pushed tag changes what installs with no
diff in the lockfile. The base image is digest-pinned, Actions are SHA-pinned, dependabot covers
pip, docker, github-actions and npm, and `pip-audit` plus `npm audit --audit-level=high` are HARD
CI failures. `tests/unit/test_repo_artifacts.py` asserts each of these from inside the repo, and
it asks git whether each pinned sha is a COMMIT object rather than an annotated tag object, which
a regular expression cannot tell apart. Note that the battery's mathematics is pure stdlib: no
numpy, no scipy, so the statistical core adds no third-party attack surface at all.

### What is deliberately out of scope?

- **Login.** This repo authenticates nobody itself: the platform in front of it does, and the UI
  forwards the assertion without parsing or trusting a parsed copy.
- **The sample feed's integrity.** Whoever supplies the validation samples is trusted to supply
  the model's real ones; this service scores what it is given.
- **The review queue.** Owned by Hrz7; this repo produces escalations and routes them.
- **Network egress control.** VPC-SC governs access to Google APIs across perimeters, not
  arbitrary internet egress. The private-egress rule that lets this service reach the Rgc7 register
  and the Hrz7 console and nothing else is an adopter network decision, called out in
  `COMPLIANCE.md` P-01.
