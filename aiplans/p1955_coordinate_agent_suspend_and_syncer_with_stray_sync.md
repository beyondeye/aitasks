---
Task: t1955_coordinate_agent_suspend_and_syncer_with_stray_sync.md
Base branch: main
Output branch: main
---

# t1955 — Coordinate agent suspends and the syncer with stray syncs

## Context

t1947 (394d9fcea) made `KanbanApp.run_editor` and `_run_sync` mutually
exclusive through `_sync_edit_lock`. It also added a sticky
`_stray_sync_session`: a timed-out sync whose session could not be proven
stopped blocks edits and syncs until `sync_session_running(sid)` is False.
Two areas were left out:

1. **The board's other suspend sites** run a child process that does git work
   on task data while the board is suspended, with no lock and no stray check.
   The task names `run_aitask_pick` and `run_codeagent_operation`. While
   exploring I found two more of the same kind:
   - `TrailScreenMixin.run_dialog_command` (`board_trail_screen.py:1441`). This
     is where every AgentCommandScreen "run" goes on the board: pick from the
     dialog, resume, create, brainstorm, work-report, trail. It is the most
     common way an agent gets launched, so fixing only the two named sites
     would leave most launches unguarded.
   - `KanbanApp._run_interactive_sync_shared` (`aitask_board.py:5246`). This is
     the conflict dialog's interactive `./ait sync`. It is a sync that skips
     the stray check.
2. **The syncer TUI** (`syncer_app.py:2247 _sync_data_worker`) gets
   `SyncResult.stray_session` but keeps no record of it. The next `s` starts a
   new sync right away, alongside the session that was never proven stopped.
   Nothing serialises two of its syncs either: the worker is
   `exclusive=True, thread=True`, and cancelling a thread worker does not stop
   its thread. Nothing that acts on a repo checks for a stray either: the
   conflict modal's interactive sync and agent, and the failure modal's
   recovery agent. A stray timeout is captured as a `SyncFailureContext`, so
   `a` leads straight to that last one. The interactive and agent launches
   also run *later* than the choice (a scheduled worker, then a later screen
   callback), so a check made when the user chooses is too early.

Goal: a board suspend that runs a child process never overlaps a sync, and
nothing starts on a stray. In the syncer, a stray session blocks that repo's
syncs and conflict resolution until the probe proves the session gone, and
the TUI shows a visible notice while it does.

Out of scope: an agent spawned in a **separate terminal** (`find_terminal()`
path) or in tmux. It runs outside the board's process, and the board keeps
syncing; sync's own live-holder deferral (t1731) covers those. Only the
suspend paths, where the board itself runs the child, are coordinated here.

## Design

### Board — one guard, every suspend path

Add one context manager to `KanbanApp` (next to `_stray_sync_blocks`,
`aitask_board.py:~5012`):

```python
@contextlib.contextmanager
def _suspend_sync_guard(self, what: str):
    """Hold ``_sync_edit_lock`` across a suspended child (t1947, t1955).

    Yields True with the lock held, or False — lock NOT held, user notified —
    when a sync is in flight or an unproven timed-out sync may still be
    running. Non-blocking: callers run on the event loop, which must not wait
    on a sync thread; a sync requested while the child runs waits in
    ``_run_sync`` instead. ``what`` names the refused action in the notices.
    """
    if not self._sync_edit_lock.acquire(blocking=False):
        self.notify(f"Sync in progress — {what} again when it finishes",
                    severity="warning")
        yield False
        return
    try:
        if self._stray_sync_blocks():
            self.notify(
                f"A timed-out sync (session {self._stray_sync_session}) may "
                f"still be changing task data — {what} refused until it stops",
                severity="error")
            yield False
            return
        yield True
    finally:
        self._sync_edit_lock.release()
```

With `what="edit"` the notices are **byte-identical** to `run_editor`'s
current ones, which the t1947 tests pin ("Sync in progress",
"edit refused").

Call sites (each `else:` / no-terminal branch only; the terminal-spawn
branches are unchanged):

1. `run_editor`: replace the hand-rolled acquire / stray check / `finally`
   release with `with self._suspend_sync_guard("edit") as allowed: if not
   allowed: return`. Inside it keep the `try: with self.suspend(): …
   except SuspendNotSupported:` block as it is. Behaviour does not change,
   and the docstring paragraph moves to the guard.
2. `run_aitask_pick` and `run_codeagent_operation`:
   ```python
   with self._suspend_sync_guard("launch") as allowed:
       if not allowed:
           return
       with self.suspend():
           ret = subprocess.call([wrapper, "invoke", ...])
   ```
   On a refusal nothing runs, and there is no failure notice and no reload.
3. `_run_interactive_sync_shared`: wrap the `run_interactive_sync(...)` call
   in `_suspend_sync_guard("sync")`. On the terminal-spawn path the lock is
   only held for the moment it takes to spawn. The stray refusal still applies.
4. `run_dialog_command` (mixin, `board_trail_screen.py`): same shape as 2,
   `what="launch"`. `_after_dialog_command` is not called on a refusal.

**Host contract.** `run_dialog_command` is shared with the stand-alone
`ait trails` app, so `_suspend_sync_guard` becomes a `TrailHost` member:
- add `def _suspend_sync_guard(self, what: str): ...` to the `TrailHost`
  Protocol (`board_trail_screen.py:~220`), with a docstring line saying the
  host owns sync coordination for suspended launches;
- `TrailsApp` (`trails_app.py`, next to `_after_dialog_command`) implements it
  as a `contextlib.contextmanager` that just yields True. That app never runs
  a sync: its `S` is refused by the capability guard. A one-line comment says
  so;
- `tests/test_trail_screen_host_protocol.py`: add `"_suspend_sync_guard"` to
  `EXPECTED_MEMBERS`.

`import contextlib` is added to `aitask_board.py` and `trails_app.py` if it is
missing.

Every board guard sits **inside the worker body**: the execution boundary,
not the moment the action was chosen. A launch scheduled before a stray was
recorded is still refused when it actually runs.

### Syncer — per-repo stray record, serialised syncs, guarded at execution

In `SyncerApp.__init__` (`syncer_app.py:~843`):
```python
# A sync never overlaps another or an inline child, and a timed-out sync
# whose session could not be proven stopped blocks ITS repo's syncs and agent
# launches until sync_session_running proves it gone (t1955, mirroring the
# board's t1947). Keyed by _repo_key; read and written only under the lock.
self._sync_data_lock = threading.Lock()
self._stray_sync_sessions: dict[str, int] = {}
```
Import `contextlib`, `threading` and `sync_session_running` (from
`sync_action_runner`).

**Root normalization.** The same repo reaches the syncer spelled three ways:
`ActionTarget.root = None` (single-repo sync), `Path(".")` (the
single-repo failure route, `_launch_resolution_agent`) and the absolute
`sess.project_root` (multi-repo). Add a module-level helper:
```python
def _repo_key(root: Path | None) -> str:
    """One stray-record key per repo, whichever spelling reaches us (t1955)."""
    try:
        return str((root or Path(".")).resolve())
    except OSError:          # cwd gone: no launch can run there anyway
        return str(root or Path("."))
```
Every read and write of `_stray_sync_sessions` goes through `_repo_key`.

- `_stray_sync_blocks(self, root) -> int | None`: the caller holds the lock.
  It returns the sid while `sync_session_running(sid)` holds, and otherwise
  pops the entry and returns None (fail closed, like the board).
- `_task_data_guard(self, root, what, label="")`: a
  `contextlib.contextmanager` with the same shape as the board's guard. It
  takes `_sync_data_lock` **non-blocking**, because every caller runs on the
  event loop. It yields False with a notice in two cases: a sync is in flight
  ("Sync in progress — {what} again when it finishes", warning), or a stray
  blocks this root ("A timed-out sync (session N) may still be changing task
  data — {what} refused until it stops", error). Notices are prefixed with
  `label`. Otherwise it yields True **with the lock held until the block
  exits**.
- `_sync_data_worker`: holds `_sync_data_lock` **blocking** (it is a thread
  worker) around the stray check, `run_sync_batch` and recording
  `result.stray_session`. If the check blocks, it notifies via
  `call_from_thread` with `self._prefix(label, "Sync skipped: a timed-out
  sync (session N) may still be changing task data")` (error) and returns;
  the busy reset stays in the existing `finally`. A second `s`, or an `s`
  pressed while an inline child holds the lock, waits and then sees the
  current state. One lock for all repos is deliberate: it is the simplest
  rule that guarantees no overlap, and each sync is bounded by its timeout.
- `_on_data_sync_done`, `STATUS_TIMEOUT`: when `result.stray_session` is
  set, notify `self._prefix(label, f"Sync: {result.error_message}")` as an
  error. A plain timeout keeps the "Sync timed out" warning. The failure
  capture stays, so `a` still offers the recovery modal, and the guard below
  is what refuses its launch while the stray survives.
- **Execution-boundary guards.** No check is made at choice time; each guard
  wraps the operation itself:
  - `_run_interactive_sync_shared` (the scheduled worker):
    `with self._task_data_guard(target.root, "sync", target.label) as ok:
    if not ok: return` around `run_interactive_sync(...)`. The lock is held
    for the whole inline `./ait sync` suspend. On the terminal-spawn path it
    is held only while spawning.
  - `_launch_agent.on_launch` (the callback that actually launches). This one
    site covers **every** syncer agent: the data-conflict agent and the
    failure-modal recovery agent (`_launch_resolution_agent`), both of which
    go through `_launch_agent`. It wraps both the `TmuxLaunchConfig` branch
    and the `"run"` branch in
    `self._task_data_guard(project_root, "launch")`. The `"run"` branch
    calls `_run_agent_in_terminal` inside the guard, so the lock covers the
    whole inline suspend child. tmux and terminal spawns hold the lock only
    for the spawn itself (the separate-terminal scope is unchanged), but the
    **stray refusal applies to every launch mode**: these agents target the
    very repo whose sync is unproven. `_tick_refresh()` still runs after a
    refusal. `_run_agent_in_terminal` itself is unchanged, so its existing
    `AgentRunInTerminalTests` are unaffected.
  - `_on_conflict_resolved` stays unchanged.

The board's tmux and terminal-spawn launches stay unguarded, as before. That
is the stated scope, and on the board a stray only blocks edits, syncs and
the suspend paths.

## Implementation steps

1. Baseline check before the first edit. t1952 has landed (9605ad7d4), and at
   plan time all seven paths I will touch are clean:
   `.aitask-scripts/board/aitask_board.py`,
   `.aitask-scripts/board/board_trail_screen.py`,
   `.aitask-scripts/board/trails_app.py`,
   `.aitask-scripts/syncer/syncer_app.py`, `tests/test_board_run_editor.py`,
   `tests/test_trail_screen_host_protocol.py`, `tests/test_syncer_rows.py`.
   Re-run `git status --short -- <7 paths>` and expect empty output. If any
   path is dirty again, a concurrent session has fresh edits there: stop and
   ask before editing that file, and do not plan around it.
2. Board: add `_suspend_sync_guard` and refactor `run_editor` onto it.
3. Board: guard `run_aitask_pick`, `run_codeagent_operation`, and
   `_run_interactive_sync_shared`.
4. Mixin + TrailsApp + Protocol + `EXPECTED_MEMBERS`, and guard
   `run_dialog_command`.
5. Syncer: `_repo_key`, the lock, the stray dict, `_stray_sync_blocks`,
   `_task_data_guard`, the worker, the timeout notice, and the
   execution-boundary guards in `_run_interactive_sync_shared` and
   `_launch_agent.on_launch`.
6. Tests: board. Extend `tests/test_board_run_editor.py`, which already has
   the real-App + fake-driver + `_ProbeLock` + `_SyncStandIn` harness:
   `_host_class` also borrows `run_aitask_pick`, `run_codeagent_operation`,
   `run_dialog_command`, `_suspend_sync_guard` and `_after_dialog_command`,
   with `find_terminal` patched to None on both `ab` and
   `ab.board_trail_screen`. The module docstring gets an agent-launch
   paragraph. Add a `SuspendedLaunchTests` class, parametrised over the three
   launch workers (pick, `resume` operation, dialog command):
   - no sync running: `["suspend","call","resume","load"]`, lock free
     afterwards (negative control);
   - sync in flight: launch refused, events `["notify"]`, "Sync in progress"
     warning, no call, no load, the sync completes, lock free;
   - sync started mid-launch from a raw thread (`_start_raw_sync`): it waits
     for the agent to return, then runs;
   - stray: launch refused with "launch refused" while the probe says
     running, and runs once the probe proves the session gone;
   - interactive sync (`_run_interactive_sync_shared`, with
     `run_interactive_sync` stubbed): refused on an in-flight or stray sync,
     and runs otherwise;
   - execution boundary: schedule `run_dialog_command` (the worker has not
     run yet), record `_stray_sync_session = 4242` synchronously before
     yielding to the loop, with the probe returning running. The worker,
     when it runs, refuses: no call, no reload.
   - `TrailsApp._suspend_sync_guard` yields True. Covered by the host-protocol
     member check plus one direct assertion in the protocol test.
7. Tests: syncer. In `tests/test_syncer_rows.py`, add a
   `StraySyncTests(_TabbedShellBase)` class, using `booted` / `settle` and
   patching `syncer_app.run_sync_batch` and `syncer_app.sync_session_running`:
   - a stray timeout records the sid and shows an error notice naming the
     session. The next `_sync_data_worker` for the same root is skipped
     (`run_sync_batch` call count unchanged, "Sync skipped" notice). With the
     probe returning False, the next sync runs and the entry is cleared;
   - multi-repo: a stray on repo1 does not block repo0;
   - a plain timeout (`stray_session=None`) records nothing and keeps the
     "Sync timed out" warning (negative control);
   - overlap: a second worker started while the first is blocked in a
     `_SyncStandIn`-style stand-in does not enter `run_sync_batch` until the
     first returns.

   Launch-timing tests. They reuse `DataConflictAgentTests.agent_seams`
   (stubbed `find_terminal` / `spawn_in_terminal` / `run_interactive_sync` /
   `AgentCommandScreen` spy / `launch_in_tmux`), moved to a shared mixin so
   the new class can use it:
   - **state changes between choice and execution, interactive.** With no
     stray, pick the INTERACTIVE choice, which schedules the worker. Record a
     stray for that root synchronously before the loop runs it, with the probe
     returning running. Then: `calls.interactive == []` and the refusal
     notice is shown;
   - **state changes between choice and execution, agent.** Open the conflict
     agent dialog (spy instance exists), record a stray, then
     `spy.dismiss("run")` and, in a second run, `spy.dismiss(cfg)`. Expect no
     `spawn_in_terminal`, no `launch_in_tmux` and a refusal notice. With the
     probe returning False, the same dismissals launch (negative control);
   - **a sync started during the inline child, interactive.** Inside the
     stubbed `run_interactive_sync`, start the raw `_sync_data_worker` body on
     a plain thread (the board test's `_start_raw_sync` shape). Its
     `run_sync_batch` stand-in is not entered while the child is "open"; it
     is entered after the child returns;
   - **a sync started during the inline child, agent.** Same check through
     `spy.dismiss("run")` → `_run_agent_in_terminal`, with no terminal, a
     fake suspend-capable driver (the board test's `_fake_driver`) and
     `subprocess.call` stubbed to start the sync thread;
   - **the timeout-recovery route** (concern 3, single-repo **and**
     multi-repo, to pin root normalization). A stray timeout from
     `_sync_data_worker` leaves `_last_failure` as a `SyncFailureContext`.
     `action_agent_resolve()` → `SyncFailureScreen` → launch (dismiss True) →
     the AgentCommandScreen spy → dismiss `"run"`: refused, no spawn, refusal
     notice. Once the probe returns False, the same route launches and the
     entry is cleared. The single-repo case is where the record key comes from
     `root=None` and the launch key from `Path(".")`.
8. Commit only this task's paths. Before committing, re-run
   `git status --short -- <7 paths>`. Also read `git diff HEAD -- <7 paths>`
   in full to confirm every hunk is mine: a concurrent session may have
   edited one of these files since step 1. If a foreign hunk appears, stop
   and ask; do not stage around it. With the delta confirmed as t1955-only:
   ```bash
   head0=$(git rev-parse HEAD)
   git add -- <7 paths>
   git commit -m "bug: <subject> (t1955)" -- <7 paths>
   ```
   The pathspec keeps anything another session staged out of the commit.
   Because the diff check just confirmed the working-tree contents of these
   paths are exactly my reviewed changes, the pathspec commit's use of
   working-tree contents is correct here. **Verify the commit, not the
   staging:**
   - `git rev-parse HEAD^` equals `$head0`, so no concurrent commit slipped
     in between;
   - `git show --stat HEAD` lists exactly the 7 paths;
   - `git diff HEAD -- <7 paths>` is empty: the committed contents are the
     working-tree contents that the tests ran against;
   - landed work is preserved: `git show HEAD:.aitask-scripts/board/aitask_board.py`
     still contains t1952's `_owned_tmux_session`, and
     `git diff "$head0" HEAD -- .aitask-scripts/board/aitask_board.py`
     contains only t1955's hunks (`_suspend_sync_guard` and its call sites).

### Post-phase (risk mitigations)

1. [isolated_staged_tree_test] Right after the step-8 commit and **before
   any push**, export the committed snapshot, which is clean by construction
   and unaffected by other sessions' dirty files elsewhere in the tree:
   `mkdir -p <scratch>/tree && git archive HEAD | tar -x -C <scratch>/tree`.
   Run `tests/test_board_run_editor.py`,
   `tests/test_board_dialog_run_dispatch.py`,
   `tests/test_trail_screen_host_protocol.py`, `tests/test_syncer_rows.py`
   and `tests/test_sync_action_runner.py` **from that tree** with
   `~/.aitask/venv/bin/python -m pytest -q`. The tested snapshot is then the
   committed contents by definition. If anything is red, fix it and amend,
   but only while `HEAD` is still this unpushed t1955 commit
   (`git rev-parse HEAD^` == `$head0`). Then re-run this step. Delete
   `<scratch>/tree/` afterwards.

## Verification

- `~/.aitask/venv/bin/python -m pytest -q tests/test_board_run_editor.py
  tests/test_board_dialog_run_dispatch.py tests/test_trail_screen_host_protocol.py
  tests/test_syncer_rows.py tests/test_sync_action_runner.py tests/test_board_sync_conflict_agent.py`
- Mutants, applied one at a time to an isolated scratch copy, never to the
  shared tree: (a) remove the guard from `run_aitask_pick`, (b) from
  `run_dialog_command`, (c) make the syncer worker skip the stray check,
  (d) drop the syncer lock. Each must turn a specific new test red.
- `bash tests/run_all_python_tests.sh --test-dir tests` with
  `set -o pipefail`, reading the last-line verdict.
- Step 9 (Post-Implementation): archival via the standard workflow; there is
  no worktree or branch to merge (current-branch mode).

## Risk

### Code-health risk: medium
- The guard now wraps every board suspend path and the shared mixin, so a
  release bug would wedge every later sync and edit on the board. Bounded:
  the guard is one context manager with `finally`, and each test asserts the
  lock is free afterwards · severity: medium · → mitigation: none (covered by plan tests)
- Shared tree with concurrent sessions. At plan time t1952 has landed and all
  seven paths are clean, but a session could edit one of them mid-task. A
  pathspec commit would then ship the foreign hunks, and the commit would not
  be what was tested. Step 1 and step 8 re-check the paths and refuse if a
  foreign hunk appears. Step 8 verifies HEAD's delta and contents, and the
  post-phase tests the exact committed snapshot · severity: medium · →
  mitigation: inline post-phase isolated_staged_tree_test
- The syncer guard holds `_sync_data_lock` across an inline agent or
  interactive sync, so an `s` pressed meanwhile queues its thread until the
  child returns. That is bounded and intended (the event loop is blocked
  during suspend anyway) · severity: low · → mitigation: none
- A sync requested while a suspended agent runs now waits on the lock for
  the whole agent session (by design, the same as the editor). The board is
  suspended during that time, so nothing is visible to the user ·
  severity: low · → mitigation: none

### Goal-achievement risk: low
- Agents spawned in a separate terminal or in tmux stay uncoordinated with
  the board's syncs. That is outside this task's suspend-site scope and is
  covered by sync's own live-holder deferral · severity: low · → mitigation: none

### Planned mitigations
- timing: post-phase | name: isolated_staged_tree_test | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: a commit whose exact contents were never tested in isolation | desc: run the touched test files from an export of the committed HEAD before pushing
