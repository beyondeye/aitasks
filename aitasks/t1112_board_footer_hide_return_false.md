---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [aitask_board]
gates: [risk_evaluated]
anchor: 1016
created_at: 2026-07-02 08:54
updated_at: 2026-07-02 08:54
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
