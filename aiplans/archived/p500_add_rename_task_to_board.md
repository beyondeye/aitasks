---
Task: t500_add_rename_task_to_board.md
Branch: main (no worktree)
---

# Plan: Add Rename Task Action to Board TUI

## Context

There is currently no way to rename an aitask from the board TUI. The task detail screen supports editing metadata (priority, effort, status, type) and content (via external editor), but not renaming the file itself. The rename must keep the `t<N>_` prefix, rename both task and plan files, commit, and sync.

## Approach

Add a rename action to `TaskDetailScreen` following existing patterns (lock/unlock/edit/delete). Create a `RenameTaskScreen` modal for input, handle the result in the main app's `check_edit` callback, and implement a threaded worker for the git operations.

## Files to Modify

- `.aitask-scripts/board/aitask_board.py` — All changes in this single file

## Implementation Steps

### 1. Add `RenameTaskScreen` modal class (~line 2108, before `CommitMessageScreen`)

Following the `CommitMessageScreen` pattern:

```python
class RenameTaskScreen(ModalScreen):
    """Modal dialog to rename a task (change the description part of the filename)."""
    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, task_filename: str):
        super().__init__()
        self.task_filename = task_filename
        self.task_num, self.current_name = TaskCard._parse_filename(task_filename)

    def compose(self):
        with Container(id="rename_dialog"):
            yield Label(f"Rename Task {self.task_num}", id="rename_title")
            yield Label(f"Prefix: [b]{self.task_num}_[/b] (fixed)")
            yield Input(value=self.current_name.replace(" ", "_"), id="rename_input",
                        placeholder="new_task_name")
            with Horizontal(id="detail_buttons"):
                yield Button("Rename", variant="success", id="btn_do_rename")
                yield Button("Cancel", variant="default", id="btn_rename_cancel")

    @on(Button.Pressed, "#btn_do_rename")
    def do_rename(self):
        new_name = self.query_one("#rename_input", Input).value.strip()
        if not new_name:
            return
        self.dismiss(("rename", new_name))

    def on_input_submitted(self, event):
        self.do_rename()

    @on(Button.Pressed, "#btn_rename_cancel")
    def cancel(self):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)
```

### 2. Add `_sanitize_name()` helper function (module-level, near `_task_git_cmd`)

Python equivalent of the shell `sanitize_name()`:

```python
def _sanitize_name(name: str) -> str:
    """Sanitize task name: lowercase, underscores, alphanumeric only, max 60 chars."""
    name = name.lower().replace(" ", "_")
    name = re.sub(r'[^a-z0-9_]', '', name)
    name = re.sub(r'_+', '_', name)
    name = name.strip("_")
    return name[:60]
```

### 3. Add rename button and binding to `TaskDetailScreen`

- Add bindings for `n`/`N` key (R is taken by Revert) → `action_rename`
- Add `(N)ame` button in `detail_buttons_file` row (between Edit and Delete/Archive)
- Disable when `is_done_or_ro` (same as Edit)
- Button handler: `self.dismiss("rename")`

### 4. Handle `"rename"` result in `action_view_details` → `check_edit` callback

In the `check_edit` callback (line ~3222), add a new branch:

```python
elif result == "rename":
    def on_rename_result(rename_result):
        if rename_result and rename_result[0] == "rename":
            new_name = rename_result[1]
            self._rename_task(focused.task_data, new_name)
    self.push_screen(RenameTaskScreen(focused.task_data.filename), on_rename_result)
    return
```

### 5. Add `_rename_task()` and `_do_rename_task()` worker methods to `KanbanApp`

`_rename_task()` — prepares the rename and shows loading overlay:
- Sanitize the new name
- Validate (non-empty after sanitization, different from current)
- Compute new task filepath and new plan filepath (if plan exists)
- Push `LoadingOverlay("Renaming...")`
- Call `_do_rename_task()` worker

`_do_rename_task()` — `@work(thread=True)`:
- Rename task file: `Path.rename()` 
- Rename plan file if it exists: `Path.rename()`
- Git add old + new paths for both task and plan: `subprocess.run([*_task_git_cmd(), "add", ...])`
- Git commit: `"ait: Rename t<N>: <new_humanized_name>"`
- Run sync: `self._run_sync(show_notification=True)`
- Pop loading overlay
- Reload tasks and refresh board with `refocus_filename=new_filename`

**Path computation logic:**
- Parent task: `aitasks/t<N>_<old>.md` → `aitasks/t<N>_<new>.md`
- Child task: `aitasks/t<P>/t<P>_<C>_<old>.md` → `aitasks/t<P>/t<P>_<C>_<new>.md`
- Parent plan: `aiplans/p<N>_<old>.md` → `aiplans/p<N>_<new>.md`
- Child plan: `aiplans/p<P>/p<P>_<C>_<old>.md` → `aiplans/p<P>/p<P>_<C>_<new>.md`

## Key Design Decisions

- **Key binding `n`/`N`**: `r` is taken by Revert, `n` for "Name" is intuitive and available
- **Python-native rename** instead of calling `aitask_update.sh --batch --name`: The shell script doesn't rename plan files and has a child-task directory bug. Doing it in Python is simpler and correct.
- **Sync after commit**: Task description says to run sync so everyone gets the updated name
- **Disabled for Done/Folded/ReadOnly tasks**: Same guard as Edit button — don't rename archived/completed tasks

## Verification

1. Open `ait board`, select a task, press Enter for detail view
2. Press `N` or click "(N)ame" button
3. Enter a new name in the modal → verify task file is renamed correctly
4. Verify plan file is also renamed if one exists
5. Check git log for the rename commit
6. Verify sync runs after commit
7. Test with a child task to ensure directory structure is preserved
8. Test that the button is disabled for Done/Folded tasks
9. Refer to Step 9 (Post-Implementation) for cleanup/archival

## Post-Review Changes

### Change Request 1 (2026-04-09 08:50)
- **Requested by user:** Arrow keys not working in rename input, and text selected by default causing it to be cleared on typing
- **Changes made:**
  1. Added `select_on_focus=False` to the Input widget in RenameTaskScreen to prevent auto-selection
  2. Added Input widget check to `check_action()` in KanbanApp to suppress priority nav bindings (left/right/up/down) when an Input widget is focused — the app's `priority=True` left/right bindings were intercepting arrow keys before the Input could handle them
- **Files affected:** `.aitask-scripts/board/aitask_board.py`

## Final Implementation Notes
- **Actual work done:** Added rename task action to board TUI as planned — RenameTaskScreen modal, _sanitize_name helper, bindings (N key), button in detail screen, _rename_task/_do_rename_task threaded workers for rename + commit + sync. Also fixed arrow key handling for all Input widgets in modal screens by adding Input check to check_action().
- **Deviations from plan:** Added Input focus fix to check_action() (not in original plan) — KanbanApp's priority=True left/right bindings were intercepting arrow keys in Input widgets. Also set select_on_focus=False.
- **Issues encountered:** Arrow keys didn't work in rename input due to KanbanApp's priority nav bindings. Text was auto-selected on focus causing UX issue. Both fixed in post-review.
- **Key decisions:** Used Python-native file rename instead of shell script (aitask_update.sh has a child task rename bug — tracked as t502). Used _task_git_cmd() for git operations to support both branch-mode and legacy-mode.
- **Known minor issue:** Tab focus cycling to the Rename button doesn't work (Textual focus limitation in the Container layout). Enter key submission via on_input_submitted should work. Mouse click on button works.
