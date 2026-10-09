---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [codebrowser, tui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1911
followup_kind: upstream_defect
created_at: 2026-10-09 11:34
updated_at: 2026-10-09 11:39
---

## Origin

Spawned from t1915 during Step 8b review.

## Upstream defect

- `.aitask-scripts/codebrowser/codebrowser_app.py:1509` — the explain `AgentCommandScreen` "Run in terminal" (`"run"`) branch calls `_run_agent_command("explain", arg)` (`codebrowser_app.py:1522-1532`), which rebuilds `[wrapper, "invoke", operation, arg]` instead of dispatching `screen.full_command`, discarding the dialog's agent/model/profile changes and any hand edit to the command.
- `.aitask-scripts/codebrowser/history_screen.py:439` — the QA dialog's `"run"` branch does the same via `_run_qa_command(task_id)`.

## Diagnostic context

While adding the missing `"run"` handling to the syncer (t1915), the other `AgentCommandScreen` consumers were surveyed. The board (`board/board_trail_screen.py:run_dialog_command`), brainstorm (`_run_dialog_command`) and tui_switcher dispatch the dialog's stored `screen.full_command` verbatim via `["sh", "-c", full_command]` — the t1225 rule: `run_terminal` stores user edits into `screen.full_command` and the agent/profile controls regenerate it, so rebuilding default wrapper args at the call site silently launches a different configuration from the one shown. Codebrowser's explain and QA paths still rebuild. (Its `action_create_task` `"run"` branch at ~1579 calls `_run_create_from_selection(ref_arg)` — check whether that one has the same issue.)

Note that the tmux branch of the same callbacks already uses `screen.full_command` — only the run-in-terminal branch diverges.

## Suggested fix

Dispatch `["sh", "-c", screen.full_command]` with `cwd=str(self._project_root)` (terminal via `spawn_in_terminal`, else inline under `suspend()`), keeping the rebuild only as the no-dialog fallback. Mind the launch-error lessons from t1915's syncer fix: catch `OSError` from the spawn / inline call (an exception escaping a screen-result callback ends the TUI), and catch it INSIDE `with self.suspend():` — Textual 8.2.7's `App.suspend` resumes the driver with no `finally`. Add tests that set the dialog's `full_command` to a distinct edited value before dismissing with `"run"`.
