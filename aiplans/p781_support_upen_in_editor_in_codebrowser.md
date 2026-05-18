---
Task: t781_support_upen_in_editor_in_codebrowser.md
Base branch: main
plan_verified: []
---

# Plan: Add "Open in editor" (E) to codebrowser TUI (t781)

## Context

The `ait codebrowser` TUI currently has no shortcut to open the currently-viewed file in the user's `$EDITOR`. The sibling `ait board` TUI already has this pattern (`run_editor` via `subprocess.call` after `self.suspend()`), and codebrowser users want parity: hit a key to pop into nano/vim/etc., edit the file, return to the browser with annotations refreshed.

The user explicitly requested:
1. Bind capital `E` to "Edit" (open current file in `$EDITOR`).
2. Place the `E` binding in the BINDINGS list **next to `e` (Explain)** so it shows next to Explain in the footer.
3. Move the `tab` ("Toggle Focus") binding to the **end** of the BINDINGS list so it shows at the tail of the footer.

## Files to modify

- `.aitask-scripts/codebrowser/codebrowser_app.py` — add binding + action.
- `website/content/docs/tuis/codebrowser/reference.md` — document `E`, re-order `Tab` to the end of the Application table.

## Implementation

### 1. `codebrowser_app.py` — BINDINGS reordering

Current (lines 370–388):

```python
BINDINGS = [
    *TuiSwitcherMixin.SWITCHER_BINDINGS,
    Binding("escape", "handle_escape_key", "Escape", show=False, priority=True),
    Binding("q", "quit", "Quit"),
    Binding("tab", "toggle_focus", "Toggle Focus", priority=True),   # <-- move to tail
    Binding("r", "refresh_explain", "Refresh annotations"),
    Binding("R", "reset_file_tree", "Reset file tree"),
    Binding("t", "toggle_annotations", "Toggle annotations"),
    Binding("g", "go_to_line", "Go to line"),
    Binding("e", "launch_agent", "Explain"),
    # <-- insert E here
    Binding("d", "toggle_detail", "Toggle detail"),
    Binding("D", "expand_detail", "Expand detail"),
    Binding("V", "view_plan", "Fullscreen plan"),
    Binding("h", "toggle_history", "History"),
    Binding("H", "history_for_task", "History for task"),
    Binding("n", "create_task", "New task"),
    Binding("w", "toggle_wrap_mode", "Wrap mode"),
    Binding("c", "copy_file_path", "Copy path"),
]
```

Target:

```python
BINDINGS = [
    *TuiSwitcherMixin.SWITCHER_BINDINGS,
    Binding("escape", "handle_escape_key", "Escape", show=False, priority=True),
    Binding("q", "quit", "Quit"),
    Binding("r", "refresh_explain", "Refresh annotations"),
    Binding("R", "reset_file_tree", "Reset file tree"),
    Binding("t", "toggle_annotations", "Toggle annotations"),
    Binding("g", "go_to_line", "Go to line"),
    Binding("e", "launch_agent", "Explain"),
    Binding("E", "open_in_editor", "Edit"),
    Binding("d", "toggle_detail", "Toggle detail"),
    Binding("D", "expand_detail", "Expand detail"),
    Binding("V", "view_plan", "Fullscreen plan"),
    Binding("h", "toggle_history", "History"),
    Binding("H", "history_for_task", "History for task"),
    Binding("n", "create_task", "New task"),
    Binding("w", "toggle_wrap_mode", "Wrap mode"),
    Binding("c", "copy_file_path", "Copy path"),
    Binding("tab", "toggle_focus", "Toggle Focus", priority=True),
]
```

### 2. `codebrowser_app.py` — `action_open_in_editor`

Add a new action method following the `aitask_board.py:4065-4077` pattern. Insert it near the other file-related actions (after `action_copy_file_path` at line 951 is a natural location).

```python
@work(exclusive=True)
async def action_open_in_editor(self) -> None:
    """Suspend app and open the current file in $EDITOR."""
    if not self._current_file_path:
        self.notify("No file selected", severity="warning")
        return
    editor = os.environ.get("EDITOR", "nano")
    if sys.platform == "win32":
        editor = os.environ.get("EDITOR", "notepad")
    filepath = self._current_file_path
    with self.suspend():
        subprocess.call([editor, str(filepath)])
    # Refresh explain annotations in case the file changed
    if self.explain_manager:
        self._refresh_explain_data(filepath)
```

Notes:
- `os`, `sys`, `subprocess` are already imported (lines 20, 23, 24).
- `@work` is already used elsewhere in the file (e.g., line 1390 `_run_agent_command`); the existing import covers it.
- Suspend/resume is the proven pattern — already used at line 1399 for `_run_agent_command` fallback.
- Refreshing explain after the edit mirrors the board's `manager.load_tasks() + refresh_board()` post-edit refresh and is cheap when no changes were made.

### 3. `website/content/docs/tuis/codebrowser/reference.md` — Application table

Current (lines 14–25):

```markdown
| Key | Action | Context |
|-----|--------|---------|
| `q` | Quit the application | Global |
| `Tab` | Cycle focus between file tree, code viewer, and detail pane | Global |
| `r` | Refresh explain annotations for current file's directory | Global |
| `t` | Toggle annotation gutter visibility | Global |
| `g` | Open go-to-line dialog | Global |
| `e` | Launch the configured code agent for explain on the current file | Global |
| `d` | Toggle detail pane visibility | Global |
| `D` | Toggle detail pane between default and expanded width | Global |
| `h` | Toggle completed tasks history view | Global |
| `H` | Open history screen navigated to the task at cursor | Global (requires annotated line) |
```

Target — insert `E` row immediately after `e`, and move `Tab` row to the end:

```markdown
| Key | Action | Context |
|-----|--------|---------|
| `q` | Quit the application | Global |
| `r` | Refresh explain annotations for current file's directory | Global |
| `t` | Toggle annotation gutter visibility | Global |
| `g` | Open go-to-line dialog | Global |
| `e` | Launch the configured code agent for explain on the current file | Global |
| `E` | Open the current file in `$EDITOR` (suspends the TUI; resumes on exit) | Global |
| `d` | Toggle detail pane visibility | Global |
| `D` | Toggle detail pane between default and expanded width | Global |
| `h` | Toggle completed tasks history view | Global |
| `H` | Open history screen navigated to the task at cursor | Global (requires annotated line) |
| `Tab` | Cycle focus between file tree, code viewer, and detail pane | Global |
```

(Other tables — History Screen, dialogs — are untouched; only the Application table changes.)

## Verification

1. `ait codebrowser` opens. Navigate to any file in the file tree.
2. Press `E` → terminal switches into `$EDITOR` (nano if unset) with the file open. Save & quit → returns to the codebrowser at the same file. Footer shows `E Edit` next to `e Explain` and `Tab Toggle Focus` at the end.
3. With no file selected (initial state), pressing `E` shows the "No file selected" toast.
4. After editing, explain annotations refresh automatically (visible if the file had prior annotations).
5. Sanity-grep the docs:
   ```bash
   grep -n '`E`\|`Tab`' website/content/docs/tuis/codebrowser/reference.md
   ```
   Confirms `E` is present and `Tab` is at the end of the Application table.

## Out of scope

- Changing the editor invocation mechanism (e.g., adding a non-suspending external-terminal launch path). Suspend+resume matches the board precedent and is what the user asked for.
- Adding `E` to any other screen (history, dialogs). Only the main app context gets the binding.

## Post-Review Changes

### Change Request 1 (2026-05-18 10:45)
- **Requested by user:** Footer showed `E Edit` after `R Reset file tree` instead of next to `e Explain`.
- **Root cause:** The codebrowser uses a custom `ContextualFooter` (`codebrowser_app.py:161`) that sorts visible bindings by `PRIMARY_ORDER = ["q", "h", "n", "e", "g"]` plus per-pane suffix lists. Bindings not in either list fall to the tail and appear in declaration order. The initial fix only changed `BINDINGS` declaration order, which has no effect on footer placement.
- **Changes made:** Added `"E"` to `ContextualFooter.PRIMARY_ORDER` between `"e"` and `"g"` so it renders adjacent to Explain in every pane. Aligns with the CLAUDE.md "uppercase sibling adjacent to its lowercase primary" rule.
- **Files affected:** `.aitask-scripts/codebrowser/codebrowser_app.py`

### Change Request 2 (2026-05-18 10:50)
- **Requested by user:** Move the `Tab Toggle Focus` entry so it appears AFTER `H History for task` in the footer, **without** changing where `H` is shown.
- **Changes made:** Appended `"tab"` to the `detail_pane` suffix (now `["d", "D", "c", "H", "tab"]`) so in the detail pane (the only pane that displays `H`) `tab` renders right after `H`. In other panes (file tree, code viewer, recent files, file search) `tab` continues to fall to the tail of the unsorted bindings — unchanged from prior behavior. PRIMARY_ORDER reverted to its original value.
- **Files affected:** `.aitask-scripts/codebrowser/codebrowser_app.py`

## Final Implementation Notes

- **Actual work done:** Added an `E` keybinding to `ait codebrowser` that suspends the TUI, runs `$EDITOR` on the currently-viewed file (nano fallback on Unix, notepad on Windows), then refreshes explain annotations on return. Inserted the new action method `action_open_in_editor` after `action_copy_file_path`. Reordered `BINDINGS` so `tab` is last and `E` is next to `e`. Added `"E"` to `ContextualFooter.PRIMARY_ORDER` so the footer actually renders it next to `e Explain` (the contextual footer is what determines visible order — `BINDINGS` declaration order only affects tail/unsorted entries). Updated the website reference table accordingly.
- **Deviations from plan:** Initial plan only modified `BINDINGS` declaration order, missing the `ContextualFooter.PRIMARY_ORDER` constant. Fixed during user review.
- **Issues encountered:** Footer mis-placement reported by user → traced to `ContextualFooter` (codebrowser-specific Footer subclass at `codebrowser_app.py:161`) and its `PRIMARY_ORDER` constant.
- **Key decisions:** Reused the `board`-side `run_editor` pattern (suspend/subprocess.call/refresh). Editor refresh after exit uses `_refresh_explain_data` since that's the codebrowser-equivalent of board's `manager.load_tasks() + refresh_board()`. Inserted `E` in `PRIMARY_ORDER` immediately after `e` so the uppercase sibling stays adjacent per the CLAUDE.md footer-ordering rule.
- **Upstream defects identified:** None

