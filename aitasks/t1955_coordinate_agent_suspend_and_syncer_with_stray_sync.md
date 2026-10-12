---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [board, tui]
gates: [risk_evaluated]
anchor: 1911
followup_kind: upstream_defect
created_at: 2026-10-12 16:30
updated_at: 2026-10-12 16:30
---

## Origin

Spawned from t1947 during Step 8b review.

## Upstream defect

- `.aitask-scripts/board/aitask_board.py:5387 — run_aitask_pick / run_codeagent_operation suspend the board and run a code agent with no _sync_edit_lock coordination, so an in-flight or thread-started sync can pull/commit task data under the agent (same class as t1947)`
- `.aitask-scripts/syncer/syncer_app.py:2249 — _sync_data_worker gets SyncResult.stray_session from run_sync_batch but has no sticky refusal, so its next sync can start while a timed-out sync's unproven session is still running`

## Diagnostic context

t1947 (commit 394d9fcea) coordinated `KanbanApp.run_editor` with `_run_sync`:
- `self._sync_edit_lock` (threading.Lock): `_run_sync` holds it (blocking) around `run_sync_batch()`; `run_editor` acquires it non-blocking across `self.suspend()` and refuses with a notice when held. A sync started mid-edit from a thread (e.g. `_do_rename_task`) waits.
- `run_sync_batch` now runs `aitask_sync.sh` in its own session and, on timeout, stops every session member (TERM, then repeated KILL rounds) and proves the session empty via `/proc` or `pgrep -s`. When it cannot prove it, `SyncResult.stray_session` carries the sid; `sync_session_running(sid)` is the fail-closed recovery probe.
- The board keeps `_stray_sync_session` (sticky): edits and syncs are refused until the probe proves the session gone (`_stray_sync_blocks`).

Two paths were left out of t1947's scope:
1. The board's other suspend sites — `run_aitask_pick` and `run_codeagent_operation` (no-terminal fallback: `with self.suspend(): subprocess.call([wrapper, "invoke", ...])`) — run a code agent in the suspended board. The agent does git work on task data (status updates, plan commits) while an auto-sync already in flight, or one started from a thread, can pull/rebase/commit the same data. They do not take `_sync_edit_lock` and ignore `_stray_sync_session`.
2. The syncer TUI (`_sync_data_worker`) receives the containment and the `stray_session` field but keeps no state: after a stray timeout its next sync starts immediately, overlapping the unproven survivor.

## Suggested fix

Reuse the board's pattern: take `_sync_edit_lock` non-blocking around the agent suspend (refuse with a notice) and consult `_stray_sync_blocks()` first. In the syncer, record `stray_session` per target repo and refuse/skip that repo's next sync until `sync_session_running(sid)` is False, with a visible notice.
