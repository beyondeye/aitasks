---
Task: t1994_isolate_board_task_op_workers_from_exclusive_cancel.md
Base branch: main
Output branch: main
---

# t1994 — Isolate board task-op workers from exclusive default-group cancels

## Context

Four task-operation thread workers in `.aitask-scripts/board/aitask_board.py`
run in Textual's **default** worker group on the `KanbanApp` node:

| worker | line (4f4d5e4a7) | caller (pushes overlay, then starts worker) |
|---|---|---|
| `_do_archive` | 6600 | `_execute_archive` → `LoadingOverlay("Archiving task...")` |
| `_do_delete` | 6756 | `_execute_delete` → `LoadingOverlay("Deleting task...")` |
| `_do_rename_task` | 6920 | `_rename_task` → `LoadingOverlay("Renaming...")` |
| `_do_git_commit_tasks` | 6971 | `_git_commit_tasks` → `LoadingOverlay("Committing...")` |

The same node runs exclusive default-group workers: `_run_sync`,
`_run_interactive_sync_shared`, `run_aitask_pick`, `run_codeagent_operation`
(aitask_board.py) and `run_dialog_command` (board_trail_screen.py, mixin).
Textual 8.2.7 `WorkerManager.add_worker` calls `cancel_group(node, group)` for an
exclusive worker; `Worker.cancel()` cancels the asyncio task, and a task cancelled
before its first step never reaches `run_in_executor`, so the thread body — and
its `finally` — never runs. (Verified in the installed
`textual/worker_manager.py` `add_worker`/`cancel_group` and `textual/worker.py`
`_start`/`_run`/`cancel`.)

**What a pre-start cancel does to each of the four (answering the task's
"confirm before fixing" question, from the code — the red run in step 1 proves it):**
- The user-confirmed archive/delete/rename/commit never runs, with no
  notification — silently dropped.
- The busy state *is* left set: each body pops its caller's `LoadingOverlay` in
  its `finally`, so the overlay is stranded on top. `LoadingOverlay`
  (board_widgets.py:690) has no bindings, and `_modal_is_active()` stays True, so
  `_auto_refresh_tick` returns early forever and every modal-gated action refuses
  — the board is effectively hung until quit.
- `_do_rename_task` additionally never reaches its follow-up `_run_sync` / reload.

**Reachability is narrow** (consistent with "not reproduced"): each caller pushes
its overlay synchronously (`App.push_screen` appends to the stack before
returning) before starting the worker, which closes the timer route — a later
tick sees the modal. The remaining exposure is a canceller that does not consult
the modal, e.g. a `_run_sync` created through `call_from_thread` from another
worker's thread (which `_do_rename_task` itself does). The fix is a cheap
structural guarantee, matching t1979/t1988.

Side effect of the fix: `_do_rename_task`'s own `_run_sync(...)` call currently
cancels the rename worker itself (state → CANCELLED while its thread keeps
running). In its own group that self-cancel disappears.

**Audit of the board's other non-exclusive default-group workers:**
- `KanbanApp` node: the four above are the only ones in `aitask_board.py`; the
  trail mixin's are already grouped (t1988, pinned by `TrailWorkerGroupTests`);
  `TuiSwitcherMixin` / `ShortcutsMixin` declare no workers.
- `board_detail_screen.py`: `_codebrowser_worker` (node: `FileReferencesField`),
  `_do_lock` / `_do_unlock` (node: `TaskDetailScreen`) are default-group, but
  `cancel_group` also matches on `worker.node`, and neither node starts an
  exclusive worker → not exposed. No change.
- `trails_app.py`: both workers already name `trails_focus`.
- Out of scope, recorded for Step 8b: `_run_sync(show_overlay=True)`
  (`action_sync_remote`, board_trail_screen.py:971) also pops its overlay in its
  own body; being exclusive in the default group, a later exclusive
  default-group worker added before it starts would strand "Syncing with
  remote...". Same mechanism among the exclusive workers; not one of this task's
  non-exclusive workers.

## Implementation

Current-branch mode (profile `fast`); no worktree.

### 1. Regression tests first, red against the unmodified code

New file `tests/test_board_task_op_worker_groups.py` (module docstring naming
t1994 and the mechanism; `Run:` line like its siblings). Imports/`sys.path` idiom
from `tests/test_board_scoped_task_commit.py`; `import board_fixture as bf`.

**`TaskOpSameTickCancelTests(unittest.TestCase)`** — real `KanbanApp` under
`run_test`. **Every (operation, variant) pair is its own test method** — 4 ops ×
{`baseline`, `same_tick_exclusive`} = 8 methods, e.g.
`test_rename_baseline` / `test_rename_survives_same_tick_exclusive_worker`.
`setUp` builds a **fresh fixture tree per method** via
`bf.enter_fixture_tree(self.addCleanup, tag=f"{type(self).__name__}_{self._testMethodName}")`,
and each method boots its **own app** and resolves `task` from **that app's**
`manager.task_datas`. No variant ever runs after another in the same tree:
rename really moves the task file (`old_task.rename(new_task)`) and delete
really removes it (`os.remove`), so a shared tree would hand the second variant
a missing/renamed file (rename would then fail before its commit, or return
"Name unchanged" without starting a worker) and the red/green comparison would
no longer exercise the same valid operation.

Both variants of an op share one helper `_drive(op, canceller: bool)` so they run
the identical operation; it:
- asserts the precondition before the op: `task.filepath.exists()` and no
  `LoadingOverlay` in `app.screen_stack`;
- drives the **real caller** (which pushes the overlay and starts the worker in
  one synchronous call);
- when `canceller`, immediately (same tick, no await) calls
  `app.run_worker(lambda: None, thread=True, exclusive=True)` — the t1988
  pattern (`test_an_exclusive_default_group_worker_cannot_strand_the_jump`);
- drains: 3× `await app.workers.wait_for_complete()` + `await pilot.pause()`,
  with `textual.worker.WorkerCancelled` suppressed so the red run fails on the
  assertions rather than erroring in `gather`;
- asserts the effect landed exactly once, and
  `not any(isinstance(s, ab.LoadingOverlay) for s in app.screen_stack)`.

Effects are recorded by stubbing only the outermost side effect, keeping the real
bodies:
- **archive** — `app._execute_archive(<id>, task)`; `patch.object(ab.subprocess,
  "run", fake)` where `fake` records argv whose `argv[0]` ends in
  `aitask_archive.sh` (returns `CompletedProcess(argv, 0, "", "")`) and delegates
  everything else to the captured real `run`. Assert one `--superseded <id>` call.
- **delete** — `app._execute_delete(<id>, [task.filepath], None)` (parent-less,
  so no orphan-archive prompt); instance stub
  `app._decref_doomed_attachments = lambda p, f: (True, "")`;
  `patch.object(ab, "commit_task_paths", rec)` returning
  `SimpleNamespace(status="committed", detail="")`. Assert one commit whose paths
  include the task file.
- **rename** — `app._rename_task(task, "renamed probe")`; `commit_task_paths`
  recorder as above; instance stub `app._run_sync = MagicMock()` (no real sync).
  Assert one commit and `_run_sync` called once.
- **commit** — `app._git_commit_tasks([task], "ait: probe")`;
  `commit_task_paths` recorder. Assert one commit with that task's path.

`task` = a top-level task from `app.manager.task_datas` of the default fixture
topology.

**`BoardWorkerGroupTests(unittest.TestCase)`** — AST guard over
`.aitask-scripts/board/aitask_board.py`, same shape as `TrailWorkerGroupTests`
(tests/test_board_bytrail_view.py:2501): every `@work` without
`exclusive=True` must name a group that is a non-empty string other than
`"default"`; vacuity guard `KNOWN = {"_do_archive", "_do_delete",
"_do_rename_task", "_do_git_commit_tasks"} <= scanned`.

**Red run** (negative control) — run the file against the unmodified board:
expected failures are exactly the four `*_survives_same_tick_exclusive_worker`
methods (effect missing, `LoadingOverlay` still in `screen_stack` — precondition
asserts passing, so the failure is the cancel and not fixture state) and the AST
guard naming all four workers; the four `*_baseline` methods must pass (proves
the harness drives the real bodies on a valid fixture and the canceller is what
breaks them). If a same-tick method passes pre-fix, stop — the test is vacuous.

### 2. The fix — `.aitask-scripts/board/aitask_board.py`

Give each worker its own group (per-worker, mirroring t1988's
`trail_link`/`trail_jump`/…; none is exclusive, so groups only isolate):

- `_do_archive`: `@work(thread=True, group="task_archive")`
- `_do_delete`: `@work(thread=True, group="task_delete")`
- `_do_rename_task`: `@work(thread=True, group="task_rename")`
- `_do_git_commit_tasks`: `@work(thread=True, group="task_commit")`

Add one sentence to each docstring, in `run_editor`'s style: own worker group —
an exclusive default-group worker started before this one begins would cancel
it, so the confirmed operation would never run and the `finally` that pops the
caller's `LoadingOverlay` would never execute (t1994). `__wrapped__` is
unchanged, so `tests/test_board_scoped_task_commit.py`'s direct body calls keep
working.

### 3. Green run

Re-run the new file (all pass), then the neighbours that touch these workers.

## Verification

```bash
PY=~/.aitask/venv/bin/python
$PY tests/test_board_task_op_worker_groups.py -v          # red before step 2, green after
$PY tests/test_board_scoped_task_commit.py -v             # direct __wrapped__ bodies
$PY tests/test_board_run_editor.py -v                     # editor/sync/launch exclusivity
$PY -m pytest -q tests/test_board_bytrail_view.py -k "TrailWorkerGroupTests or cannot_strand"
```

Post-implementation: Step 9 (Post-Implementation) — commit, archive, push.

## Risk

### Code-health risk: low
- None identified.

### Goal-achievement risk: low
- The same-tick regression test could pass vacuously if the canceller never landed before the victim's first step · severity: low · → mitigation: none (covered in-plan by step 1's red run and the per-method `*_baseline` controls)
- A baseline and its same-tick control could exercise different operations if they shared fixture state (rename/delete mutate disk) · severity: low · → mitigation: none (covered in-plan: one fresh tree + app per test method, shared `_drive` helper, precondition asserts)
