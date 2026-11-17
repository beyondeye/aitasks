---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [tui, website, screenshots]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2278
followup_kind: upstream_defect
implemented_with: codex/gpt6_1_sol
created_at: 2026-11-17 09:56
updated_at: 2026-11-17 22:19
completed_at: 2026-11-17 22:19
---

## Origin

Spawned from t2278_4 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/agent_command_screen.py:1278-1282` — `_build_tmux_config` reads the tmux-tab session `Select.value` before it is populated right after the dialog opens, so an early `r` is refused with "Please select a session" (fast typists and replayed recipes both hit it)

## Diagnostic context

While recording the docs screenshot scenes (t2278_4), the board's pick
dialog (`build_pick_screen` → `AgentCommandScreen`) sometimes ignored `r`
pressed right after the dialog appeared: the dialog stayed open, and a toast
"Please select a session" was shown, even though the Session field displayed
the right session (`lumen`). Measured with a scripted harness: 1 drop in 9
second picks in a fresh session; 0 in 20 once the driver waited until the
session Select displayed its value before pressing `r`.

`on_mount` populates the tmux tab (`_populate_tmux_tab`, which runs a tmux
subprocess on the UI thread), switches the active tab to tmux, and defers
`_on_window_changed` with `call_after_refresh`. The first frame can show the
tmux tab (with "(R)un in tmux") while `#tmux_session_select.value` is still
`Select.NULL`; `action_run` → `run_tmux` → `_build_tmux_config` then hits the
`else` branch and refuses. A user who presses `r` quickly after `p` (the
dialog's documented flow) can hit the same refusal.

The docs-screenshot recipes now work around it by waiting for the Select to
display the session name before `r` (see the archived plan of t2278_4).

## Suggested fix

Resolve the session from the dialog's own state when the Select has not yet
reported a value (`self._selected_session`, set synchronously in
`_populate_tmux_tab`), or defer handling `run` until the tmux tab's widgets are
mounted and valued, instead of refusing. A test should press `r` in the first
frame after the dialog mounts.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-17T20:05:28Z status=pass attempt=1 type=human
>
> Note: approval:21817ddda1704f858117f22563465af4:205a2916221024df

> **🔄 gate:risk_evaluated** run=2026-11-17T20:09:01Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:94fa29966cd123cb

> **✅ gate:risk_evaluated** run=2026-11-17T20:09:01Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2323/risk_evaluated_2026-11-17T20:09:01Z-risk_evaluated-a1.log`

> **✅ gate:review_approved** run=2026-11-17T20:17:26Z status=pass attempt=1 type=human
>
> Note: approval:469a4f28817e4040b7375d4d14620350:cb7a067867a2ff18
