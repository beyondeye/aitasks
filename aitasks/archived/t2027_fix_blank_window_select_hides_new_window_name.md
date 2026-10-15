---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [tui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2013
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-16 00:50
updated_at: 2026-10-16 01:06
completed_at: 2026-10-16 01:06
---

## Origin

Spawned from t2025 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/agent_command_screen.py:1294-1297` — on an existing
  session, choosing the window Select's blank entry (`allow_blank=True`) hides
  both the window-name row and the split row, yet `_build_tmux_config` falls
  through to "Default to new window" and launches a new window under the
  hidden default name. A hidden control decides the launch, the same class of
  problem as t2025, reached through the blank option instead of the
  new-session path.

(Line numbers as of commit 2874e66ea.)

## Diagnostic context

t2025 fixed the new-session path: `_on_window_changed` now shows
`#tmux_new_window_row` whenever `value == _NEW_WINDOW_SENTINEL` or the session
Select holds `_NEW_SESSION_SENTINEL` (`_new_session_pending()`). That mirrors
`_build_tmux_config`, which reads `#tmux_new_window_input` when
`new_session or win_select.value == _NEW_WINDOW_SENTINEL`.

A third launch branch is still out of step with the visible controls. The window
Select is built with `allow_blank=True`, so its overlay offers a blank entry.
Choosing it on an existing session sets the value to `Select.NULL`.
`_on_window_changed`'s else-branch then hides both the window-name row and the
split row. `_build_tmux_config`'s final `else` ("Default to new window") still
launches `new_window=True` with `window = self.default_window_name or "aitask"`,
a name the user can neither see nor edit at that point.

## Suggested fix

Make the blank window choice and the launch agree. One option is to treat
`Select.NULL` on an existing session like `_NEW_WINDOW_SENTINEL` in
`_on_window_changed`, so the name row shows. Another is to build the window
Select with `allow_blank=False`, but check what the new-session path's
`set_options([])` and `clear()` need before choosing it. Add a test beside
t2025's in `tests/test_agent_command_dialog_narrow.py`: blank the window Select
on an existing session, then assert that the visible rows match the
`TmuxLaunchConfig` produced by `r`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-15T21:58:34Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-15T22:04:34Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-10-15T22:06:00Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:31e7af85d1f42c54

> **✅ gate:risk_evaluated** run=2026-10-15T22:06:00Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2027/risk_evaluated_2026-10-15T22:06:00Z-risk_evaluated-a1.log`
