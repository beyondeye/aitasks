---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [board, tui]
assigned_to: dario-e@beyond-eye.com
anchor: 1911
followup_kind: upstream_defect
created_at: 2026-10-11 17:39
updated_at: 2026-10-11 19:11
---

## Origin

Spawned from t1943 during Step 8b review.

## Upstream defect

- `.aitask-scripts/board/aitask_board.py:5063` — `_run_sync` (thread worker running `aitask_sync.sh --batch`) is not coordinated with the board's suspend-and-edit path: an in-flight background auto-sync can pull/merge/commit task data while `$EDITOR` holds the same task file open; cancelling the worker never stopped its thread or subprocess (pre-existing, unchanged by t1943).

## Diagnostic context

t1943 moved `KanbanApp.run_editor` from the exclusive default worker group into its own `"editor"` group. In review we confirmed that the old exclusive-cancel never gave mutual exclusion with `_run_sync`. That worker is `@work(exclusive=True, thread=True)` and blocks in `run_sync_batch()` → `subprocess.run(aitask_sync.sh --batch)`. Textual's `Worker.cancel()` on a thread worker only marks it cancelled; the thread and its git subprocess keep running. A background auto-sync (the `set_interval` path at ~line 2829, `show_overlay=False`) that is already in flight when the user presses edit therefore runs concurrently with the suspended `$EDITOR` session, before and after t1943. The blocked event loop (the editor's `subprocess.call` runs on it) only prevents a *new* default-group worker from starting mid-edit. `tests/test_board_run_editor.py::test_editor_overlaps_an_in_flight_threaded_sync` pins today's overlap; it makes no claim that the overlap is safe.

## Suggested fix

Coordinate the edit path with an in-flight sync. For example: before suspending, wait for or refuse while a `_run_sync` worker is running (notify "sync in progress"), and/or pause the auto-sync timer for the duration of the edit. Keep the editor's own worker group so edit still never cancels unrelated workers.
