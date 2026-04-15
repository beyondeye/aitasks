---
Task: t540_5_board_file_references_field.md
Parent Task: aitasks/t540_task_creation_from_codebrowser.md
Parent Plan: aiplans/p540_task_creation_from_codebrowser.md
Sibling Tasks: aitasks/t540/t540_7_*.md, aitasks/t540/t540_8_*.md
Archived Sibling Plans: aiplans/archived/p540/p540_1_foundation_file_references_field.md, aiplans/archived/p540/p540_2_codebrowser_focus_mechanism.md, aiplans/archived/p540/p540_3_auto_merge_on_file_ref.md, aiplans/archived/p540/p540_4_codebrowser_create_from_selection.md, aiplans/archived/p540/p540_6_use_labels_from_previous_task.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_6 @ 2026-04-15 11:49
---

# Plan — t540_5: board `FileReferencesField` widget (verified)

## Context

t540_1 added the `file_references` frontmatter field and CLI flags on
`aitask_update.sh`. t540_2 added
`launch_or_focus_codebrowser(session, focus_value)` in
`lib/agent_launch_utils.py`. Without this task, the `ait board` detail
modal silently ignores the new field: the whitelist-free YAML parser
reads it, but it is never rendered, so users cannot see entries or jump
to codebrowser from the board. t540_5 adds a read-only focusable widget
that renders the entries and uses `enter` to open the referenced file +
range in codebrowser.

**Scope (per user):** read-only. Navigation only. No add/remove keybindings
inside the board. Users already have `./.aitask-scripts/aitask_update.sh
--file-ref ... --remove-file-ref ...` and the codebrowser create-task
flow (t540_4) for populating/editing `file_references`.

## Verification result

The existing plan at `aiplans/p540/p540_5_*.md` was sound; corrections
from reading current code:

- **`DependsField`** at `aitask_board.py:918` (plan said 915-976).
- **`ChildrenField`** at `aitask_board.py:998` (plan said 995-1034).
- **`FoldedTasksField`** at `aitask_board.py:1046-1095` — good anchor
  for placing the new widget class.
- **`DependencyPickerScreen`** at `aitask_board.py:1496`, uses
  `Container id="dep_picker_dialog"` + per-entry `DepPickerItem`. CSS id
  reusable.
- **`TaskDetailScreen`** at `aitask_board.py:1768`; `compose()` body
  L1825-1976. The correct wiring point is right after the "Folded into"
  block at L1911-1917 (keeps the field at the bottom of the metadata
  section, adjacent to the lock status).
- **`launch_or_focus_codebrowser`** at `lib/agent_launch_utils.py:300`,
  signature `(session, focus_value, window_name="codebrowser") ->
  tuple[bool, str | None]`. Existing import in the board is on
  `aitask_board.py:16` — extend to add the new symbol.
- **`task_yaml.py`** parser is whitelist-free (L81 `yaml.load`) and
  `_normalize_task_ids` only touches `depends`, `children_to_implement`,
  `folded_tasks`; `file_references` round-trips as raw strings. No
  parser change.

## Design decisions (locked)

- **Read-only.** The only key binding consumed by the widget is `enter`.
  No `a` / `x` / `d` handlers. Any other key falls through to the
  `TaskDetailScreen` modal bindings (pick, close, save, etc.), matching
  `DependsField.on_key` behavior at L933-937.
- **Navigate semantics:**
  - 0 entries → no-op (the widget still renders, so it's focusable for
    tab-cycle consistency, but `enter` does nothing).
  - 1 entry → call `launch_or_focus_codebrowser(session, entry)`.
  - ≥2 entries → push `FileReferencePickerScreen`, on selection call the
    launcher.
- **Rendering:** `"  [b]File Refs:[/b] <entries joined with ', '>"`. If
  empty, `"  [b]File Refs:[/b] [dim](none)[/dim]"`. All entries are
  displayed verbatim — no compact collapse for same-path entries.
  Multi-range entries like `foo.py:10-20^30-40` are shown as-is and
  pass through to codebrowser which collapses to the outer span per
  t540_2's parser.
- **Always rendered** (even when `file_references` is empty or absent).
  This keeps the focus cycle stable regardless of task content and makes
  the field discoverable as a labeled row. No branching between a
  placeholder and the "real" widget.
- **Tmux session discovery:** inline helper `_current_tmux_session()`
  next to the field class, calling `tmux display-message -p '#S'` with
  a 2-second timeout. Same pattern used in
  `codebrowser_app.py:207`, `monitor_app.py:1569`,
  `minimonitor_app.py:582`. If the subprocess fails or returns empty,
  notify "Codebrowser focus requires tmux" and return — navigation is a
  no-op. Cold-launch outside tmux is out of scope.
- **No CSS additions:** reuse `classes="meta-ro"` on the widget +
  `ro-focused` on focus (mirror of `DependsField.on_focus` / `on_blur`
  at L975-979). Picker reuses `id="dep_picker_dialog"` and
  `id="dep_picker_title"` so existing board CSS applies unchanged.

## Key files to modify

### 1. `.aitask-scripts/board/aitask_board.py`

**Extend the import** at L16:

```python
from agent_launch_utils import find_terminal, find_window_by_name, resolve_dry_run_command, resolve_agent_string, TmuxLaunchConfig, launch_in_tmux, launch_or_focus_codebrowser, maybe_spawn_minimonitor
```

**Add session helper + widget class** after `FoldedTasksField` (currently
ends at `aitask_board.py:1095`):

```python
def _current_tmux_session() -> str | None:
    """Return the current tmux session name, or None if not in tmux."""
    try:
        result = subprocess.run(
            ["tmux", "display-message", "-p", "#S"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0:
            name = result.stdout.strip()
            return name or None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


class FileReferencesField(Static):
    """Focusable, read-only file_references field.

    Enter navigates to the entry in codebrowser (picker if multi).
    No add/remove keybindings — use `aitask_update.sh --file-ref` /
    `--remove-file-ref` or the codebrowser create-task flow instead.
    """

    can_focus = True

    def __init__(self, file_refs: list, manager: "TaskManager",
                 owner_task: "Task", **kwargs):
        super().__init__(**kwargs)
        self.file_refs = list(file_refs or [])
        self.manager = manager
        self.owner_task = owner_task

    def render(self) -> str:
        if not self.file_refs:
            return "  [b]File Refs:[/b] [dim](none)[/dim]"
        return f"  [b]File Refs:[/b] {', '.join(self.file_refs)}"

    def on_key(self, event):
        if event.key == "enter":
            self._navigate()
            event.prevent_default()
            event.stop()

    def _navigate(self):
        if not self.file_refs:
            return
        if len(self.file_refs) == 1:
            self._launch_codebrowser(self.file_refs[0])
        else:
            def on_picked(entry):
                if entry:
                    self._launch_codebrowser(entry)
            self.app.push_screen(
                FileReferencePickerScreen(self.file_refs),
                on_picked,
            )

    def _launch_codebrowser(self, entry: str):
        session = _current_tmux_session()
        if not session:
            self.app.notify(
                "Codebrowser focus requires tmux", severity="warning")
            return
        ok, err = launch_or_focus_codebrowser(session, entry)
        if not ok:
            self.app.notify(
                f"Codebrowser launch failed: {err}", severity="error")

    def on_focus(self):
        self.add_class("ro-focused")

    def on_blur(self):
        self.remove_class("ro-focused")
```

**Add the picker modal** after the `FoldedTaskPickerScreen` block (ends
around `aitask_board.py:~1640`). Mirror `DependencyPickerScreen`
(L1496-1521):

```python
class FileReferenceItem(Static):
    """A selectable file-reference entry in the picker."""

    can_focus = True

    def __init__(self, entry: str, **kwargs):
        super().__init__(**kwargs)
        self.entry = entry

    def render(self) -> str:
        return f"  {self.entry}"

    def on_key(self, event):
        if event.key == "enter":
            self.screen.dismiss(self.entry)
            event.prevent_default()
            event.stop()

    def on_focus(self):
        self.add_class("dep-item-focused")

    def on_blur(self):
        self.remove_class("dep-item-focused")


class FileReferencePickerScreen(ModalScreen):
    """Popup to select which file_references entry to open."""

    BINDINGS = [
        Binding("escape", "close_picker", "Close", show=False),
    ]

    def __init__(self, entries: list):
        super().__init__()
        self.entries = list(entries)

    def compose(self):
        with Container(id="dep_picker_dialog"):
            yield Label(
                "Select file reference to open:", id="dep_picker_title")
            for entry in self.entries:
                yield FileReferenceItem(entry)
            yield Button("Cancel", variant="default", id="btn_dep_cancel")

    @on(Button.Pressed, "#btn_dep_cancel")
    def cancel(self):
        self.dismiss(None)

    def action_close_picker(self):
        self.dismiss(None)
```

Note: the existing `#btn_dep_cancel` Button id is already used by
`DependencyPickerScreen`, `ChildPickerScreen`, and `FoldedTaskPickerScreen`
— scoped per-screen so there's no collision (each modal has its own
DOM subtree).

**Wire into `TaskDetailScreen.compose()`** right after the "Folded into"
block at `aitask_board.py:1911-1917`, before the "Lock status" section
at L1919:

```python
            # File references field (read-only, navigate via enter)
            if self.manager:
                file_refs = meta.get("file_references") or []
                yield FileReferencesField(
                    file_refs, self.manager, self.task_data,
                    classes="meta-ro")
```

The `if self.manager` guard matches the pattern used by `DependsField`,
`ChildrenField`, `FoldedTasksField`, `FoldedIntoField`. The field is
always yielded even when `file_refs` is empty so the row is discoverable
and the focus cycle is stable.

### 2. `.aitask-scripts/board/task_yaml.py`

**No change.** Parser is dynamic; `file_references` round-trips as a
list of raw strings.

### 3. No changes to other files

- `aitask_update.sh` — not touched (no add/remove from the board).
- `agent_launch_utils.py` — already has `launch_or_focus_codebrowser`;
  session discovery is done inline in the board.

## Implementation sequence

1. Extend the `agent_launch_utils` import at `aitask_board.py:16` to
   include `launch_or_focus_codebrowser`.
2. Add `_current_tmux_session()` helper above the new class.
3. Add `FileReferencesField` class after `FoldedTasksField` (before the
   next class definition at L1097+).
4. Add `FileReferenceItem` + `FileReferencePickerScreen` after the
   `FoldedTaskPickerScreen` block (same locality as the other pickers).
5. Wire the `FileReferencesField` yield into `TaskDetailScreen.compose()`
   right after the Folded-into block at L1911-1917.
6. Syntax check:
   `python -c "import ast; ast.parse(open('.aitask-scripts/board/aitask_board.py').read())"`.
7. Manual verification (see below).

## Verification

**Prep:** seed a scratch Ready task with entries, e.g.
```bash
./.aitask-scripts/aitask_update.sh --batch <id> \
  --file-ref .aitask-scripts/board/aitask_board.py:918-979 \
  --file-ref .aitask-scripts/lib/agent_launch_utils.py:300-357 \
  --silent
```

- **Render (multi):** open `./ait board`, focus the scratch task, press
  enter to open the detail modal. The `File Refs:` row shows both
  entries joined by `", "`. Tab-cycle reaches the field (focus
  highlight via `ro-focused` class).
- **Render (empty):** open a task without `file_references` — row shows
  `(none)`. The field is still focusable.
- **Navigate (single):** update the scratch task to have only one ref,
  focus the field, press `enter` — an existing codebrowser window
  focuses and lands on the file+range, OR a new codebrowser window
  cold-launches via `./ait codebrowser --focus <entry>`. Requires tmux.
- **Navigate (multi):** focus the field on the seeded task with two
  refs, press `enter` — `FileReferencePickerScreen` opens, tab/arrow to
  an entry, press `enter` → codebrowser focuses that entry. Escape
  cancels.
- **Navigate (compact multi-range):** add
  `foo.py:10-20^30-40` via `aitask_update.sh --file-ref` (not via the
  board), then press `enter` on it — codebrowser lands on the outer
  span 10-40.
- **Navigate (outside tmux):** run `./ait board` in a plain terminal
  (no tmux), press `enter` on a ref — notify warning "Codebrowser focus
  requires tmux", no crash.
- **Navigate (zero):** open a task that has no refs, focus the field,
  press `enter` — no-op, no crash, modal stays.
- **Modal binding sanity:** with the field focused, press `p`, `c`, `s`,
  `e`, `d` — the modal actions still fire (pick / close / save / edit /
  delete) because the widget only consumes `enter`.
- **Focus cycle:** tab from Depends → Children → Folded → FileRefs →
  wraps back. Escape still closes the modal from any focus.
- **Syntax check:** the ast.parse command above exits 0.

## Out of scope

- Add/remove from the board (user preference — navigation only).
- Codebrowser-side handoff (t540_2, done).
- Fold-time union of `file_references` (t540_7).
- Auto-merge-on-file-ref creation flow (t540_3, done).
- Display collapse of multiple same-path entries — all entries rendered
  verbatim.

## Post-implementation

Standard archival via `./.aitask-scripts/aitask_archive.sh 540_5`
(task-workflow Step 9). Final Implementation Notes must capture any
surprises in Textual key propagation, picker focus behavior, or tmux
session discovery edge cases, so t540_7 and t540_8 pick up the context
cleanly.
