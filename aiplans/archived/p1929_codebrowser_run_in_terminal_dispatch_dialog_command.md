---
Task: t1929_codebrowser_run_in_terminal_dispatch_dialog_command.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1929 — Codebrowser "Run in terminal" dispatches the dialog's `full_command`

## Context

`AgentCommandScreen.run_terminal()` stores in-dialog edits into `screen.full_command`, and the
agent/model/profile controls regenerate it (the t1225 rule). The board, brainstorm, tui_switcher
and (since t1915) syncer all dispatch that string verbatim through `["sh", "-c", full_command]`.
Codebrowser's three dialog consumers still **rebuild default argv** in their `"run"` branch, so the
terminal launches a different configuration from the one the dialog showed:

| Site | `"run"` branch today | Also rebuilds? |
|---|---|---|
| `codebrowser_app.py` `action_launch_agent` (explain) | `_run_agent_command("explain", arg)` → `[wrapper, "invoke", "explain", arg]` | yes |
| `history_screen.py` `action_launch_qa` | `_run_qa_command(task_id)` → `[wrapper, "invoke", "qa", task_id]` | yes |
| `codebrowser_app.py` `action_create_task` | `_run_create_from_selection(ref_arg)` → `[create_script, "--file-ref", ref_arg]` | **yes** (the task asked to check this one; it drops hand edits too) |

The tmux branch of each callback already uses `screen.full_command`; only the run-in-terminal branch
diverges. Also, none of these workers guard against launch errors: they are `@work` workers (default
`exit_on_error=True`), so an `OSError` from `spawn_in_terminal` / `subprocess.call` (a broken terminal
binary, a vanished cwd) or `SuspendNotSupported` **ends the codebrowser**.

## Approach

One shared launch worker on `CodeBrowserApp`. Every run-in-terminal route uses it, both the dialog
dispatch and the no-dialog fallback, which still rebuilds argv. It follows the t1915
`syncer_app._run_agent_in_terminal` error handling. `HistoryScreen` already relies on its app being
`CodeBrowserApp` (`self.app._history_index`, …), so it calls `self.app.run_launch_command(...)`.

## Steps

### 1. `codebrowser_app.py`: add the shared worker, remove the per-branch workers

- Import `SuspendNotSupported` from `textual.app` (add to the existing `from textual.app import App, ComposeResult`).
- Replace `_run_agent_command` and `_run_create_from_selection` with:

```python
@work(exclusive=True, group="launch")
async def run_launch_command(self, argv: list[str], *, refresh_explain: bool = False) -> None:
    """Run ``argv`` in a new terminal, or inline under ``suspend()``.

    Dialog "run" branches pass ``["sh", "-c", screen.full_command]``: the dialog
    stores the user's edits and agent/profile changes there, so rebuilding default
    wrapper argv would silently launch a different configuration (t1225, t1929).
    Only the no-dialog fallback passes rebuilt argv.

    An escaping exception would end the codebrowser (worker exit_on_error), so
    launch failures are notified instead. The inline OSError is caught INSIDE
    ``with self.suspend():`` — Textual 8.2.7's ``App.suspend`` resumes the driver
    with no ``finally``, so an exception leaving the block would keep the
    terminal suspended (t1915).
    """
    cwd = str(self._project_root)
    terminal = _find_terminal()
    if terminal:
        try:
            spawn_in_terminal(terminal, argv, cwd=cwd)
        except OSError as exc:
            self.notify(f"Could not launch command: {exc}", severity="error")
        return
    launch_error: OSError | None = None
    try:
        with self.suspend():
            try:
                subprocess.call(argv, cwd=cwd)
            except OSError as exc:
                launch_error = exc
    except SuspendNotSupported:
        self.notify(
            "No terminal emulator found and this environment cannot "
            "suspend the TUI to run the command inline.",
            severity="error",
        )
        return
    if launch_error is not None:
        self.notify(f"Could not launch command: {launch_error}", severity="error")
    elif refresh_explain:
        self.action_refresh_explain()
```

**Dedicated worker group `"launch"` (review finding).** Textual 8.2.7's `WorkerManager.add_worker`
cancels every worker with the same owner node and group when an exclusive worker is registered.
`_load_explain_data` and `_refresh_explain_data` are `@work(exclusive=True)` in the implicit
`"default"` group on the App. With a default-group launcher, a launch would cancel in-flight annotation
loading. Explain and create already do that today, and QA would start doing it once its worker
moves from `HistoryScreen` to the App. With the dedicated group, launches cancel only earlier launches
(the same double-launch guard as before), never annotation work.

(The non-zero exit code is still not reported, as before. An explain or create session that the user cancels is not a failure, and the task does not ask for that change.)

- Add a small private helper for the fallback argv: `_codeagent_argv(operation, arg)` →
  `[str(self._project_root / ".aitask-scripts" / "aitask_codeagent.sh"), "invoke", operation, arg]`.
- `action_launch_agent`:
  - `"run"` → `self.run_launch_command(["sh", "-c", screen.full_command])`
  - no-dialog fallback (`full_cmd` is None) → `self.run_launch_command(self._codeagent_argv("explain", arg))`
- `action_create_task`:
  - `"run"` → `self.run_launch_command(["sh", "-c", screen.full_command], refresh_explain=True)`
    (keeps the old inline-only explain refresh after a create; the terminal path never refreshed).
  - **Quote the executable in the default command (review finding).** Today
    `full_cmd = f"{create_script} --file-ref {shlex.quote(ref_arg)}"` and `full_cmd = create_script`
    interpolate the script path unquoted. Under `sh -c`, a project root like `/tmp/My Project` runs
    `/tmp/My`. The tmux branch already has this bug, and the old direct-argv `"run"` path did not.
    Both forms become `shlex.quote(create_script)` (+ ` --file-ref {shlex.quote(ref_arg)}`). That fixes
    the run branch and the tmux branch together. The explain and QA defaults come from the wrapper's
    `--dry-run` (`env AITASK_AGENT_STRING=… <agent> …`), which carries no project path, so they need no change.

### 2. `history_screen.py`: route QA through the shared worker

- `action_launch_qa`:
  - `"run"` → `self.app.run_launch_command(["sh", "-c", screen.full_command])`
  - fallback → `self.app.run_launch_command(self.app._codeagent_argv("qa", task_id))`
- Delete `_run_qa_command`. Then drop the `_find_terminal`, `spawn_in_terminal`, `subprocess` and `work` imports, but only after a grep confirms nothing else in the file uses them.

### 3. Tests: new `tests/test_codebrowser_dialog_run_dispatch.py`

Modelled on `tests/test_board_dialog_run_dispatch.py`. The setup is `sys.path` for `codebrowser/` + `lib/`, a `MagicMock` app, and unbound
method calls. `OVERRIDE = "opencode run --model x '/aitask-explain foo.py'"` is the edited value.

- **Construction-spy tests** (each action's dismiss callback; `resolve_agent_binary`, `shutil.which`,
  `resolve_dry_run_command` (default value ≠ OVERRIDE), `resolve_agent_string`, `resolve_skill_profile`
  patched on the module that reads them):
  - explain: pop `(screen, callback)` from `app.push_screen`, set `screen.full_command = OVERRIDE`,
    `callback("run")` → `app.run_launch_command.assert_called_once_with(["sh", "-c", OVERRIDE])`.
  - create: same, asserting `refresh_explain=True`.
  - QA: `HistoryScreen.action_launch_qa(screen_mock)` with `screen_mock.query_one` returning a detail
    whose `_nav_stack == ["42"]`; asserting on `screen_mock.app.run_launch_command`.
- **Negative controls**: with `resolve_dry_run_command` returning `None`, explain and QA push no screen and
  call `run_launch_command` with the rebuilt `[wrapper, "invoke", op, arg]`. In the tmux branch,
  `callback(TmuxLaunchConfig(...))` still calls `launch_in_tmux(OVERRIDE, cfg)` (patched).
- **Dead-helper pin**: `_run_agent_command`, `_run_create_from_selection` (on `CodeBrowserApp`) and
  `_run_qa_command` (on `HistoryScreen`) are gone.
- **Worker tests** (`CodeBrowserApp.run_launch_command.__wrapped__` run with `asyncio.run` on a `MagicMock` app,
  `find_terminal` / `spawn_in_terminal` / `subprocess.call` always patched):
  - terminal path: `spawn_in_terminal("footerm", argv, cwd=root)`; nothing refreshed.
  - terminal `OSError` → `app.notify(..., severity="error")`, no exception escapes.
  - inline path (`app.suspend = contextlib.nullcontext`): `subprocess.call(argv, cwd=root)`; with
    `refresh_explain=True` → `action_refresh_explain` called once; without it → not called.
  - inline `OSError` → notify, no refresh.
  - `SuspendNotSupported` from `app.suspend` → notify, `subprocess.call` not called.
- **Create default command survives a project root with spaces (review finding).** In a temp dir
  `"My Project"`, write an executable stub `.aitask-scripts/aitask_create.sh` that writes its argv to a
  marker file. Drive `action_create_task` (mock app with `_project_root` = that dir) for two cases,
  with a file selection and without one. Take the **default** `screen.full_command` (no override), run
  it for real with `subprocess.run(["sh", "-c", cmd])`, and assert the marker shows the stub ran with
  the expected `--file-ref` argv. The edited-command spy cannot catch this, because the override
  replaces the faulty default.
- **Real `App.suspend` ordering and worker isolation (review findings).** Use a lightweight host
  `App` that borrows the real method (`run_launch_command = CodeBrowserApp.run_launch_command`) and
  sets `_project_root`. Boot it under `App.run_test`, following `tests/test_syncer_rows.py:3230-3282`:
  - inline `OSError`: patch `app._driver` with the fake driver (`can_suspend=True`,
    `no_automatic_restart` → `nullcontext`, suspend and resume append to one shared `events` list),
    patch `find_terminal` → `None`, make `subprocess.call` append `"call"` and then raise `FileNotFoundError`,
    and capture `notify` into the same list. `await worker.wait()` inside the patches, then assert
    `events == ["suspend", "call", "resume", "notify"]` and `app.is_running`. Moving the handler
    outside the `with` block drops `"resume"` before `"notify"` and fails this test.
  - `can_suspend=False` → `SuspendNotSupported` is contained: one error notice, `call` never runs.
  - overlap: the host also defines `_annotation_blocker`, decorated `@work(exclusive=True)` in the
    default group to mirror `_load_explain_data` / `_refresh_explain_data`, which awaits an
    `asyncio.Event`. Start it, start `run_launch_command` (terminal path stubbed), pause, and assert
    the blocker worker is not `CANCELLED`. Then set the event and assert it reaches `SUCCESS`. Negative
    control during implementation: dropping `group="launch"` must make this test fail.

## Verification

- `python3 -m pytest tests/test_codebrowser_dialog_run_dispatch.py -q` (or `unittest` if pytest is absent).
- Regression: `tests/test_codebrowser_startup_focus.py`, `tests/test_board_dialog_run_dispatch.py`, `tests/test_monitor_completed_status.py`.
- Red proofs, each a temporary edit-and-undo in the working tree (never a git stash or restore). Each one must turn exactly its targeted test red:
  (a) revert one `"run"` branch to the rebuild → its spy test fails;
  (b) unquote `create_script` → the spaces test fails;
  (c) drop `group="launch"` → the overlap test fails;
  (d) move the inline `except OSError` outside `with self.suspend():` → the event-order test fails.
- `python3 -m pyflakes` / `py_compile` on the two edited modules, to catch unused imports.

## Risk

### Code-health risk: low
- Dispatching the dry-run string through `sh -c` instead of `wrapper invoke` could, in principle, lose wrapper-side setup. In practice the tmux branch of the same callbacks already launches this exact string, and the t1850 `env AITASK_AGENT_STRING=…` prefix carries the env export. · severity: low · → mitigation: none (pinned by step 3 spy tests)
- Removing `_run_agent_command` / `_run_create_from_selection` / `_run_qa_command`: a grep over `.aitask-scripts/` and `tests/` found no other callers. · severity: low · → mitigation: none (dead-helper pin in step 3)
- Moving create's `"run"` branch onto `sh -c` exposes the unquoted default script path, so a project root with spaces breaks. That is now a plan step (quote it) and is pinned by a real-execution test. · severity: low (residual) · → mitigation: none (in-plan step + test)
- A shared App-level exclusive worker could cancel annotation loading. The dedicated `"launch"` group prevents it, and a real-Textual overlap test pins it. · severity: low (residual) · → mitigation: none (in-plan step + test)

### Goal-achievement risk: low
None identified.

## Step 9 (Post-Implementation)

Commit the code (`bug: … (t1929)`), commit the plan through `./ait git`, then archive per task-workflow Step 9.

## Final Implementation Notes
- **Actual work done:** Added `CodeBrowserApp.run_launch_command(argv, *, refresh_explain=False)` — `@work(exclusive=True, group="launch")` — plus `_codeagent_argv(operation, arg)` for the no-dialog fallback. Explain, create and history-QA "run" branches now dispatch `["sh", "-c", screen.full_command]`; the explain/QA fallbacks dispatch rebuilt wrapper argv through the same worker. Removed `_run_agent_command`, `_run_create_from_selection` and `HistoryScreen._run_qa_command` (and history_screen's now-unused `subprocess` / `find_terminal` / `spawn_in_terminal` imports). The create dialog's default command now `shlex.quote`s the script path in both forms, which also fixes its tmux branch for project roots with spaces. New `tests/test_codebrowser_dialog_run_dispatch.py` (21 tests).
- **Deviations from plan:** None in substance. The plan was revised before approval to add three review findings: quoting the create script path, the dedicated `"launch"` worker group, and real-`App.suspend` ordering tests. The space-root test runs the default command via `os.spawnvp("sh", ...)`, and its stub writes one argv entry per line through a loop, because `printf '%s\n'` with no args emits an empty line.
- **Issues encountered:** The full suite's serial carve-out had one failure in `tests/test_minimonitor_bottom_pin_live.py::test_2_the_press_hit_the_thumb`. That live tmux test is unrelated to codebrowser and passed 6/6 on an isolated re-run. The parallel lane had 8500 passed, 2 skipped.
- **Key decisions:** The worker lives on the App (HistoryScreen already depends on its app being CodeBrowserApp). A non-zero exit is still not reported (unchanged behaviour; cancelling create is not a failure). All four red proofs were mutate-and-restore runs, each failing exactly its targeted test: the run branch reverted to rebuild, the script path unquoted (both forms), `group="launch"` dropped, and the OSError handler moved outside `suspend()`.
- **Upstream defects identified:**
  - .aitask-scripts/codebrowser/codebrowser_app.py:1079 — action_open_in_editor runs subprocess.call([editor, path]) inside `with self.suspend():` with no OSError guard (a missing $EDITOR binary raises, which ends the codebrowser and leaves the terminal suspended); an $EDITOR with arguments (e.g. "code -w") is also treated as one executable name; and as an exclusive default-group worker it cancels in-flight explain-annotation loading

