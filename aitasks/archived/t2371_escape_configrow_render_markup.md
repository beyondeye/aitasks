---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [tui, execution_profiles]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2363
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-11-27 01:18
updated_at: 2026-11-27 10:37
completed_at: 2026-11-27 10:37
---

## Origin

Spawned from t2363 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/profile_editor.py:639-641` — `ConfigRow.render` (the non-compact form, used by the settings TUI Profiles tab and by the wide `ProfileEditScreen`) interpolates `self.key` / `self.value` into Rich markup unescaped. A profile string value containing markup such as `[/bold]` raises `MarkupError` on render. `CycleField.render` already escapes its label and options for exactly this reason (see its comment).

## Diagnostic context

t2363 added a compact `ConfigRow` render for the narrow profile editor, which wraps key and value in `escape()`. The wide and subordinate forms were left unchanged, out of t2363's scope. Values come straight from profile YAML (`default_email`, `description`, CSV lists), so any of them can carry text that the renderer parses as markup.

## Suggested fix

Wrap `self.key`, `self.value` (and the subordinate form's `self.value`) in `rich.markup.escape` inside `ConfigRow.render`. Add a test that renders a row whose value is `"[/bold]x"` in both the settings TUI and `ProfileEditScreen`. Also check `settings_app.py` for its own `ConfigRow` uses.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-27T06:37:30Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-27T08:34:23Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-11-27T08:37:39Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:2eeafb364c94147e

> **✅ gate:risk_evaluated** run=2026-11-27T08:37:39Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2371/risk_evaluated_2026-11-27T08:37:39Z-risk_evaluated-a1.log`
