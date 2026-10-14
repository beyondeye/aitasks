---
priority: medium
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
anchor: 1957
followup_kind: upstream_defect
created_at: 2026-10-14 22:13
updated_at: 2026-10-14 22:31
---

## Origin

Spawned from t1988 during Step 8b review.

## Upstream defect

- `.aitask-scripts/board/aitask_board.py:6600,6756,6920,6971 — _do_archive / _do_delete / _do_rename_task / _do_git_commit_tasks run as @work(thread=True) in Textual's default group; an exclusive default-group worker (_run_sync from the auto-refresh timer, run_dialog_command, run_aitask_pick, run_codeagent_operation) started before one of them begins cancels it, and the confirmed archive/delete/rename/commit silently never runs (same mechanism as t1979/t1988; not reproduced)`

(Line numbers as of commit 4f4d5e4a7.)

## Diagnostic context

Textual's `WorkerManager.add_worker` calls `cancel_group(worker.node,
worker.group)` for every `exclusive=True` worker. `Worker.cancel()` cancels
the worker's asyncio task; if that happens before the task's first step,
`Worker._run` never reaches `run_in_executor`, so a thread worker's body —
and any `finally` — never runs (verified in the installed Textual:
`worker.py` `_start` / `_run` / `cancel`, `worker_manager.py` `add_worker`).
Once the body is in the executor a cancel cannot stop it.

On the board App node the default group holds exclusive workers `_run_sync`
(`exclusive=True, thread=True`, also started by `_auto_refresh_tick` from a
`set_interval` timer — gated only by `_modal_is_active()`, which is already
False once a confirm dialog has been dismissed), `run_dialog_command`
(`board_trail_screen.py`), `run_aitask_pick`, `run_codeagent_operation` and
`_run_interactive_sync_shared`. The four task-operation thread workers above
run in the same default group with no group of their own, and are started from
confirm-dialog result callbacks. Textual can process several queued messages
(e.g. a dialog result and a timer tick) without yielding to the event loop,
so "same tick" does not require the same handler.

t1979 (`_trail_link_worker`, `group="trail_link"`) and t1988 (every other
thread worker in `board_trail_screen.py`) fixed the same mechanism in the trail
mixin. `run_editor` (`aitask_board.py`, `group="editor"`) already documents the
hazard from the other side. The t1988 regression-test pattern:
start the victim worker, then `app.run_worker(lambda: None, thread=True,
exclusive=True)` in the same tick, and assert that the victim's effect landed.
See `tests/test_board_bytrail_view.py`
`test_an_exclusive_default_group_worker_cannot_strand_the_jump` and
`TrailWorkerGroupTests` (AST guard: every non-exclusive `@work` names a
non-default group).

Not reproduced for these four workers. Before fixing, confirm what each one
does when it is cancelled before start: is a user-confirmed operation silently
dropped, and is any busy/lock state left set?

## Suggested fix

Give each task-operation worker a dedicated non-default group (or one shared
`task_ops` group if they must never overlap — none is exclusive, so a shared
group does not cancel). Add a same-tick exclusive-worker regression test per
worker, and consider extending an AST guard like t1988's to `aitask_board.py`'s
non-exclusive workers. While there, audit the board's other non-exclusive
default-group workers too.
