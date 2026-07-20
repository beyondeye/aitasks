---
priority: medium
effort: medium
depends: [1158]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1158]
created_at: 2026-07-20 00:16
updated_at: 2026-07-20 09:30
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1158

## Verification Checklist

- [ ] [t1158] Tier auto-detection from free text: "quick review" → quick; unqualified "adversarial review" (or "basic"/"legacy"/"default") → default; "advanced review" (or "standard") → advanced; "deep review" → deep; a generic "review the implementation" prompts with Advanced recommended
- [ ] [t1158] Default tier runs the one-to-one legacy three-axis review (S0 implementation flaws, S1 unmitigated risks, S2 unjustified deviations) as a single full-context pass — no verdict ladder, no findings cap
- [ ] [t1158] Advanced and Deep findings carry verdicts (CONFIRMED/PLAUSIBLE); all tiers carry disposition tags (blocking/follow-up); findings ordered blocking-first, severity within partition
- [ ] [t1158] Single 4-option tier chooser renders and works on a Codex shadow (request_user_input, verified capable on v0.144.6 — re-confirm in the live flow; no two-stage adaptation expected)
- [ ] [t1158] For a generated Advanced or Deep review in minimonitor: concern auto-offer triggers; picker opens in blocking-first order; disposition and verdict text show in each concern body; selected concerns forward to the followed agent unchanged; concern regions stay short (basename.ext:LINE, no full paths)
