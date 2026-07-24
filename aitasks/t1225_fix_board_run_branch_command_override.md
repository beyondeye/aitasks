---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [ui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1162
implemented_with: claudecode/opus4_8
created_at: 2026-07-24 10:28
updated_at: 2026-07-24 14:45
---

## Origin

Spawned from t1162_4 during Step 8b review.

## Upstream defect

- `.aitask-scripts/board/aitask_board.py:5696,5866 — the pick "run" result callbacks (and the brainstorm :6006, resume :6179, create :6308 branches) call run_aitask_pick / rebuild default wrapper args instead of dispatching the dialog's stored screen.full_command, silently discarding in-dialog command edits and agent/profile overrides.`

## Diagnostic context

t1162_4 added the board `w` (Work Report) flow. During its plan review (Change
Request 1) it was found that `AgentCommandScreen.run_terminal()` stores user
command edits into `screen.full_command`, and the dialog's agent/profile
controls regenerate that command. The "run" (run-in-terminal) result branch
must therefore dispatch `screen.full_command`, NOT rebuild default wrapper
args — otherwise in-dialog edits and agent/profile overrides are silently
discarded (the tmux path already honored them). t1162_4 fixed this for the new
work-report action (`run_work_report(screen.full_command)`), but the same
pre-existing flaw remains in the board's other "run" result callbacks:

- `on_pick_result` (~5696 and ~5866) → `run_aitask_pick(filename)` rebuilds
  the pick wrapper argv from the task filename.
- brainstorm (~6006), resume (~6179), create (~6308) "run" branches follow the
  same filename-/default-arg pattern.

Each rebuilds the default command instead of honoring the dialog's stored
`full_command`, so a user who edits the command or switches agent/model in the
AgentCommandScreen and then chooses "run" (rather than the tmux launch) gets
the default, not their override.

## Suggested fix

Route each board "run" result branch through the dialog's stored
`screen.full_command` (dispatched via the `["sh", "-c", full_command]` worker
pattern, mirroring `run_work_report`), rather than reconstructing default
wrapper args. Where a filename-scoped refocus/reload is still wanted (pick),
preserve that side effect while dispatching the stored command. Add
construction-spy tests mirroring t1162_4's
`test_run_result_dispatches_dialog_command_not_pick`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-24T11:45:21Z status=pass attempt=1 type=human
