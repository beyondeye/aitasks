---
Task: t573_3_tui_init_modal_file_picker.md
Parent Task: aitasks/t573_import_initial_proposal_in_brainstrom.md
Sibling Tasks: aitasks/t573/t573_4_docs_and_seed_config.md, aitasks/t573/t573_5_manual_verification_import_initial_proposal.md
Archived Sibling Plans: aiplans/archived/p573/p573_1_initializer_agent_and_ingestion.md, aiplans/archived/p573/p573_2_cli_proposal_file_flag.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-23 12:41
---

# t573_3 — TUI init modal: three-button `InitSessionModal` + file picker + poll-and-apply (verified refresh)

## Context

Parent task t573 adds support for importing an external markdown proposal when
initializing a brainstorm session. Siblings t573_1 (initializer agent type +
`apply_initializer_output`) and t573_2 (CLI `--proposal-file` flag +
`RUNNER_STARTED:` / `RUNNER_START_FAILED:` markers) are archived. This child
surfaces the feature in the `ait brainstorm <N>` TUI: when no session exists,
the user must be able to choose between **Blank**, **Import Proposal…**, or
**Cancel**. The import path opens a markdown-filtered file picker, shells to
`ait brainstorm init <N> --proposal-file <path>`, then polls
`<session_path>/initializer_bootstrap_status.yaml` and calls
`apply_initializer_output(task_num)` once the agent completes.

The external plan file `aiplans/p573/p573_3_tui_init_modal_file_picker.md`
already exists, was approved, and has been re-verified against the current
codebase on 2026-04-23. This refresh adds a `plan_verified` entry and two
small robustness corrections:

1. **Parse `RUNNER_START_FAILED:` from stderr.** The CLI in t573_2 emits
   `RUNNER_STARTED:<crew>` on stdout on success and
   `RUNNER_START_FAILED:<crew>` on stderr when the runner auto-start fails but
   the CLI still returns 0. Without this check, the TUI would start polling
   for a status file that will never appear.
2. **Use the `ProjectFileTree`-style subclass pattern** for restricting the
   DirectoryTree to markdown files (overriding `filter_paths` on a subclass),
   rather than instance-attribute assignment. `filter_paths` is a method on
   Textual's `DirectoryTree`, and subclass override matches the pattern at
   `.aitask-scripts/codebrowser/file_tree.py:67` (`ProjectFileTree`).

## Codebase Verification (2026-04-23)

| Plan reference | Current state | Match? |
|---|---|---|
| `InitSessionModal` — `brainstorm_app.py:171-199` | same two-button modal | ✓ |
| `_on_init_result` — `brainstorm_app.py:3043-3048` | boolean-based handler | ✓ |
| `_run_init` — `brainstorm_app.py:3050-3065` | shells to `ait brainstorm init` | ✓ |
| `BrainstormApp.__init__` — `brainstorm_app.py:1238-1254` | sets `self.session_path = crew_worktree(task_num)` on line 1242 | ✓ |
| `_load_existing_session` — `brainstorm_app.py:1727-1738` | loads session + DAG | ✓ |
| `_update_title_from_task` — `brainstorm_app.py:1266` | exists | ✓ |
| Imports: `crew_worktree`, `load_session`, `read_yaml` | already imported at top of file | ✓ |
| `apply_initializer_output` | defined at `brainstorm_session.py:264` | ✓ |
| `ProjectFileTree(DirectoryTree)` subclass pattern | `codebrowser/file_tree.py:67` | ✓ |
| CLI markers emitted by `cmd_init` | `SESSION_PATH:` / `INITIALIZER_AGENT:initializer_bootstrap` / stdout `RUNNER_STARTED:` / stderr `RUNNER_START_FAILED:` | ✓ (per archived p573_2 Final Implementation Notes) |

## Implementation Plan

### 1. `InitSessionModal` — three buttons

Replace the body of `InitSessionModal` (`.aitask-scripts/brainstorm/brainstorm_app.py:171-199`). The
new compose/handlers return `"blank" | f"import:{abs_path}" | None` via
`dismiss`:

```python
class InitSessionModal(ModalScreen):
    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, task_num: str):
        super().__init__()
        self.task_num = task_num

    def compose(self) -> ComposeResult:
        with Container(id="init_dialog"):
            yield Label(
                f"No brainstorm session for t{self.task_num}", id="init_title"
            )
            yield Label("How would you like to initialize the session?")
            with Horizontal(id="init_buttons"):
                yield Button("Initialize Blank", variant="default", id="btn_init_blank")
                yield Button("Import Proposal…", variant="primary", id="btn_init_import")
                yield Button("Cancel", variant="default", id="btn_cancel")

    @on(Button.Pressed, "#btn_init_blank")
    def on_blank(self) -> None:
        self.dismiss("blank")

    @on(Button.Pressed, "#btn_init_import")
    def on_import(self) -> None:
        self.app.push_screen(
            ImportProposalFilePicker(),
            callback=self._on_picker_result,
        )

    def _on_picker_result(self, path: str | None) -> None:
        if path:
            self.dismiss(f"import:{path}")
        # On None, stay in the modal — user can still pick Blank or Cancel.

    @on(Button.Pressed, "#btn_cancel")
    def cancel(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
```

### 2. `ImportProposalFilePicker(ModalScreen)` — new class

Insert after `InitSessionModal` (before `DeleteSessionModal` at line 202).
Import `DirectoryTree` at the top of the file (add to the existing
`from textual.widgets import (...)` block) rather than inline. Use the
subclass pattern per `codebrowser/file_tree.py:67`:

```python
class _MarkdownOnlyDirectoryTree(DirectoryTree):
    """DirectoryTree that only lists directories + markdown files."""

    def filter_paths(self, paths):
        return [
            p for p in paths
            if p.is_dir() or p.suffix.lower() in (".md", ".markdown")
        ]


class ImportProposalFilePicker(ModalScreen):
    """Markdown-only file picker for the initial proposal import flow."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def compose(self) -> ComposeResult:
        with Container(id="import_picker_dialog"):
            yield Label(
                "Select a markdown file for the initial proposal",
                id="import_picker_title",
            )
            yield _MarkdownOnlyDirectoryTree(".", id="import_picker_tree")
            yield Label("↵ select  esc cancel", id="import_picker_footer")

    def on_directory_tree_file_selected(self, event) -> None:
        self.dismiss(str(Path(event.path).resolve()))

    def action_cancel(self) -> None:
        self.dismiss(None)
```

### 3. `_on_init_result` — three-way branch

Replace `brainstorm_app.py:3043-3048`:

```python
def _on_init_result(self, result: str | None) -> None:
    """Handle InitSessionModal result."""
    if result is None:
        self.exit()
    elif result == "blank":
        self._run_init()  # unchanged
    elif isinstance(result, str) and result.startswith("import:"):
        path = result[len("import:"):]
        self._run_init_with_proposal(path)
    else:
        self.notify(f"Unknown init result: {result!r}", severity="error")
        self.exit()
```

### 4. `_run_init_with_proposal(path)` — threaded shell-out

Add immediately after `_run_init` (~line 3065). Parse both
`INITIALIZER_AGENT:` (required) and `RUNNER_START_FAILED:` (error surface).
Only start polling when the runner has actually started:

```python
@work(thread=True)
def _run_init_with_proposal(self, path: str) -> None:
    """Shell to `ait brainstorm init <N> --proposal-file <path>`, then poll."""
    result = subprocess.run(
        [AIT_PATH, "brainstorm", "init", self.task_num,
         "--proposal-file", path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        msg = result.stderr.strip() or result.stdout.strip()
        self.call_from_thread(
            self.notify, f"Init failed: {msg}", severity="error"
        )
        self.call_from_thread(self.exit)
        return

    # Parse stdout markers
    agent_name = "initializer_bootstrap"
    for line in result.stdout.splitlines():
        if line.startswith("INITIALIZER_AGENT:"):
            agent_name = line.split(":", 1)[1].strip()
            break

    # Check stderr for runner-start failure (cmd_init may succeed but
    # start_runner() may have returned False).
    if "RUNNER_START_FAILED:" in result.stderr:
        self.call_from_thread(
            self.notify,
            "Initializer agent registered but runner failed to start. "
            "Run `ait crew runner --crew brainstorm-"
            f"{self.task_num}` manually.",
            severity="error",
        )
        self.call_from_thread(self.exit)
        return

    self.call_from_thread(self._start_initializer_wait, agent_name)
```

### 5. `_start_initializer_wait(agent_name)` — main-thread setup

Add right after `_run_init_with_proposal`:

```python
def _start_initializer_wait(self, agent_name: str) -> None:
    """Main-thread setup: show placeholder DAG + start polling timer."""
    self._initializer_agent = agent_name
    self._initializer_done = False
    self.session_data = load_session(self.task_num)
    self._update_title_from_task()
    self._load_existing_session()  # placeholder n000_init already exists
    self.notify(f"Waiting for {agent_name} to complete…")
    self._initializer_timer = self.set_interval(2, self._poll_initializer)
```

### 6. `_poll_initializer`

Add right after `_start_initializer_wait`:

```python
def _poll_initializer(self) -> None:
    """Timer tick: check initializer_bootstrap_status.yaml, apply on Completed."""
    if self._initializer_done:
        return
    status_path = self.session_path / f"{self._initializer_agent}_status.yaml"
    if not status_path.is_file():
        return
    try:
        data = read_yaml(str(status_path))
    except Exception:
        return
    status = (data or {}).get("status", "")
    if status == "Completed":
        self._initializer_done = True
        if self._initializer_timer is not None:
            self._initializer_timer.stop()
        try:
            from brainstorm.brainstorm_session import apply_initializer_output
            apply_initializer_output(self.task_num)
            self.notify("Initial proposal imported.")
        except Exception as e:
            self.notify(
                f"Failed to apply initializer output: {e}",
                severity="error",
            )
        self._load_existing_session()
    elif status in ("Error", "Aborted"):
        self._initializer_done = True
        if self._initializer_timer is not None:
            self._initializer_timer.stop()
        self.notify(
            f"Initializer agent {status.lower()}. "
            "Placeholder retained; retry via TUI.",
            severity="error",
        )
        self._load_existing_session()
```

### 7. Wire state attrs in `BrainstormApp.__init__`

In `brainstorm_app.py` near line 1252 (next to `self._status_refresh_timer = None`),
add the three initializer-tracking attrs:

```python
self._initializer_agent: str | None = None
self._initializer_done: bool = False
self._initializer_timer = None
```

### 8. Imports

At the top of `brainstorm_app.py`, add `DirectoryTree` to the
`from textual.widgets import (...)` block (existing block around lines 19-32).
No other top-level imports needed — `crew_worktree`, `load_session`, and
`read_yaml` are already imported (lines 51-69). `apply_initializer_output` is
imported lazily inside `_poll_initializer` to keep the module import graph
lightweight for the blank path.

## Verification

Per-task sanity (aggregate manual-verification is covered by sibling t573_5):

- `ait brainstorm <fresh_task>`:
  - Modal shows three buttons.
  - "Initialize Blank" → existing behaviour (DAG shows `n000_init` from the
    task file body) — regression check.
  - "Import Proposal…" → picker opens; non-`.md` / `.markdown` files hidden;
    Enter on a `.md` file closes the picker; TUI shows a waiting
    notification; the DAG pane shows the placeholder `n000_init`; after the
    initializer agent completes, the DAG is refreshed with the reformatted
    `n000_init` (dimensions populated).
  - "Cancel" on the main modal → TUI exits cleanly.
  - `escape` in the picker → returns to the main modal (does NOT exit the
    TUI).
- `md5sum` of the imported source file is identical before and after the
  flow (sanity — the CLI + initializer agent must not mutate it).
- Error path — truncate `initializer_bootstrap_output.md` mid-run (simulate
  malformed agent output). When the polling loop sees `Completed`, the
  `apply_initializer_output` call will raise `ValueError`; the TUI must
  notify severity=error and leave the placeholder n000_init in place
  without crashing.
- Runner-start-failure path — temporarily monkey-patch `start_runner` in
  `agentcrew_runner_control` to return False. Importing a proposal should
  surface the "runner failed to start" error and exit without starting the
  polling timer.
- No-tmux path — run the TUI with `TMUX=` unset; the initializer agent
  launches via the headless fallback (`is_tmux_available()`); polling still
  observes `Completed` and the flow completes identically.

## Notes for sibling tasks

- `Path(event.path).resolve()` yields an absolute path; the CLI in t573_2
  also realpaths, so double-resolution is harmless.
- `_MarkdownOnlyDirectoryTree` is intentionally local to the brainstorm TUI.
  If future brainstorm agents need a file picker, promote it to a shared
  helper alongside `ProjectFileTree`.
- The polling cadence is 2 seconds — matches the existing status refresh
  pattern (`_status_refresh_timer = self.set_interval(30, ...)` is 30s for
  status refresh; 2s is intentionally faster because the user is watching
  a synchronous init).
- `_initializer_timer.stop()` is null-safe (the attr is initialized to
  `None` in `__init__` and only set to a Timer after `set_interval`). The
  null-check in `_poll_initializer` covers the race where a stray tick
  fires before the timer is assigned.

## Step 9 (Post-Implementation)

Follow the shared workflow's Step 9 after user approval in Step 8:
`./.aitask-scripts/aitask_archive.sh 573_3`. The archived plan file will
land in `aiplans/archived/p573/` as the primary reference for t573_4
(docs + seed config) and t573_5 (manual verification sibling).

## Final Implementation Notes

- **Actual work done:** All eight planned items landed as designed in a
  single file, `.aitask-scripts/brainstorm/brainstorm_app.py`:
  1. `DirectoryTree` added to the `textual.widgets` import block.
  2. New `_MarkdownOnlyDirectoryTree(DirectoryTree)` subclass overriding
     `filter_paths` to admit only directories + `.md` / `.markdown`.
  3. New `ImportProposalFilePicker(ModalScreen)` inserted immediately
     before `InitSessionModal`.
  4. `InitSessionModal` rewritten with three buttons
     (`btn_init_blank`, `btn_init_import`, `btn_cancel`) and a
     `_on_picker_result` callback that stays in the modal on picker-cancel
     (so the user can still choose Blank or Cancel without re-entering
     the session modal).
  5. `_on_init_result` replaced with a three-way branch keyed on a string
     result (`None | "blank" | "import:<path>"`). Unknown results notify
     severity=error and exit.
  6. New `_run_init_with_proposal` — threaded shell-out to
     `ait brainstorm init <N> --proposal-file <path>`. Parses
     `INITIALIZER_AGENT:` from stdout and surfaces
     `RUNNER_START_FAILED:` from stderr (`cmd_init` may exit 0 even when
     the runner fails to auto-start).
  7. New `_start_initializer_wait` — main-thread setup that loads the
     placeholder session, shows the DAG, and schedules
     `_poll_initializer` on a 2-second `set_interval` timer.
  8. New `_poll_initializer` — reads `<session_path>/<agent>_status.yaml`;
     on `Completed` it calls `apply_initializer_output(self.task_num)` and
     refreshes the session; on `Error`/`Aborted` it notifies the user and
     leaves the placeholder `n000_init` in place for a retry.
  9. Three new state attrs wired in `BrainstormApp.__init__`:
     `_initializer_agent`, `_initializer_done`, `_initializer_timer`.

- **Deviations from plan:** None. The one robustness correction
  identified at verify time (RUNNER_START_FAILED stderr parsing) landed
  exactly as described in the Context section.

- **Issues encountered:** None. The file AST-parses cleanly, the module
  imports without error, and both the full brainstorm suite (108/108)
  and the sibling test (`test_apply_initializer_output.sh` — 8/8) pass.
  Note: several unrelated `tests/test_*.sh` files show uncommitted
  `cp lib/archive_utils.sh` additions in the working tree — these are
  user in-progress work addressing the follow-up flagged by sibling
  t573_2's Final Implementation Notes. Not touched by this commit.

- **Key decisions:**
  - **Lazy import of `apply_initializer_output`** inside
    `_poll_initializer` (not at module top-level). The blank-init path
    is the common case and doesn't need this symbol. This mirrors the
    lazy-import pattern sibling t573_2 established for `start_runner`
    inside `cmd_init`.
  - **Class ordering:** `_MarkdownOnlyDirectoryTree` and
    `ImportProposalFilePicker` are inserted **before** `InitSessionModal`
    so that the reader sees the picker first and then the modal that
    opens it — matches the flow of control.
  - **`_on_picker_result` stays in the modal on cancel** rather than
    dismissing it. The user may have opened the picker by mistake and
    still wants Blank. Matches the plan's "On None: stay in this modal"
    note.
  - **`_initializer_timer.stop()` is null-safe**: the attr is
    initialized to `None` in `__init__` and may be set to a `Timer`
    only after `set_interval`. The null-check in `_poll_initializer`
    also guards against a stray tick firing in a race.

- **Notes for sibling tasks (t573_4 / t573_5):**
  - **3-button modal is the new default** — any docs that still
    describe the 2-button init screen need to be updated by t573_4.
  - **Canonical stderr marker `RUNNER_START_FAILED:<crew>`** is now
    consumed by the TUI. If any future refactor of `cmd_init` changes
    this literal, the TUI error path breaks silently (runs the happy
    path, then polls forever). Keep the marker stable.
  - **Polling cadence is 2 seconds** — deliberately faster than the
    30s `_status_refresh_timer` because the user is waiting
    synchronously on first init. Adjust downward (not upward) if it
    proves noisy.
  - **Picker scope is `"."`** — `ait` always cds to the repo root
    before running, so the CWD is always the project root.
  - **Manual verification items for t573_5** should include: (a) picker
    hides `.py` / `.sh` / `.txt` files, (b) picker shows `.md` /
    `.markdown` (both cases), (c) escape-from-picker returns to the
    main modal (not a full exit), (d) runner-start-failure surfaces a
    user-visible error (not silent polling), (e) agent-error
    (`Error`/`Aborted` status) surfaces an error notification with the
    placeholder retained.

- **Verification results:**
  - `python3 -m unittest discover -s tests -p 'test_brainstorm*.py'`
    → 108/108 PASS.
  - `bash tests/test_apply_initializer_output.sh` → 8/8 PASS.
  - AST parse of `brainstorm_app.py` → OK.
  - `from brainstorm.brainstorm_app import BrainstormApp,
    _MarkdownOnlyDirectoryTree, ImportProposalFilePicker` → OK.
  - `_MarkdownOnlyDirectoryTree.filter_paths(None, fixtures)` admits
    `.md`, `.MARKDOWN` (case-insensitive), and directories; excludes
    `.py` and suffix-less files.
