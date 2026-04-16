---
Task: t570_copy_file_path_action_in_ait_codebrowser_for_currently_opene.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: Copy File Path Dialog in Codebrowser TUI (t570)

## Context

The codebrowser TUI currently has no way to copy the path of the currently opened file. Users need to manually select/copy paths from the title bar. The task requests a keybinding that opens a modal dialog with full (absolute) and relative (project-root-relative) paths, each with a copy button. The dialog should auto-close on copy and show a notification. The pattern follows the existing `AgentCommandScreen` copy-row UI in `.aitask-scripts/lib/agent_command_screen.py`.

## Implementation

### 1. Add `CopyFilePathScreen` modal class to `codebrowser_app.py`

Insert a new `CopyFilePathScreen(ModalScreen)` class after `GoToLineScreen` (after line ~100), following the same dialog pattern:

```python
class CopyFilePathScreen(ModalScreen):
    """Modal dialog to copy the current file path."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("a", "copy_absolute", "Copy absolute", show=False),
        Binding("r", "copy_relative", "Copy relative", show=False),
    ]

    def __init__(self, absolute_path: str, relative_path: str):
        super().__init__()
        self.absolute_path = absolute_path
        self.relative_path = relative_path

    def compose(self):
        with Container(id="copy_path_dialog"):
            yield Label("Copy file path:")
            with Horizontal(classes="copy-path-row"):
                yield Label(self.relative_path, id="copy_path_rel_label", classes="copy-path-value")
                yield Button("Copy (R)el", variant="primary", id="btn_copy_rel")
            with Horizontal(classes="copy-path-row"):
                yield Label(self.absolute_path, id="copy_path_abs_label", classes="copy-path-value")
                yield Button("Copy (A)bs", variant="primary", id="btn_copy_abs")
            with Horizontal(id="copy_path_buttons"):
                yield Button("Cancel", variant="default", id="btn_copy_cancel")

    @on(Button.Pressed, "#btn_copy_rel")
    def copy_relative(self) -> None:
        self.app.copy_to_clipboard(self.relative_path)
        self.app.notify(f"Copied: {self.relative_path}", timeout=2)
        self.dismiss(None)

    @on(Button.Pressed, "#btn_copy_abs")
    def copy_absolute(self) -> None:
        self.app.copy_to_clipboard(self.absolute_path)
        self.app.notify(f"Copied: {self.absolute_path}", timeout=2)
        self.dismiss(None)

    @on(Button.Pressed, "#btn_copy_cancel")
    def cancel(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_copy_absolute(self) -> None:
        self.copy_absolute()

    def action_copy_relative(self) -> None:
        self.copy_relative()
```

### 2. Add CSS for the dialog

Add to `CodeBrowserApp.CSS` (after the `GoToLineScreen` / `#goto_buttons` styles, around line 150):

```css
CopyFilePathScreen {
    align: center middle;
}
#copy_path_dialog {
    width: 80;
    height: auto;
    padding: 1 2;
    background: $surface;
    border: thick $primary;
}
.copy-path-row {
    height: 3;
    width: 100%;
    align: left middle;
}
.copy-path-value {
    width: 1fr;
    overflow: hidden;
}
.copy-path-row Button {
    width: auto;
    min-width: 14;
}
#copy_path_buttons {
    margin-top: 1;
    height: auto;
}
```

### 3. Add keybinding `c` to `CodeBrowserApp.BINDINGS`

Add after the `w` binding (line 169):
```python
Binding("c", "copy_file_path", "Copy path"),
```

### 4. Add `action_copy_file_path` method to `CodeBrowserApp`

Add after `action_toggle_wrap_mode` (around line 730):

```python
def action_copy_file_path(self) -> None:
    """Open copy-file-path modal for the currently opened file."""
    if not self._current_file_path:
        self.notify("No file selected", severity="warning")
        return
    abs_path = str(self._current_file_path)
    rel_path = str(self._current_file_path.relative_to(self._project_root))
    self.push_screen(CopyFilePathScreen(abs_path, rel_path))
```

## Files Modified

- `.aitask-scripts/codebrowser/codebrowser_app.py` — new `CopyFilePathScreen` class, CSS, binding, and action method

## Verification

1. Run `python .aitask-scripts/codebrowser/codebrowser_app.py` (or `ait codebrowser`)
2. Open a file in the tree
3. Press `c` — modal should appear with relative and absolute paths
4. Click "Copy (R)el" or press `r` — dialog closes, notification shown, relative path in clipboard
5. Reopen with `c`, click "Copy (A)bs" or press `a` — dialog closes, notification shown, absolute path in clipboard
6. Reopen with `c`, press Escape or click Cancel — dialog closes without copying
7. Press `c` with no file open — "No file selected" warning notification

## Post-Implementation

Step 9: archive task, commit, push per task-workflow SKILL.md.
