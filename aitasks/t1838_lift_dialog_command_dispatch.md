---
priority: low
effort: low
depends: []
issue_type: refactor
status: Ready
labels: [ait_brainstorm, tui]
anchor: 1823
followup_kind: risk_mitigation
created_at: 2026-09-18 12:27
updated_at: 2026-09-18 12:27
---

## Origin

Risk-mitigation ("after") follow-up for t1823_4, created at Step 8d after implementation landed.

## Risk addressed

code-health — third copy of the dialog full_command sh -c dispatch

- A third copy of the "dispatch the dialog's `full_command` via `sh -c` in a terminal or under suspend" pattern (board trail screen, board, now brainstorm) · severity: low · → mitigation: lift_dialog_command_dispatch

## Goal

Lift the "dispatch an `AgentCommandScreen` result's finalized `full_command` via `["sh", "-c", cmd]` in a new terminal (`find_terminal` + `spawn_in_terminal`), else inline under `app.suspend()` + `subprocess.call`" pattern into one shared helper under `.aitask-scripts/lib/` (e.g. alongside `agent_launch_utils.py`), and migrate the callers:

- `board/board_trail_screen.py` `run_dialog_command` (the t1225 fix; keeps its `@work`, error notice and `_after_dialog_command` refresh hook — only the argv/dispatch core moves);
- `brainstorm/brainstorm_app.py` `_run_dialog_command` / `_dispatch_argv` (t1823_4; synchronous, cwd = repo root);
- any other `AgentCommandScreen` "run" branch still rebuilding or re-implementing the dispatch (grep `spawn_in_terminal(` / `self.suspend()` across `.aitask-scripts/`).

Keep the invariant the t1225 and t1823_4 regressions pin: the dispatched argv is the dialog's `screen.full_command` verbatim. Existing tests (`tests/test_brainstorm_discuss_launch.py` finalized-command cases, the board's run_dialog_command tests) must stay green; add a unit test for the helper's terminal vs suspend branches.
