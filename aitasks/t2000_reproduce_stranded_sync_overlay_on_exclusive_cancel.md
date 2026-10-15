---
priority: low
effort: low
depends: []
issue_type: bug
status: Ready
labels: [ui]
gates: [risk_evaluated]
anchor: 1957
followup_kind: upstream_defect
created_at: 2026-10-15 09:19
updated_at: 2026-10-15 09:19
---

## Origin

Spawned from t1994 during Step 8b review. Scoped by the user as a **small
reproduction experiment, not a fix**: the cancellation mechanism is credible,
but its reachability in normal use is unproven. A fix (medium effort) is
premature unless this experiment reproduces it or users report stuck sync
overlays.

## Upstream defect

- `.aitask-scripts/board/aitask_board.py:5136 — _run_sync(show_overlay=True) (started by action_sync_remote at :5134 and board_trail_screen.py:971) pops its "Syncing with remote..." LoadingOverlay only in its own body; being exclusive in the default group, a later exclusive default-group worker added before it takes its first step cancels it and strands the overlay (same mechanism as t1979/t1988/t1994, among the exclusive workers; not reproduced)`

(Line numbers as of commit 00e3fcc41.)

## Diagnostic context

From t1994's investigation (Textual 8.2.7): `WorkerManager.add_worker` calls
`cancel_group(node, group)` for every `exclusive=True` worker, and a worker
cancelled before its asyncio task's first step never reaches
`run_in_executor`, so a thread worker's body — and any `finally` — never runs.
t1994 proved this for the four task-op workers (archive/delete/rename/commit):
a same-tick exclusive worker dropped the operation and left the caller's
`LoadingOverlay` on the screen stack (pre-fix probe output in
`aiplans/archived/p1994_*.md`, "Red/green evidence").

`_run_sync` is the same shape among the *exclusive* workers: `action_sync_remote`
pushes `LoadingOverlay("Syncing with remote...")` and starts
`_run_sync(show_overlay=True)`, whose body pops the overlay. Exclusive-vs-
exclusive cancellation in the default group is deliberate (the newest sync
wins), but a newer canceller that does not pop that overlay (e.g. a
`_run_sync(show_notification=...)` without `show_overlay`, or
`run_aitask_pick` / `run_codeagent_operation` / `run_dialog_command` /
`_run_interactive_sync_shared`) would strand it. `LoadingOverlay` has no
bindings and keeps `_modal_is_active()` True, so the board would appear hung.

Why reachability is unproven: the overlay is pushed synchronously before the
worker starts, so the auto-refresh timer (`_auto_refresh_tick`, gated by
`_modal_is_active()`) and modal-gated actions cannot start a canceller after
it. A canceller has to come from a route that does not consult the modal — the
one t1994 identified is a `_run_sync` created through `call_from_thread` from
another worker's thread (`_do_rename_task` does this right after popping its
own overlay), racing a user's `s` press in the same loop iteration.

## Goal: reproduction experiment

1. Enumerate every route that can create an exclusive default-group worker on
   the `KanbanApp` node **without** checking `_modal_is_active()` (cross-thread
   `call_from_thread` creations, timer/callback paths, screen result callbacks).
2. For each, try to make it land in the same event-loop iteration as
   `action_sync_remote` (or the trail-screen sync at board_trail_screen.py:971)
   through the real entry points — key presses via `pilot.press`, real worker
   threads — not by calling `app.run_worker(..., exclusive=True)` directly
   (that only re-proves the mechanism, which t1994 already did).
3. Record the outcome in the plan: reproduced (with the exact sequence) /
   not reproducible (with the routes checked and why each cannot interleave).

## Suggested fix (only if reproduced)

Move the overlay pop out of the cancellable body (e.g. pop from a
done/cancel callback, or have the sync path own its overlay independently of
which `_run_sync` invocation wins), with a same-tick regression test modelled
on `tests/test_board_task_op_worker_groups.py`. If not reproduced, close the
task with the findings and no code change.
