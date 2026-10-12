---
Task: t1961_fix_syncer_interactive_sync_on_done_thread.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1961 — Syncer interactive sync: call the refresh directly in `on_done`

## Context

`SyncerApp._run_interactive_sync_shared` (`.aitask-scripts/syncer/syncer_app.py:2444-2454`)
is an **async** `@work(exclusive=True, group="syncer-action")` worker, so it runs on
the app thread. It passes
`on_done=lambda: self.call_from_thread(self._tick_refresh)` to
`run_interactive_sync` (`.aitask-scripts/lib/sync_action_runner.py:761`). With no
terminal emulator, that helper suspends the app, runs `./ait sync` inline, and
calls `on_done()` synchronously **in the same thread**. Textual then raises
`RuntimeError: The call_from_thread method must run in a different thread from the app`.
The worker errors and the post-sync refresh never runs. The t1955 lock is still
released, because the guard releases it in its `finally`. The board's twin passes a
plain callable and is unaffected. Existing tests stub `run_interactive_sync`
entirely, so the real completion callback is never exercised.

## Implementation

1. **Fix** — `.aitask-scripts/syncer/syncer_app.py`, `_run_interactive_sync_shared`:
   replace `on_done=lambda: self.call_from_thread(self._tick_refresh)` with
   `on_done=self._tick_refresh`. Add a short comment saying the callback already
   runs on the app thread, because the worker is async. This matches the board twin
   (`KanbanApp._run_interactive_sync_shared`, a plain `reload`). `_tick_refresh`
   only schedules the thread worker `_refresh_worker` and takes no
   `_sync_data_lock`, so it is safe to call while the guard is held.

2. **Regression test** — `tests/test_syncer_rows.py`: add a new class
   `InteractiveSyncCompletionTests(_TabbedShellBase)`, placed after `StraySyncTests`.
   It drives the **real** `run_interactive_sync`:
   - do not patch `syncer_app.run_interactive_sync`, so do not use `agent_seams`;
   - patch `sync_action_runner.find_terminal` → `None`. This is the helper's own
     module global; `syncer_app.find_terminal` is a different binding;
   - patch `sync_action_runner.subprocess.call` with a recorder that appends
     `"call"` and the argv, and returns 0;
   - patch `app._driver` with a local suspend-capable fake driver modelled on
     `_fake_driver` in `tests/test_board_run_editor.py:158`: `can_suspend=True`,
     `no_automatic_restart` → `nullcontext`, and suspend/resume side effects that
     append events;
   - wrap `app._tick_refresh` in a counting spy, using `mock.patch.object(app,
     "_tick_refresh", wraps=...)`;
   - `worker = app._run_interactive_sync_shared(ActionTarget(None, None, ""))`,
     `await worker.wait()` (which raises `WorkerFailed` on the pre-fix code), then
     `settle`.
   - Asserts: `worker.state == WorkerState.SUCCESS`, events
     `["suspend", "call", "resume"]`, argv `["./ait", "sync"]`, refresh spy
     called exactly once and after `resume`, and `_sync_data_lock` free afterwards
     (`acquire(blocking=False)` succeeds, then release).
   - Second test, a multi-repo target (`ActionTarget(Path("/tmp/repo1"), None,
     "repo1")` with two sessions): argv is `["/tmp/repo1/ait", "sync"]` with
     `cwd="/tmp/repo1"`, and the refresh still runs. This covers the `repo_root`
     branch through the same real path.
   - Import `WorkerState` from `textual.worker` and `sync_action_runner` as a
     module, if not already imported.

## Verification

- **Red proof:** run the new tests against the unfixed line first. They must fail
  with the `call_from_thread` RuntimeError / `WorkerFailed`. Then apply the fix.
  The tests must go green.
- `bash tests/run_all_python_tests.sh --test-dir` is not needed for one module. Run
  `~/.aitask/venv/bin/python -m pytest tests/test_syncer_rows.py -q`. That covers
  the whole module, including the existing `StraySyncTests` and
  `DataConflictAgentTests`.
- Step 9 (Post-Implementation): commit, archive the task.

## Risk

### Code-health risk: low
None identified. One-line change in a single worker; it matches the board twin's
existing pattern, and the new test is additive.

### Goal-achievement risk: low
None identified. The root cause is confirmed from the code: the async worker plus
the synchronous `on_done` in the helper. The test exercises the real helper
through `App.suspend`, which is exactly the path the task names.

## Final Implementation Notes
- **Actual work done:** `syncer_app.py` `_run_interactive_sync_shared` now passes `on_done=self._tick_refresh` (plain callable, with a one-line comment), replacing the `call_from_thread` lambda. Added `InteractiveSyncCompletionTests` to `tests/test_syncer_rows.py` (two tests: single-repo `root=None` → `["./ait","sync"]`, `cwd=None`; multi-repo → `["/tmp/repo1/ait","sync"]`, `cwd="/tmp/repo1"`). Both drive the REAL `run_interactive_sync`, stubbing only `sync_action_runner.find_terminal` (→ None), `sync_action_runner.subprocess.call` and `app._driver` (suspend-capable fake), and assert worker `SUCCESS`, event order `suspend, call, resume, refresh`, and `_sync_data_lock` free afterwards.
- **Deviations from plan:** The refresh spy is a plain recording wrapper around the real `_tick_refresh` (not `mock.patch(wraps=...)`), so "refresh after resume" is asserted through the single ordered event list. `WorkerFailed` is caught and asserted rather than propagated, so the red run reports the cause directly.
- **Issues encountered:** None. Red proof: both tests failed pre-fix with `RuntimeError: The call_from_thread method must run in a different thread from the app`; post-fix the whole module passes (164 tests).
- **Key decisions:** Direct call instead of `call_later`. The callback already runs on the app thread, and this matches the board twin's plain `reload`. `_tick_refresh` only schedules the threaded refresh worker and does not take `_sync_data_lock`, so calling it inside the guard is safe.
- **Upstream defects identified:** None
