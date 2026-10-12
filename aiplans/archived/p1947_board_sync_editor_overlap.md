---
Task: t1947_board_sync_editor_overlap.md
Base branch: main
Output branch: main
---

# t1947 — Coordinate board edit with an in-flight sync

## Context

`KanbanApp.run_editor` (`.aitask-scripts/board/aitask_board.py:5015`) suspends the
board and runs `$EDITOR` on a task/plan file. `KanbanApp._run_sync` (`:5070`) is a
`@work(exclusive=True, thread=True)` worker that blocks in `run_sync_batch()`
(`.aitask-scripts/lib/sync_action_runner.py:368`) → `aitask_sync.sh --batch`
(pull/rebase/commit of task data). Nothing coordinates the two:

1. **Sync already running when the user edits.** The auto-sync timer
   (`_auto_refresh_tick` `:2826`) starts it silently. Worker state cannot see it:
   `Worker.cancel()` on a thread worker only marks it CANCELLED, and the thread
   and its git keep running.
2. **Sync started mid-edit.** `_do_rename_task` (`:6840`) starts `_run_sync` *from
   a thread*; Textual allows this (probe verified), so the blocked event loop does
   not stop it.
3. **Sync timed out but its git is still running** (review findings, verified):
   - `subprocess.run(timeout=30)` kills only the direct `bash`. The pull/rebase
     git children survive and keep mutating task data after `STATUS_TIMEOUT`.
   - `killpg` misses `_git_with_timeout` (`aitask_sync.sh:253`), because
     coreutils `timeout` `setpgid`s itself and git into their own group.
   - A liveness pipe does not prove completion either: a descendant can close
     inherited fds (e.g. Python `Popen(close_fds=True)` in a hook) and keep
     running.
   - `aitask_sync.sh` has no signal traps.

Intended outcome: no sync activity overlaps an open `$EDITOR`, including a
timed-out sync's descendants. An edit requested during a sync is refused. A sync
requested during an edit waits for the editor. After a timed-out sync whose
stop cannot be **proven**, edits and further syncs stay refused until a re-check
proves the activity stopped.

## Approach

- **Exclusion lock.** A per-app `threading.Lock`:
  - `_run_sync` holds it (blocking acquire) around `run_sync_batch()`.
  - `run_editor` holds it across `self.suspend()` with a **non-blocking**
    acquire. It runs on the event loop, which must never wait on a sync thread.
    It refuses rather than waits, so the editor never pops open at an
    unpredictable later moment.
  - Side effect, intended: overlapping `_run_sync` threads now run serially.
- **Session-based containment in `run_sync_batch`.** The sync runs with
  `start_new_session=True`, so its session id (SID = bash's pid) is inherited by
  every descendant, whatever its process group or open fds. A process leaves
  the session only by calling `setsid()` itself. That is deliberate
  daemonization (ssh ControlPersist masters, `git maintenance --detach`), not
  task-data work. On timeout the runner:
  - signals **every session member** with SIGTERM, then a short grace (git
    removes its `*.lock` files on TERM);
  - repeats SIGKILL rounds until membership is empty or a deadline passes (the
    repeats cover a member forking between listing and kill);
  - reaps bash and re-queries.
  - Proven empty ⇒ normal `STATUS_TIMEOUT`. Members remaining, **or the
    membership query unavailable** ⇒ the result carries `stray_session=<sid>`
    (fail closed).
- **Normal exit needs no proof.** `aitask_sync.sh` waits for every child it
  starts; its only `&` is the watchdog fallback in `_git_with_timeout`, which it
  `wait`s. Anything left in the session after a clean exit is a helper daemon git
  spawned on purpose (credential-cache, fsmonitor), not task-data activity.
  Waiting on those would stall or permanently block every sync.
- **Sticky unsafe state on the board.** A `stray_session` result is stored as
  `self._stray_sync_session`. While it is set, `run_editor` refuses and
  `_run_sync` skips the sync, both with a notice. Each such attempt re-checks
  `sync_session_running(sid)`, and the state clears only when the re-check
  **proves** the session empty. An unavailable query keeps it refused. Every
  read and write of the state happens under the exclusion lock.

## Steps

1. **`sync_action_runner.py`** (shared with the syncer; it gets containment and
   the `stray_session` field, but no sticky state — that gap is noted, not
   fixed here):
   - imports `os`, `signal`, `time`.
   - constants beside `DEFAULT_SYNC_TIMEOUT_SECONDS`: `_TERM_GRACE_SECONDS = 3`,
     `_KILL_DEADLINE_SECONDS = 5`, `_POLL_SECONDS = 0.05`, each commented.
   - `SyncResult.stray_session: int | None = None`. Documented as set only on
     `STATUS_TIMEOUT`, when the sync's session could not be proven empty. The
     caller must treat task data as possibly still changing until
     `sync_session_running(sid)` is False.
   - `_session_members(sid) -> list[int] | None`:
     - Linux: scan `/proc/<pid>/stat` and parse after the last `)` (state,
       ppid, pgrp, session); skip zombies (`Z`) and pids that vanish mid-scan.
     - Elsewhere: `pgrep -s <sid>`. rc 1 ⇒ `[]`, rc 0 ⇒ the pids, anything else
       or `OSError`/timeout ⇒ `None`.
   - `sync_session_running(sid) -> bool` (public): `True` when members exist
     **or** the query is unavailable. This is the board's recovery probe.
   - `_signal_members(members, sig)`: `os.kill` each member, swallowing
     `ProcessLookupError`/`PermissionError`.
   - `_stop_sync_session(proc) -> int | None`. Uses `sid = proc.pid`:
     - TERM round, then poll up to `_TERM_GRACE_SECONDS` for empty;
     - SIGKILL rounds every poll until empty or `_KILL_DEADLINE_SECONDS`;
     - `proc.kill()` (direct child; harmless if already dead), `proc.wait()`,
       close `proc.stdout`/`proc.stderr` (never `communicate()` again);
     - final query, then return `None` when `[]`, else `sid`. An unknown query
       at any point ⇒ `sid`.
   - `_run_sync_process(argv, *, cwd, timeout, encoding, errors)` →
     `subprocess.CompletedProcess`:
     - `Popen(argv, stdout=PIPE, stderr=PIPE, encoding=…, errors=…, cwd=cwd,
       start_new_session=True)`, then `communicate(timeout=timeout)`;
     - on `TimeoutExpired`, raise `SyncProcessTimeout(argv, timeout,
       stray_session=_stop_sync_session(proc))` (a `subprocess.TimeoutExpired`
       subclass).
   - `run_sync_batch` calls `_run_sync_process(argv, cwd=cwd, timeout=timeout,
     encoding="utf-8", errors="surrogateescape")` (decode comment kept). On
     `SyncProcessTimeout` it returns `SyncResult(STATUS_TIMEOUT,
     error_message=…, stray_session=exc.stray_session)`. A stray appends "; its
     processes could not be confirmed stopped (session <sid>)". Docstring:
     containment contract and the setsid boundary.

2. **`aitask_board.py`**:
   - Import `sync_session_running`.
   - `import threading`. In `KanbanApp.__init__` beside
     `self._auto_refresh_timer = None` (`:2387`):
     `self._sync_edit_lock = threading.Lock()` and
     `self._stray_sync_session = None`, with a why-comment (t1947).
   - `_stray_sync_blocks(self) -> bool`, documented "caller holds
     `_sync_edit_lock`":
     - `None` ⇒ False;
     - `sync_session_running(sid)` ⇒ True;
     - otherwise clear the state and return False.
   - `_run_sync`:
     ```python
     with self._sync_edit_lock:
         skipped_for = self._stray_sync_session if self._stray_sync_blocks() else None
         if skipped_for is None:
             result = run_sync_batch()
             if result.stray_session is not None:
                 self._stray_sync_session = result.stray_session
     if show_overlay: pop overlay          # existing line, now after the lock
     if skipped_for is not None:
         notify (always, "error"): "Sync skipped: a timed-out sync (session <sid>)
         may still be changing task data"
         return
     ```
     In the TIMEOUT branch, also notify when `result.stray_session` is set
     (always, severity `"error"`, with `error_message`).
   - `run_editor`, after `resolve_editor_argv()` succeeds:
     ```python
     if not self._sync_edit_lock.acquire(blocking=False):
         notify("Sync in progress — edit again when it finishes", "warning"); return
     try:
         if self._stray_sync_blocks():
             notify("A timed-out sync (session <sid>) may still be changing task "
                    "data — edit refused until it stops", "error"); return
         <existing suspend / OSError / SuspendNotSupported block, unchanged>
     finally:
         self._sync_edit_lock.release()
     ```
     Add a docstring paragraph on the coordination.

3. **`tests/test_sync_action_runner.py`**:
   - Repoint the 4 `mock.patch.object(sync_action_runner.subprocess, "run", …)`
     sites to `sync_action_runner._run_sync_process`. The fakes and their
     kwargs assertions (`cwd`, `encoding`, `errors`) are unchanged.
   - Add `TimeoutContainmentTests` (real processes, POSIX). A temp
     `repo_root/.aitask-scripts/aitask_sync.sh` runs under
     `run_sync_batch(timeout=0.5, repo_root=…)`. Delayed descendants write a
     marker after ~1 s and record their pid in a file; cleanup kills any
     survivor. Tests:
     - **control:** a same-group delayed child under plain
       `subprocess.run(timeout=0.5)` still writes the marker, which proves the
       fixture makes a real survivor.
     - `test_timeout_stops_a_same_group_child`: the pull/rebase shape. Expect
       TIMEOUT, `stray_session is None`, and no marker after 1.5 s.
     - `test_timeout_stops_a_child_in_its_own_process_group`: the coreutils
       `timeout` shape, a `sys.executable` child that calls
       `os.setpgid(0, 0)`. Same expectations.
     - `test_timeout_stops_an_fd_dropping_descendant`: the reviewer's shape. The
       child `setpgid`s, closes stdio and spawns the delayed writer with
       `Popen(close_fds=True, stdin/stdout/stderr=DEVNULL)`, then exits. Same
       expectations.
     - `test_unprovable_stop_reports_the_session`: `_signal_members` patched to
       a no-op, so the child survives; grace and deadline patched short. Expect
       `stray_session` set, `sync_session_running(sid)` True, and "could not be
       confirmed" in `error_message`. Then kill the child and expect
       `sync_session_running(sid)` False: the recovery probe releases.
     - `test_unavailable_membership_query_fails_closed`: `_session_members`
       patched to `None`. Expect `stray_session` set and `sync_session_running`
       True.
     - `test_normal_exit_does_not_wait_for_session_helpers`: the script
       backgrounds a 5 s out-of-group sleeper with redirected stdio and prints
       `NOTHING`. Expect NOTHING returned in well under 5 s; cleanup kills the
       sleeper.

4. **`tests/test_board_run_editor.py`**. The host borrows the real `run_editor`,
   `_run_sync` and `_stray_sync_blocks` from the fixture-bound module.
   `ab.run_sync_batch` is patched to a stand-in that sets `entered`, blocks on a
   release Event and returns a given `SyncResult`. `ab.sync_session_running` is
   patched per test.
   - Host attributes:
     - `_sync_edit_lock` is a `_ProbeLock` around a real `threading.Lock`. It sets
       an `attempting` Event at the start of every blocking
       `acquire`/`__enter__`.
     - `_stray_sync_session = None`, `base_filter = "all"`,
       `active_trail_handle = None`.
     - Drop `threaded_sync_blocker`.
   - The `_run_editor` helper takes `blocker="sync"` (sync still blocked) or
     `"sync_finished"`. It records `lock_free_after` on every run.
   - `test_editor_refuses_while_a_sync_is_in_flight` (replaces the overlap
     pin):
     - no suspend and no call;
     - one `warning` containing "Sync in progress";
     - no editor reload;
     - the sync is not cancelled and ends `SUCCESS` once released.
   - `test_editor_runs_once_the_sync_has_finished` (replaces the probe's negative
     control): `suspend, call, resume, load`.
   - `test_sync_started_mid_edit_waits_for_the_editor`. Inside the stand-in
     `subprocess.call`:
     - start a plain thread running
       `ab.KanbanApp._run_sync.__wrapped__(app, show_notification=False)` (the
       `_do_rename_task` shape);
     - **handshake:** assert `attempting.wait(5)` (the thread reached the lock);
     - assert `entered.wait(0.3)` is False.
     - After the editor worker ends: `await asyncio.to_thread(entered.wait, 5)`
       is True, then `await asyncio.to_thread(thread.join, 5)`. Both stay off the
       event loop, because the real sync body blocks on `call_from_thread`.
   - `test_stray_timeout_refuses_edit_and_sync_until_proven_stopped`:
     1. A real `_run_sync` gets `SyncResult(STATUS_TIMEOUT, stray_session=4242,
        …)` with `show_notification=False`. Expect an `error` notice and
        `_stray_sync_session == 4242`.
     2. With `sync_session_running` → True:
        - the editor is refused: no suspend or call, an `error` notice naming
          the session;
        - a second `_run_sync` is skipped: the stand-in is not entered, and a
          "Sync skipped" notice appears.
     3. With `sync_session_running` → False: the editor runs normally
        (`suspend, call, resume, load`) and the state is cleared.
   - `lock_free_after` assertions on the success, missing-editor,
     no-suspend-support and refusal tests.
   - Module docstring: add a coordination bullet.

## Verification

- `~/.aitask/venv/bin/python -m pytest tests/test_board_run_editor.py tests/test_sync_action_runner.py -q`
- Red proof (no stash, no restore in the shared tree): in a scratch
  `git worktree add --detach` of HEAD, copy in only the two changed test files.
  - These must fail: refuse, mid-edit, stray-sticky, same-group, own-group and
    fd-dropping.
  - These must pass: the `subprocess.run` control and the finished-first
    control.
- Other borrowers: `pytest -n 4 --dist loadfile` over `tests/test_board_*.py`,
  `tests/test_syncer*.py` and `tests/test_sync*.py`, minus the `_live`
  carve-outs.
- `aitask_board.py` carries t1946's uncommitted edits, so stage only this task's
  hunks:
  - filter the patch: `git diff` → keep the t1947 hunks → `git apply --cached`;
  - check `git diff --cached`;
  - commit the staged content; that file gets no `-- <path>`, which would take
    its worktree content;
  - finish with `git show --stat`.

Step 9 (Post-Implementation): current-branch mode, so no merge; archive with
`aitask_archive.sh 1947`.

## Risk

### Code-health risk: medium
- `run_sync_batch` (shared with the syncer TUI) moves from `subprocess.run` to `Popen` + session signalling + a `/proc`/`pgrep` membership query · severity: medium · Bounded:
  - the normal path is still one `communicate()`;
  - the timeout path is pinned by real-process tests covering same-group, own-group and fd-dropping descendants;
  - the existing targeting/decode tests keep their assertions.
  → mitigation: none (covered by plan steps 1 and 3)
- The non-Linux membership path (`pgrep -s`) is untested here · severity: low · Any failure there is `None`, which fails closed: edits are refused until the probe works, and the notice names the session · → mitigation: none
- A held lock or a stuck unsafe state would block edits/syncs · severity: low · Residual:
  - the lock is released in `finally`, with `lock_free_after` asserted on every exit path;
  - the unsafe state releases on any attempt once the probe proves the session empty, and that release is pinned in steps 3 and 4.
  → mitigation: none

### Goal-achievement risk: low
- A descendant that calls `setsid()` leaves the session and is not tracked · severity: low · That is deliberate daemonization (ssh ControlPersist, `git maintenance --detach`), not task-data work. It is documented in the runner docstring as the containment boundary · → mitigation: none
- Out of scope; Step 8 records each as an upstream-defect candidate:
  - the other suspend sites (`run_aitask_pick` `:5339`, `run_codeagent_operation` `:5358`) run an agent in the suspended board with no sync coordination;
  - the syncer TUI gets the containment and `stray_session` but no sticky refusal of its next sync.

## Post-Review Changes

### Change Request 1 (2026-10-12 12:55)
- **Requested by user:** `_session_members` treated every `OSError` reading `/proc/<pid>/stat` as "process exited", so a `PermissionError`/I/O error yielded `[]` and `sync_session_running` returned False — clearing the board's unsafe state without proof. Add a backend-level regression (the existing unavailable-query test stubbed `_session_members` itself).
- **Changes made:** only `FileNotFoundError`/`ProcessLookupError` (vanished between listing and reading) are skipped; any other `OSError`, and an unparseable stat line, return `None` (unknown → fail closed). Tests `test_unreadable_proc_entry_is_unknown_not_gone` (PermissionError, EIO → `None`/running) and control `test_vanished_proc_entry_is_skipped` (ENOENT, ESRCH → `[]`/not running) drive the real `/proc` backend against the test's own live session with `open` patched in the module namespace. Old behaviour reproduced as a mutant: `members=[] running=False`.
- **Files affected:** `.aitask-scripts/lib/sync_action_runner.py`, `tests/test_sync_action_runner.py`

## Final Implementation Notes
- **Actual work done:** As planned (third revision, after two review rounds): a per-app `_sync_edit_lock` (non-blocking in `run_editor`, blocking around `run_sync_batch()` in `_run_sync`); session-contained `run_sync_batch` (`start_new_session`, TERM then repeated KILL rounds over every session member, proof by `/proc`/`pgrep -s` membership; `SyncResult.stray_session` when unproven); sticky board unsafe state `_stray_sync_session` cleared only by `sync_session_running(sid)` proving the session empty.
- **Deviations from plan:** None in design. The four pre-existing `subprocess.run` mocks in `test_sync_action_runner.py` were repointed to the new `_run_sync_process` seam (same fake shape). The editor test host's `refresh_board` now records only explicit refocus targets (the borrowed `_run_sync` calls it with `refresh_locks=True`).
- **Issues encountered:** A thread-only `threading.Thread` calling the undecorated `_run_sync` needs `contextvars.copy_context().run` (the body uses `self.app`). A first red proof at HEAD was not guard-specific (every test failed on missing attributes), so it was replaced by eight single-guard mutants in a scratch worktree — each fails only its guard's tests. `aitask_board.py` carried another session's (t1952) uncommitted hunks; only t1947 hunks were staged.
- **Key decisions:** Session membership rather than process group (coreutils `timeout` `setpgid`s git out of the group) or a liveness pipe (a descendant can close inherited fds). Refuse rather than wait on the editor side. No drain on a clean exit (aitask_sync.sh waits for every child it starts; remaining session members are helper daemons such as credential-cache). Unknown membership always fails closed. `setsid()`-detached processes are the documented boundary.
- **Upstream defects identified:**
  - `.aitask-scripts/board/aitask_board.py:5387 — run_aitask_pick / run_codeagent_operation suspend the board and run a code agent with no _sync_edit_lock coordination, so an in-flight or thread-started sync can pull/commit task data under the agent (same class as t1947)`
  - `.aitask-scripts/syncer/syncer_app.py:2249 — _sync_data_worker gets SyncResult.stray_session from run_sync_batch but has no sticky refusal, so its next sync can start while a timed-out sync's unproven session is still running`
