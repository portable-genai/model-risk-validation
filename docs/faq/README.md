# FAQ index

Answers to the questions different teams ask when evaluating, adopting or reviewing this
repository as a second-line model-risk base for quantitative, non-AI models. Each file is written
for a specific audience; skim the one that matches your role.

| FAQ | For | Answers |
|---|---|---|
| [security-faq.md](security-faq.md) | AppSec / security review | server-side identity, the exposure guard, secrets, supply chain, the audit chain, why there is no model surface to attack |
| [portability-faq.md](portability-faq.md) | Architecture / cloud / exit planning | no-lock-in, the three profiles, the sovereign exit, why the statistics move unchanged |
| [features-faq.md](features-faq.md) | Product / risk / delivery | what the tiering, battery and monitoring engines compute, and the boundary with `model-quality-gate` and `obligations-control-mapping` |
| [adoption-faq.md](adoption-faq.md) | Engineering leads forking the repo | rename, upstream fixes, the packs, what stays open |
| [compliance-faq.md](compliance-faq.md) | Model risk / compliance / second line | why a tier and a battery verdict are defensible, maker-checker, residency, retention |

These FAQs deliberately do **not** re-document capabilities owned by sibling systems in the GRC
catalog. Where a concern belongs to another repo (AI model risk and promotion `model-quality-gate`, the obligation
graph `obligations-control-mapping`, the human-review console `human-review-console`, observability and the WORM sink `agent-observability`), the FAQ points
at it and explains the boundary rather than duplicating it. See
[features-faq.md](features-faq.md) for the full "what this repo owns vs what it integrates" map.

Authority order for anything these pages disagree with: [`SPEC.md`](../../SPEC.md), then
[`ARCHITECTURE.md`](../../ARCHITECTURE.md), then [`COMPLIANCE.md`](../../COMPLIANCE.md), then
[`README.md`](../../README.md). These pages restate; they do not decide.
