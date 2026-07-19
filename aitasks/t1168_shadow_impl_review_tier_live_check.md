---
priority: medium
effort: medium
depends: [1158]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1158]
created_at: 2026-07-20 00:16
updated_at: 2026-07-20 00:16
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1158

## Verification Checklist

- [ ] [t1158] Tier auto-detection from free text: "quick review" → quick; unqualified "adversarial review" → basic; "standard review" → standard; "deep review" → deep; a generic "review the implementation" prompts with Standard recommended
- [ ] [t1158] Basic tier runs the one-to-one legacy three-axis review (S0 implementation flaws, S1 unmitigated risks, S2 unjustified deviations) as a single full-context pass — no verdict ladder, no findings cap
- [ ] [t1158] Standard and Deep findings carry verdicts (CONFIRMED/PLAUSIBLE); all tiers carry disposition tags (blocking/follow-up); findings ordered blocking-first, severity within partition
- [ ] [t1158] Deterministic two-stage tier chooser on a 3-option-capped agent (Codex shadow): Stage 1 Standard/Basic/Other, Stage 2 Quick/Deep
- [ ] [t1158] For a generated Standard or Deep review in minimonitor: concern auto-offer triggers; picker opens in blocking-first order; disposition and verdict text show in each concern body; selected concerns forward to the followed agent unchanged; concern regions stay short (basename.ext:LINE, no full paths)
