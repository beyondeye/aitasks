---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [aitask_board]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1016
created_at: 2026-07-02 08:54
updated_at: 2026-07-03 12:45
---

## Origin

Spawned from t1035 during Step 8b review.

## Upstream defect

`.aitask-scripts/board/aitask_board.py` — several `check_action` branches
(`commit_selected`, `commit_all`, `pick_task`, `brainstorm_task`,
`open_cross_repo`) `return None` with a `# Hide from footer` intent, but under
Textual 8.2.7 `check_action` returning `None` yields `enabled=False` (the key
is shown *greyed*), while only `False` excludes the binding (truly hidden) — see
`Screen.active_bindings` (`if action_state is False: continue`). So these footer
actions are displayed greyed instead of hidden when inapplicable.

## Diagnostic context

While implementing t1035 (By-Topic sort modes), hiding the task/column movement
and `x` toggle-children actions in the derived In-Flight / By-Topic views
required switching those branches from `return None` to `return False`, because
`None` only greyed them. The remaining `# Hide from footer` sites still use
`None` and share the same latent bug. `run_action` gates execution on
`check_action` being truthy, so both `None` and `False` already block the
action from firing — this is a display-only defect (greyed vs hidden).

## Suggested fix

Normalize the remaining `check_action` "Hide from footer" branches
(`commit_selected`, `commit_all`, `pick_task`, `brainstorm_task`,
`open_cross_repo`) to `return False`. Audit for any other `return None`
"hide"-intent sites in `check_action`. Consider a short comment at the top of
`check_action` documenting the Textual 8.2.7 semantics (False = hidden,
None = shown+disabled) to prevent regressions.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **🔄 gate:risk_evaluated** run=2026-07-03T09:46:11Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:411197d686be7a05

> **❌ gate:risk_evaluated** run=2026-07-03T09:46:11Z-risk_evaluated-a1 status=fail attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluation incomplete: plan '## Risk' missing '### Code-health risk' subsection
> Log: `.aitask-gates/1112/risk_evaluated_2026-07-03T09:46:11Z-risk_evaluated-a1.log`

> **🔄 gate:risk_evaluated** run=2026-07-03T09:46:51Z-risk_evaluated-a2 status=running attempt=2 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:a4eb9633eaf356f6

> **✅ gate:risk_evaluated** run=2026-07-03T09:46:51Z-risk_evaluated-a2 status=pass attempt=2 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1112/risk_evaluated_2026-07-03T09:46:51Z-risk_evaluated-a2.log`
