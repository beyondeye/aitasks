---
Task: t573_3_tui_init_modal_file_picker.md
Parent Task: aitasks/t573_import_initial_proposal_in_brainstrom.md
Sibling Tasks: aitasks/t573/t573_1_*.md, aitasks/t573/t573_2_*.md, aitasks/t573/t573_4_*.md
Archived Sibling Plans: aiplans/archived/p573/p573_*_*.md
Worktree: (none — default profile works on current branch)
Branch: main
Base branch: main
---

# t573_3 — TUI init modal: three-button `InitSessionModal` + file picker + poll-and-apply

## Context

Third child, depends on t573_1 (`apply_initializer_output`) and t573_2
(CLI flag that the TUI shells to). Surfaces the feature in the
`ait brainstorm <N>` TUI.

## Implementation steps

### 1. `InitSessionModal` — three buttons

Edit `brainstorm_app.py:171-199`:

```python
class InitSessionModal(ModalScreen):
    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, task_num: str):
        super().__init__()
        self.task_num = task_num

    def compose(self) -> ComposeResult:
        with Container(id="init_dialog"):
            yield Label(f"No brainstorm session for t{self.task_num}", id="init_title")
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
        # On None: stay in this modal — the user can still pick Blank or Cancel.

    @on(Button.Pressed, "#btn_cancel")
    def cancel(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
```

### 2. `ImportProposalFilePicker(ModalScreen)` — new class

Add after `InitSessionModal`:

```python
class ImportProposalFilePicker(ModalScreen):
    """Directory-tree modal restricted to markdown files."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def compose(self) -> ComposeResult:
        from textual.widgets import DirectoryTree
        with Container(id="import_picker_dialog"):
            yield Label("Select a markdown file for the initial proposal",
                        id="import_picker_title")
            tree = DirectoryTree(".", id="import_picker_tree")
            tree.filter_paths = self._filter_paths  # type: ignore[assignment]
            yield tree
            yield Label("↵ select  esc cancel", id="import_picker_footer")

    @staticmethod
    def _filter_paths(paths):
        return [
            p for p in paths
            if p.is_dir() or p.suffix.lower() in (".md", ".markdown")
        ]

    def on_directory_tree_file_selected(self, event) -> None:
        self.dismiss(str(Path(event.path).resolve()))

    def action_cancel(self) -> None:
        self.dismiss(None)
```

If Textual's `DirectoryTree` doesn't expose `filter_paths` as a
settable attr, override it by subclassing — see
`.aitask-scripts/codebrowser/file_tree.py:67` for the subclass idiom.
Read that file before writing this modal.

### 3. `_on_init_result` — three-way branch

Replace the current boolean-based handler at `brainstorm_app.py:3043-3048`:

```python
def _on_init_result(self, result: str | None) -> None:
    if result is None:
        self.exit()
    elif result == "blank":
        self._run_init()  # existing method, unchanged
    elif isinstance(result, str) and result.startswith("import:"):
        path = result[len("import:"):]
        self._run_init_with_proposal(path)
    else:
        self.notify(f"Unknown init result: {result!r}", severity="error")
        self.exit()
```

### 4. `_run_init_with_proposal(path)` — threaded shell-out

Add next to `_run_init`:

```python
@work(thread=True)
def _run_init_with_proposal(self, path: str) -> None:
    result = subprocess.run(
        [AIT_PATH, "brainstorm", "init", self.task_num,
         "--proposal-file", path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        self.call_from_thread(
            self.notify,
            f"Init failed: {result.stderr.strip() or result.stdout.strip()}",
            severity="error",
        )
        self.call_from_thread(self.exit)
        return

    # Parse INITIALIZER_AGENT line
    agent_name = "initializer_bootstrap"
    for line in result.stdout.splitlines():
        if line.startswith("INITIALIZER_AGENT:"):
            agent_name = line.split(":", 1)[1].strip()
            break

    self.call_from_thread(self._start_initializer_wait, agent_name)
```

### 5. `_start_initializer_wait(agent_name)` — main-thread setup

```python
def _start_initializer_wait(self, agent_name: str) -> None:
    self._initializer_agent = agent_name
    self._initializer_done = False
    self.session_data = load_session(self.task_num)  # placeholder n000_init already exists
    self._update_title_from_task()
    self._load_existing_session()  # show placeholder DAG
    self.notify(f"Waiting for {agent_name} to complete…")
    self._initializer_timer = self.set_interval(2, self._poll_initializer)
```

### 6. `_poll_initializer`

```python
def _poll_initializer(self) -> None:
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
        self._initializer_timer.stop()
        try:
            from brainstorm.brainstorm_session import apply_initializer_output
            apply_initializer_output(self.task_num)
            self.notify("Initial proposal imported.")
        except Exception as e:
            self.notify(f"Failed to apply initializer output: {e}",
                        severity="error")
        self._load_existing_session()
    elif status in ("Error", "Aborted"):
        self._initializer_done = True
        self._initializer_timer.stop()
        self.notify(
            f"Initializer agent {status.lower()}. Placeholder retained; retry via TUI.",
            severity="error",
        )
        self._load_existing_session()
```

### 7. Wire state attrs in `__init__`

Ensure `self._initializer_agent`, `self._initializer_done`,
`self._initializer_timer` are initialized to `None`/`False` in
`BrainstormApp.__init__` (find where other private attrs are set —
the class is at roughly `brainstorm_app.py:1400+`).

## Verification

Manual verification in the TUI — covered by the aggregate
`manual_verification` sibling (to be added by the parent planner).
Per-task sanity:

- `ait brainstorm <fresh_task>`:
  - Modal shows three buttons.
  - "Initialize Blank" → existing behaviour (DAG shows `n000_init` =
    task file).
  - "Import Proposal…" → picker opens; non-`.md` files hidden;
    Enter on a `.md` file closes picker; TUI shows waiting
    notification; after agent completion the DAG is repopulated.
  - "Cancel" or `escape` on main modal → TUI exits cleanly.
  - `escape` in picker → returns to main modal (not a full exit).
- `md5sum` of the imported file before and after is identical.
- Simulate agent failure (e.g. truncate the `_output.md` by hand mid-
  run): TUI notifies error severity and the placeholder n000_init
  remains — no crash.
- Run the TUI outside tmux (`unset TMUX`): polling still observes
  `Completed` via the headless fallback.

## Notes for sibling tasks

- `Path(event.path)` / `resolve()` is used to hand the picker result
  back as an absolute path. The CLI also realpaths, so double-
  resolution is harmless.
- The picker stays on the same `BINDINGS` style as `InitSessionModal`
  — `escape` → cancel — to avoid user confusion.
- If any future brainstorm agent needs a modal file picker, promote
  `ImportProposalFilePicker` to a shared helper. Today, keep it local
  to the brainstorm TUI.
