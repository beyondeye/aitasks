---
priority: high
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: [t1427_3]
issue_type: documentation
status: Implementing
labels: [shadow, aitask_monitormini, aitask_monitor]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1159
implemented_with: claudecode/opus5
created_at: 2026-08-05 17:18
updated_at: 2026-08-09 10:26
---

Documentation for the t1427 concern-rejection feature. Depends on t1427_1..3
(store, picker tri-state, producer suppression all landed). Parent plan
`aiplans/p1427_reject_shadow_concerns_suppress_next_round.md` is binding.
Document CURRENT SOURCE, not the plan — re-verify behavior against the landed
implementation before writing.

## Surfaces

- `website/content/docs/workflows/shadow-agent.md` — concern block +
  selective-forwarding sections: describe reject (`r`), the rejected-store
  view (`R`) with un-reject, the per-task store, and the next-round
  suppression with its visible "Suppressed N previously-rejected concern(s)."
  report and fail-open (unsure → kept, with reason) behavior.
- `website/content/docs/tuis/minimonitor/how-to.md` — "How to Pick Shadow
  Concerns" + keybinding table: add `r` / `R`; REMOVE the deleted `a` / `A`
  bulk shortcuts wherever mentioned.
- `website/content/docs/tuis/monitor/how-to.md` and `reference.md` —
  equivalents; same a/A scrub.
- `aidocs/framework/shadow_agent.md` — new `## Concern rejection store`
  section between "Feedback freshness" (ends ~:339) and "Configuration"
  (~:341): store path/format, helper subcommands, TUI write path, producer
  consult path, archive-time pruning. FRAME AS PRODUCER-SIDE FILTERING, NEVER
  A GATE — the doc's "no gating on followed-agent state" principle (~:366-390)
  forbids anything that decides whether the user may proceed. Also: one
  sentence in the Step 2 bullet (~:107) and the sub-procedure list
  (~:110-142).

## Constraints

- Un-reject is presented as TUI-only. The helper's `remove` subcommand is
  machinery invoked by the TUI — do NOT document it as a user-facing CLI.
- Per documentation_conventions.md: current-state-only prose (no version
  history), genericize agent references where applicable.
- Sweep every keybinding table / help reference for the removed `a`/`A`
  shortcuts — the picker now offers only per-row forward/reject plus
  confirm/cancel.

## Verification

- `cd website && hugo build --gc --minify` builds clean.
- Grep the docs tree for lingering references to the picker's `a`/`A`
  shortcuts and for "copy all" wording tied to the concern picker.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-09T07:26:34Z status=pass attempt=1 type=human
