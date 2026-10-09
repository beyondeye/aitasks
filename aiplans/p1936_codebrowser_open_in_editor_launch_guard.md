---
Task: t1936_codebrowser_open_in_editor_launch_guard.md
Base branch: main
Output branch: main
---

# t1936 — Guard codebrowser `action_open_in_editor` like the shared launch worker

## Context

t1929 hardened codebrowser's run-in-terminal launches into one worker,
`CodeBrowserApp.run_launch_command` (`.aitask-scripts/codebrowser/codebrowser_app.py:1527`):
own worker group, `OSError` caught **inside** `with self.suspend():` (Textual 8.2.7's
`App.suspend` resumes the driver after its yield with no `finally`), and
`SuspendNotSupported` contained. `action_open_in_editor` (`codebrowser_app.py:1079`,
bound to `E`) is the remaining suspend-launch and has none of these:

- `@work(exclusive=True)` in the **default** group → pressing `E` cancels in-flight
  `_load_explain_data` / `_refresh_explain_data` (exclusive, default group);
- `subprocess.call([editor, path])` with a missing/mistyped `$EDITOR` raises
  `FileNotFoundError` → escapes `suspend()` (terminal stays suspended) and the worker
  (`exit_on_error` ends the codebrowser);
- `$EDITOR="code -w"` / `"emacsclient -t"` is passed as a single argv[0] → same failure;
- no `SuspendNotSupported` handling.

## Implementation

### 1. `.aitask-scripts/codebrowser/codebrowser_app.py` — rewrite `action_open_in_editor`

`shlex`, `SuspendNotSupported` are already imported (lines 21, 45).

```python
@work(exclusive=True, group="editor")
async def action_open_in_editor(self) -> None:
    """Suspend the app and open the current file in $EDITOR.

    Own worker group: an exclusive default-group worker would cancel the
    in-flight ``_load_explain_data`` / ``_refresh_explain_data`` annotation
    loading. ``$EDITOR`` is shlex-split so values with arguments
    (``code -w``) work. Same containment as ``run_launch_command``: the
    OSError is caught INSIDE ``with self.suspend():`` (``App.suspend`` has
    no ``finally`` around the driver resume, Textual 8.2.7) and notified
    after resume; an escaping exception would end the codebrowser.
    """
    if not self._current_file_path:
        self.notify("No file selected", severity="warning")
        return
    default = "notepad" if sys.platform == "win32" else "nano"
    editor = os.environ.get("EDITOR", "").strip() or default
    if sys.platform == "win32":
        editor_argv = [editor]   # POSIX shlex would eat path backslashes
    else:
        try:
            editor_argv = shlex.split(editor)
        except ValueError as exc:
            self.notify(f"Invalid $EDITOR {editor!r}: {exc}", severity="error")
            return
    filepath = self._current_file_path
    launch_error: OSError | None = None
    try:
        with self.suspend():
            try:
                subprocess.call([*editor_argv, str(filepath)])
            except OSError as exc:
                launch_error = exc
    except SuspendNotSupported:
        self.notify("This environment cannot suspend the TUI to run $EDITOR.",
                    severity="error")
        return
    if launch_error is not None:
        self.notify(f"Could not launch editor: {launch_error}", severity="error")
        return
    if self.explain_manager:
        self._refresh_explain_data(filepath)
```

Behaviour notes: an empty / whitespace-only `$EDITOR` now falls back to the default
(previously `subprocess.call([""])` crashed). Successful-edit path (refresh explain
data) is unchanged.

### 2. New test `tests/test_codebrowser_open_in_editor.py`

Reuse the real-`App.suspend` fake-driver pattern from
`tests/test_codebrowser_dialog_run_dispatch.py::LaunchWorkerLiveTests`
(`_fake_driver`, shared `events` list, `patch.object(app, "_driver", ...)`).
A minimal `_EditorHost(App)` borrows the **real decorated**
`CodeBrowserApp.action_open_in_editor`, sets `_current_file_path`, a truthy
`explain_manager`, a recording `_refresh_explain_data` stub, and a default-group
exclusive `annotation_blocker` worker (mirrors the t1929 host).

Cases (EDITOR set via `patch.dict(os.environ, ...)`, `cba.subprocess.call` patched):
- `EDITOR="code -w"` → argv `["code", "-w", <path>]`; events `suspend, call, resume`;
  one refresh, no notify.
- unset / whitespace `EDITOR` → argv `["nano", <path>]` (POSIX; skip on win32).
- call raises `FileNotFoundError` → events `suspend, call, resume, notify`; severity
  `error`; app still running; no refresh.
- `can_suspend=False` → no call, single `notify` mentioning "cannot suspend"; running.
- malformed `EDITOR='vim "unterminated'` → no suspend, no call, error notify.
- annotation non-cancellation: start `annotation_blocker`, run the editor worker
  (fake driver), assert blocker not `CANCELLED` and finishes `SUCCESS`.
- no file selected → warning notify, no call.

Red proof: run the new test against the pre-change function (temporarily, in a
scratch copy — not via stash/restore of the shared tree) and confirm the OSError,
arg-split and non-cancellation cases fail.

## Out of scope (flag at Step 8b)

`.aitask-scripts/board/aitask_board.py:5037` `run_editor` has the identical defect
(no OSError guard, unsplit `$EDITOR`, default-group exclusive). Report it as a
follow-up candidate rather than fixing it here.

## Verification

- `python3 -m pytest tests/test_codebrowser_open_in_editor.py -q` (or `python3 tests/test_codebrowser_open_in_editor.py`)
- `python3 -m pytest tests/test_codebrowser_dialog_run_dispatch.py -q` (neighbour still green)
- `bash tests/run_all_python_tests.sh --test-dir tests` is not needed; run the codebrowser
  test modules (`ls tests/test_codebrowser*.py`) via the runner's `--test-dir` only if
  cheap, otherwise the two files above.
- Manual (optional): `EDITOR="nonexistent-editor" ait codebrowser`, press `E` →
  error toast, TUI stays usable.

Step 9 (Post-Implementation): commit code (`bug: … (t1936)`), plan via
`aitask_task_commit.sh`, archive per the workflow.

## Risk

### Code-health risk: low
- Single function in one TUI plus a new test file; mirrors an existing, tested pattern (`run_launch_command`). · severity: low · → mitigation: none needed

### Goal-achievement risk: low
- `shlex.split` is POSIX-only by design; Windows keeps the single-argv behaviour, so `$EDITOR` with arguments remains unsupported there. Codebrowser's inline suspend path is not a Windows target, so this is accepted rather than mitigated. · severity: low · → mitigation: none needed
