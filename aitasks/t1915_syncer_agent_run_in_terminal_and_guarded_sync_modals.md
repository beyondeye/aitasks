---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [syncer, aitask_board, tui]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1911
followup_kind: upstream_defect
created_at: 2026-10-08 16:16
updated_at: 2026-10-08 16:56
---

## Origin

Spawned from t1911 during Step 8b review.

## Upstream defect

- `.aitask-scripts/syncer/syncer_app.py:2518-2525` — the syncer agent-launch callback (`_launch_agent.on_launch`, inherited from the old `_launch_resolution_agent`) ignores `AgentCommandScreen`'s `"run"` result, so "Run in terminal" silently does nothing for both the failure and the data-conflict agent. The fix needs a cwd-aware terminal spawn for multi-repo rows.
- `.aitask-scripts/lib/sync_action_runner.py:496` and `.aitask-scripts/syncer/sync_failure_screen.py:26` — `SyncConflictScreen` and `SyncFailureScreen` derive from bare `ModalScreen` against the `GuardedModalScreen` dismissal rule in `aidocs/framework/tui_conventions.md`. A stale `action_cancel` after the next modal opened popped that next modal (review: PLAUSIBLE; natural key timing unverified).

## Diagnostic context

t1911 added a "Launch agent to resolve" option to the shared aitask-data conflict dialog (`SyncConflictScreen`) and generalised the syncer's agent launch into `_launch_agent(*, title, window_name, prompt, project_root)`, now used by both the failure escape hatch and the data-conflict agent.

`AgentCommandScreen` dismisses with `"run"` (its "Run in terminal" button), a `TmuxLaunchConfig`, or `None`. The board handles `"run"` through `run_dialog_command` (`board/board_trail_screen.py`, `["sh", "-c", full_command]` via `find_terminal` / `spawn_in_terminal`, or `suspend()`), but the syncer's callback only handles `TmuxLaunchConfig`. In the syncer the target may be another repo (multi-repo rows), so the spawn must run in that repo root — `spawn_in_terminal` / the board's helper take no cwd.

During t1911's review, the conflict modal was flagged for still deriving from bare `ModalScreen`. `lib/guarded_dismiss.GuardedModalScreen` exists for exactly this; the inheritance predates t1911 and applies equally to `SyncFailureScreen`.

## Suggested fix

- Handle `"run"` in the syncer's `_launch_agent` callback with a cwd-aware spawn (e.g. `sh -c 'cd <root> && <cmd>'`, or extend the shared helper with a cwd), plus a test in `tests/test_syncer_rows.py`.
- Re-base `SyncConflictScreen` and `SyncFailureScreen` on `GuardedModalScreen`, keeping their dismiss values (`CONFLICT_CHOICE_*` / `None`; `True` / `False`), and add a stale-cancel test.
