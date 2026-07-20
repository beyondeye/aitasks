---
priority: medium
effort: medium
depends: [1158]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [1158]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-07-20 00:16
updated_at: 2026-07-20 12:23
boardidx: 20
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1158

## Verification Checklist

- [x] [t1158] Tier auto-detection from free text: "quick review" → quick; unqualified "adversarial review" (or "basic"/"legacy"/"default") → default; "advanced review" (or "standard") → advanced; "deep review" → deep; a generic "review the implementation" prompts with Advanced recommended — PASS 2026-07-20 12:23 auto: inspected tier-routing rules in impl-challenge.md; all required free-text mappings and generic Advanced recommendation are present
- [x] [t1158] Default tier runs the one-to-one legacy three-axis review (S0 implementation flaws, S1 unmitigated risks, S2 unjustified deviations) as a single full-context pass — PASS 2026-07-20 12:23 auto: inspected Default tier contract; it specifies one full-context S0/S1/S2 pass with no verdict ladder or finding cap
- [x] [t1158] Advanced and Deep findings carry verdicts (CONFIRMED/PLAUSIBLE); all tiers carry disposition tags (blocking/follow-up); findings ordered blocking-first, severity within partition — PASS 2026-07-20 12:23 auto: inspected findings contract; Advanced/Deep require CONFIRMED/PLAUSIBLE and all tiers use disposition-first ordering
- [x] [t1158] Single 4-option tier chooser renders and works on a Codex shadow (request_user_input, verified capable on v0.144.6 — PASS 2026-07-20 12:23 auto: live Codex request_user_input check displayed four tier choices and returned Advanced
- [defer] [t1158] For a generated Advanced or Deep review in minimonitor: concern auto-offer triggers; picker opens in blocking-first order; disposition and verdict text show in each concern body; selected concerns forward to the followed agent unchanged; concern regions stay short (basename.ext:LINE, no full paths) — DEFER 2026-07-20 12:23 auto: focused minimonitor concern tests passed, but no generated Advanced/Deep shadow review was available in a live minimonitor pane for end-to-end confirmation
