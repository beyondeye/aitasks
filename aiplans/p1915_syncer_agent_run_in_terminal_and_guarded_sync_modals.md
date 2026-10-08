---
Task: t1915_syncer_agent_run_in_terminal_and_guarded_sync_modals.md
Base branch: main
Output branch: main
---

# t1915 — Syncer "Run in terminal" + guarded sync modals

## Context

Two upstream defects surfaced during t1911's review:

1. `SyncerApp._launch_agent` (`.aitask-scripts/syncer/syncer_app.py:2496-2525`)
   pushes `AgentCommandScreen` but its `on_launch` callback only handles a
   `TmuxLaunchConfig` result. The dialog's **"Run in terminal"** button
   dismisses with `"run"`, which falls through silently — so the button does
   nothing for both the failure-resolution agent and the t1911 data-conflict
   agent. In the syncer the target may be *another* repo (multi-repo rows), so
   the spawn must run in `project_root`, not the syncer's cwd.
2. `SyncConflictScreen` (`.aitask-scripts/lib/sync_action_runner.py:496`, shared
   with the board) and `SyncFailureScreen`
   (`.aitask-scripts/syncer/sync_failure_screen.py:26`) derive from bare
   `ModalScreen`, against the `GuardedModalScreen` rule in
   `aidocs/framework/tui_conventions.md`. Textual 8.2.7's `Screen.dismiss`
   calls `app.pop_screen()` unconditionally, so a stale `action_cancel` (Esc)
   on an already-closed conflict/failure modal pops whatever is on top — the
   `AgentCommandScreen` the modal just opened.

## Implementation

### 1. Handle `"run"` in the syncer agent callback (`syncer_app.py`)

- Import `find_terminal` and `spawn_in_terminal` **by name** into the existing
  `from agent_launch_utils import (...)` block (same "patchable seam on
  `syncer_app`" reason as the other impure imports there). Add `import shlex`.
- In `_launch_agent.on_launch`, add an `elif result == "run":` branch calling a
  new `self._run_agent_in_terminal(screen.full_command, project_root)` — using
  `screen.full_command` (the user-edited command, t1225 rule), never a rebuilt one.
  Keep the trailing `self._tick_refresh()`.
- New method, mirroring brainstorm's `_dispatch_argv`
  (`brainstorm/brainstorm_app.py:3072-3080`) and tui_switcher's `"run"` branch
  (`lib/tui_switcher.py:1254-1262`):

  ```python
  def _run_agent_in_terminal(self, full_command: str, project_root: Path) -> None:
      """Run the dialog's finalized command in ``project_root`` (t1915).

      A multi-repo row's agent must run in ITS repo. ``cwd=`` alone is not
      enough: some terminals (gnome-terminal's server, xdg-terminal-exec) do
      not start the child in the spawner's cwd, so the shell cds first. The
      newline keeps any ``;`` / ``||`` in the command out of the cd's scope.
      """
      root = str(project_root)
      script = f"cd -- {shlex.quote(root)} || exit 1\n{full_command}"
      argv = ["sh", "-c", script]
      terminal = find_terminal()
      # Runs in a screen-result callback: an escaping exception would end the
      # syncer. A vanished repo dir (cwd=) or a broken terminal binary raises
      # OSError before the shell ever starts.
      if terminal:
          try:
              spawn_in_terminal(terminal, argv, cwd=root)
          except OSError as exc:
              self._notify_launch_error(root, exc)
          return
      ret = 0
      launch_error: OSError | None = None
      try:
          with self.suspend():
              try:
                  ret = subprocess.call(argv, cwd=root)
              except OSError as exc:
                  # Caught INSIDE the block: App.suspend resumes the driver
                  # after its yield with no `finally` (Textual 8.2.7), so an
                  # exception leaving the block would keep the terminal
                  # suspended. Notify only after the context has restored it.
                  launch_error = exc
      except SuspendNotSupported:
          self.notify(
              "No terminal emulator found and this environment cannot "
              "suspend the TUI to run the agent inline.",
              severity="error",
          )
          return
      if launch_error is not None:
          self._notify_launch_error(root, launch_error)
      elif ret != 0:
          self.notify(f"Agent command exited with status {ret}", severity="error")
  ```

  `_notify_launch_error(root, exc)` is a one-line helper
  (`self.notify(f"Could not launch agent in {root}: {exc}", severity="error")`).
  Import `SuspendNotSupported` from `textual.app` (add it to the existing
  `from textual.app import ...` line). Only `OSError` (process-start failures)
  and `SuspendNotSupported` are caught — anything else is a real fault and must
  surface.

### 2. Re-base the two modals on `GuardedModalScreen`

- `lib/sync_action_runner.py`: `from guarded_dismiss import GuardedModalScreen`
  (lib/ is already on the module's sys.path — it imports `agent_launch_utils`
  the same way), `class SyncConflictScreen(GuardedModalScreen)`. Drop the now
  unused `ModalScreen` import if nothing else uses it; update the module
  docstring line 13 (`Textual ModalScreen` → `GuardedModalScreen`).
- `syncer/sync_failure_screen.py`: same base change; the syncer process already
  has `lib/` on `sys.path` (it imports `agent_launch_utils`), verify the import
  works from the test harness too.
- Dismiss values unchanged: `CONFLICT_CHOICE_AGENT` / `CONFLICT_CHOICE_INTERACTIVE`
  / `None`; `True` / `False`. Call sites stay plain `self.dismiss(...)`.

### 3. Tests (`tests/test_syncer_rows.py`, in `DataConflictAgentTests`)

Extend `agent_seams()` to also patch `syncer_app.find_terminal` and
`syncer_app.spawn_in_terminal` (recording `(terminal, argv, kwargs)`), so no
test can spawn a real terminal.

Both run tests set `spy.full_command = "claude --model edited 'resolve'"`
(distinct from the dry-run seam's `claude 'resolve'`) before
`spy.dismiss("run")`, and assert the script is exactly
`f"cd -- {root} || exit 1\nclaude --model edited 'resolve'"` — so dispatching the
original `full_cmd` instead of the user-edited `screen.full_command` fails.

- `test_run_in_terminal_spawns_in_the_conflicting_repo` — two repos, conflict →
  click `#btn_sync_agent` → edit + `spy.dismiss("run")`; assert one spawn with
  `argv[:2] == ["sh", "-c"]`, the exact script above, `cwd` is the repo1 root,
  and `seams.launches == []` (no tmux launch).
- `test_run_without_terminal_runs_inline_in_the_failed_repo` — failure route:
  set `_last_failure = SyncFailureContext(..., repo_root="/tmp/repo1")`,
  `action_agent_resolve()` → click `#btn_failure_launch` → edit +
  `spy.dismiss("run")` with `find_terminal` → `None`, `app.suspend` patched to
  `nullcontext`, `syncer_app.subprocess.call` patched to record and return 1;
  assert the exact script and `cwd`, and that an error notification was raised.
- `test_terminal_spawn_oserror_notifies_and_keeps_the_app` — via the dialog:
  `spawn_in_terminal` raises `FileNotFoundError`; assert an error notification
  naming the root, `app.is_running`, and the app still usable
  (`action_agent_resolve()` reopens the modal afterwards).
- **Inline terminal-restoration tests use the REAL `App.suspend`** (a
  `nullcontext` stub cannot prove restoration). Call
  `app._run_agent_in_terminal(cmd, root)` directly with `find_terminal` → `None`
  and `app._driver` patched (only around the call) to a `MagicMock` with
  `can_suspend=True` and `no_automatic_restart=lambda: contextlib.nullcontext()`:
  - `subprocess.call` raises `FileNotFoundError` → exactly one
    `suspend_application_mode` and one `resume_application_mode` call, then one
    error notification naming the root. Red proof: move the `except OSError`
    outside the `with` and confirm resume count drops to 0.
  - `subprocess.call` returns 1 → one suspend, one resume, exit-status
    notification.
  - a driver with `can_suspend=False` → `SuspendNotSupported` is contained, one
    error notification, no exception.
- `test_stale_conflict_cancel_keeps_the_agent_dialog` — conflict → click agent
  → `self.assertIs(app.screen, spy)` → call the (closed) conflict screen's
  `action_cancel()` twice → `app.screen` is still `spy`, app running.
- `test_stale_failure_cancel_keeps_the_agent_dialog` — same via the failure
  modal.
- Red proof: temporarily revert each base to `ModalScreen` (edit + re-edit,
  no stash/restore) and confirm the two stale-cancel tests fail; temporarily
  remove the `"run"` branch and confirm the run tests fail.

## Verification

- `python -m pytest tests/test_syncer_rows.py -q` (via
  `~/.aitask/venv/bin/python`), plus `tests/test_brainstorm_guarded_dismiss.py`
  and any board test that pushes `SyncConflictScreen`
  (`grep -l SyncConflictScreen tests/`).
- `bash tests/run_all_python_tests.sh --test-dir tests` — read the last-line
  verdict only.
- Step 9 (Post-Implementation): no separate branch (fast profile, current
  branch); archive via `aitask_archive.sh 1915`.

## Risk

### Code-health risk: low
- `SyncConflictScreen` is shared with the board (`board/aitask_board.py:5135`), so the base change reaches it too; active-screen dismiss behaviour is identical and only stale dismisses change · severity: low · → mitigation: none (covered by the existing board/syncer suites in Verification)

- A process-start `OSError` (vanished repo dir, broken terminal binary) escaping the screen-result callback would end the syncer · severity: low (residual — handled by the `except OSError` branches, the inline one inside `suspend()` so the driver is resumed) · → mitigation: none (pinned by the spawn-OSError test and the real-`App.suspend` restoration tests)

### Goal-achievement risk: low
- Terminals that ignore the spawner's cwd would start the agent in the wrong repo · severity: low · → mitigation: none (addressed in design by the explicit `cd --` prefix, pinned by the run-in-terminal test)
