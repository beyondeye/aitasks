---
Task: t1943_board_run_editor_launch_guard.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1943 — Contain the board's `run_editor` launch failures

## Context

`KanbanApp.run_editor` (`.aitask-scripts/board/aitask_board.py:5037`) — reached
from the task detail screen's "edit" / "edit_plan" results — has the defect
t1936 fixed in codebrowser (commit 33b54e172):

- `subprocess.call([editor, path])` runs inside `with self.suspend():` with no
  `OSError` guard. Textual 8.2.7's `App.suspend` resumes the driver after its
  `yield` with no `finally`, so a missing `$EDITOR` leaves the terminal
  suspended and the worker's `exit_on_error` ends the board.
- `$EDITOR="code -w"` / `"emacsclient -t"` is used as one argv[0] → same failure.
- No `SuspendNotSupported` handling.
- `@work(exclusive=True)` in the **default** group, which it shares with
  `_run_sync` (thread), `_run_interactive_sync_shared`, `run_aitask_pick`,
  `run_codeagent_operation` — pressing edit cancels whichever of those is in
  flight (e.g. an in-flight `_run_sync` gets cancelled mid-overlay).

Outcome: editor launch failures are notified after the terminal resumes, the
board keeps running, `$EDITOR` with arguments works, unquoted executable paths
with spaces keep working, and edit no longer cancels the board's other workers.

## Approach

The `$EDITOR` → argv rule (whole-value-first, then POSIX `shlex.split`, Windows
single argv, blank → platform default) is subtle and now needed by two TUIs.
Extract **only that rule** into a small shared lib helper so the two copies
cannot drift; the suspend/notify containment stays per-caller because the
post-launch work differs (codebrowser refreshes annotations, board reloads tasks).

### 1. New `.aitask-scripts/lib/editor_argv.py`

```python
"""Resolve ``$EDITOR`` to an argv prefix for TUI open-in-editor actions (t1943)."""
from __future__ import annotations
import os, shlex, shutil, sys

def resolve_editor_argv() -> list[str]:
    """Return the argv prefix for the user's ``$EDITOR``.

    Blank/unset → ``nano`` (``notepad`` on Windows). A value that names a whole
    executable (an unquoted path with spaces, ``/opt/my editor/bin/ed``) is one
    argv[0]; otherwise it is shlex-split so ``code -w`` carries its arguments.
    Windows always keeps one argv (POSIX shlex would eat path backslashes).

    Raises ValueError (message names the value) when shlex cannot parse it.
    """
    default = "notepad" if sys.platform == "win32" else "nano"
    editor = os.environ.get("EDITOR", "").strip() or default
    if sys.platform == "win32" or shutil.which(editor):
        return [editor]
    try:
        return shlex.split(editor)
    except ValueError as exc:
        raise ValueError(f"Invalid $EDITOR {editor!r}: {exc}") from exc
```

The ValueError text is exactly codebrowser's existing notice, so its label is
preserved byte-for-byte.

### 2. `codebrowser_app.py` — swap the inline rule for the helper

In `action_open_in_editor` replace the `default = …` … `editor_argv = shlex.split`
block with:

```python
try:
    editor_argv = resolve_editor_argv()
except ValueError as exc:
    self.notify(str(exc), severity="error")
    return
```

Import `from editor_argv import resolve_editor_argv`; drop `shlex`/`shutil`
imports only if no other use remains (grep first). Trim the docstring sentence
about shlex-splitting to point at the helper. Containment code unchanged.
Existing `tests/test_codebrowser_open_in_editor.py` pins the behaviour unchanged.

### 3. `aitask_board.py` — contain `run_editor`

```python
@work(exclusive=True, group="editor")
async def run_editor(self, filepath):
    """Suspend the app and open ``filepath`` in $EDITOR.

    <docstring mirroring codebrowser's: own group so edit does not cancel the
    default-group exclusive workers (_run_sync, run_aitask_pick, …); OSError
    caught INSIDE the suspend block (App.suspend has no finally); notify after
    resume; a failed launch skips the reload.>
    """
    try:
        editor_argv = resolve_editor_argv()
    except ValueError as exc:
        self.notify(str(exc), severity="error")
        return
    filename = Path(filepath).name
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
    self.manager.load_tasks()
    self.refresh_board(refocus_filename=filename)
```

Imports: `from textual.app import App, SuspendNotSupported`;
`from editor_argv import resolve_editor_argv` (lib is already on sys.path).

### 4. Tests

- **`tests/test_board_run_editor.py`** — copy the real-`App.suspend` fake-driver
  pattern from `tests/test_codebrowser_open_in_editor.py`: a minimal `App` host
  borrowing the real `KanbanApp.run_editor`, a stub `manager` (records
  `load_tasks`) and `refresh_board` (records `refocus_filename`), a default-group
  `@work(exclusive=True)` blocker. Cases: args split; quoted path; unquoted
  executable path with spaces stays whole; unset/blank → nano; missing editor →
  `suspend, call, resume, notify`, app still running, no reload; no suspend
  support → contained, no reload; malformed `$EDITOR` → notify without suspending;
  success → reload + refocus on filename; edit does not cancel the default-group
  async blocker. Skip on win32 as the codebrowser file does.

  Plus a **threaded overlap** case shaped like `_run_sync`: a
  `@work(exclusive=True, thread=True)` default-group worker that blocks on a
  `threading.Event` (stand-in for `run_sync_batch`'s subprocess) is started
  first; then the editor runs. Assert the editor's `call` happens while the
  thread is still running (the overlap is real, and the editor neither waits
  for it nor cancels it), the threaded worker is not CANCELLED, and after the
  event is released it finishes SUCCESS. This pins today's behaviour; it does
  not claim the overlap is safe. The old exclusive default-group cancel only
  marked such a worker cancelled and never stopped its thread or subprocess.
- **`tests/test_editor_argv.py`** — direct helper unit cases (default, blank,
  split, whole executable, malformed → ValueError message), with `os.environ`
  patched; Windows branch via patching `sys.platform` on the module.

## Verification

```bash
python3 -m pytest -q tests/test_board_run_editor.py tests/test_editor_argv.py tests/test_codebrowser_open_in_editor.py
bash tests/run_all_python_tests.sh --test-dir tests   # last line verdict; or AIT_TEST_PARALLEL default
```
Negative control (scratch only, never in-tree): point the test host at a copy
of the pre-fix `run_editor` and confirm the missing-editor, args-split and
blocker tests fail.

Manual: `EDITOR=nonexistent ait board` → open a task detail → edit: board shows
"Could not launch editor" and keeps running; `EDITOR="code -w"` opens VS Code.

Step 9 (Post-Implementation): current-branch mode, no merge; archive via
`aitask_archive.sh 1943` after the risk_evaluated gate passes.

## Risk

### Code-health risk: low
- Touches t1936's just-landed codebrowser code to share the argv rule; a wrong swap could change codebrowser's notice text or argv · severity: low · → mitigation: None (its 10 existing tests pin argv and notice text unchanged)
- Moving `run_editor` to its own group drops its exclusive-cancel of `_run_sync`. That cancel never gave mutual exclusion. `_run_sync` is a `thread=True` worker, and cancelling it only marks the worker. Its thread and `run_sync_batch`'s `aitask_sync.sh --batch` subprocess keep running while the editor is open, and they did so before this change as well. So a background auto-sync (no overlay) that is already in flight can pull/merge/commit task data while the user edits a task file, before and after t1943. The blocked event loop only prevents a *new* default-group worker from starting mid-edit. The change keeps the overlap as it is and stops marking the sync worker cancelled. The async-blocker test proves cancellation isolation only; the threaded overlap test pins the real overlap · severity: low (pre-existing, unchanged) · → mitigation: None in t1943. Sync/editor coordination is pre-existing debt, recorded under Final Implementation Notes → Upstream defects for a Step 8b follow-up.

### Goal-achievement risk: low
None identified.

## Upstream defect to record (Step 8b)
- `.aitask-scripts/board/aitask_board.py:5063` — `_run_sync` (thread worker running `aitask_sync.sh --batch`) is not coordinated with the board's suspend-and-edit path. An in-flight background sync can pull, merge or commit task data while `$EDITOR` holds the same task file open, and cancelling the worker never stopped its thread or subprocess.
