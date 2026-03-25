---
Task: t463_focus_bug_fixes_to_history_screen.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: Fix focus bugs in history screen (t463)

## Context

Two focus/keyboard navigation bugs in the codebrowser history screen:

1. **Back button focus loss**: After pressing Enter on `_BackButton` to navigate back, `go_back()` calls `_render_task()` which removes all children (including the focused `_BackButton`) and mounts new widgets — but never sets focus on any new widget. Up/down arrows then just scroll the container instead of navigating fields. Only works after pressing left+right because `action_focus_right()` explicitly focuses the first focusable child.

2. **Sibling picker missing keyboard navigation**: `SiblingPickerModal` has no `on_key()` method to bridge down-arrow from the search input to the first `_SiblingItem`. The `LabelFilterModal` (from t458) already implements this pattern correctly and should be replicated.

## File to modify

`.aitask-scripts/codebrowser/history_detail.py`

## Changes

### Bug 1: Focus first field after `go_back()`

**In `HistoryDetailPane.go_back()` (line 584):**

Add a helper method `_focus_first_field()` and call it after `_render_task()` returns:

```python
def go_back(self) -> None:
    """Pop navigation stack, show previous task (no browse event)."""
    if len(self._nav_stack) > 1:
        self._nav_stack.pop()
        prev = self._nav_stack[-1]
        self._showing_plan = False
        self._render_task(prev)
        self._focus_first_field()

def _focus_first_field(self) -> None:
    """Focus the first focusable field in this pane."""
    for child in self.children:
        if child.can_focus and child.display and child.styles.display != "none":
            child.focus()
            child.scroll_visible()
            return
```

This matches the exact pattern used by `action_focus_right()` in `history_screen.py:254-266`.

### Bug 2: Add keyboard navigation to `SiblingPickerModal`

**2a. Add `on_key()` to `SiblingPickerModal` (after line 501):**

Bridge down-arrow from search input to first sibling item (same pattern as `LabelFilterModal.on_key()` at `history_label_filter.py:245-256`):

```python
def on_key(self, event) -> None:
    """Handle Down arrow from Input to move focus to first sibling item."""
    if event.key == "down":
        focused = self.focused
        if isinstance(focused, Input) and focused.id == "sibling_search":
            container = self.query_one("#sibling_list", VerticalScroll)
            items = list(container.query(_SiblingItem))
            if items:
                items[0].focus()
                items[0].scroll_visible()
                event.prevent_default()
                event.stop()
```

**2b. Update `_SiblingItem.on_key()` up-arrow handling (line 457):**

When the first item receives up-arrow, move focus back to search input (same pattern as `LabelFilterItem.on_key()` at `history_label_filter.py:120-142`):

```python
elif event.key == "up":
    parent = self.parent
    if parent is not None:
        focusable = [
            w for w in parent.children
            if w.can_focus and w.display and w.styles.display != "none"
        ]
        try:
            idx = focusable.index(self)
        except ValueError:
            idx = 1
        if idx == 0:
            modal = self.screen
            if isinstance(modal, SiblingPickerModal):
                modal.query_one("#sibling_search", Input).focus()
            event.prevent_default()
            event.stop()
            return
    _focus_neighbor(self, -1)
    event.prevent_default()
    event.stop()
```

**2c. Add keybind help text to `SiblingPickerModal.compose()` (line 494):**

Add a help line between search input and sibling list:

```python
def compose(self):
    with Container(id="sibling_picker_dialog"):
        yield Input(placeholder="Search siblings...", id="sibling_search")
        yield Static(
            "[dim]\\[Up/Down] navigate  \\[Enter] select  \\[Esc] cancel[/]",
            id="sibling_keybind_help",
        )
        yield VerticalScroll(id="sibling_list")
```

**2d. Add CSS for the help text:**

Add to `SiblingPickerModal.DEFAULT_CSS`:
```css
#sibling_keybind_help {
    height: 1;
    padding: 0 1;
    color: $text-muted;
    margin-bottom: 1;
}
```

## Verification

1. Open the codebrowser: `python .aitask-scripts/codebrowser/codebrowser.py` (or `ait browse`)
2. Press `h` to open history screen
3. **Bug 1 test**: Navigate to a child task (click to open), then press Enter on the back button. Verify up/down arrows immediately work to navigate fields without needing left+right first.
4. **Bug 2 test**: Open a child task detail, focus the "Siblings" field, press Enter or 's' to open sibling picker. Verify: down-arrow from search moves to first sibling, up-arrow from first sibling returns to search, up/down navigates between siblings, Enter selects a sibling.

## Post-Review Changes

### Change Request 1 (2026-03-25)
- **Requested by user:** Focus is also lost when selecting a sibling task from the sibling picker dialog (same issue as back button)
- **Changes made:** Added `focus_after_render` parameter to `show_task()` → `_load_and_render()` → `_render_task()` chain. Set `focus_after_render=True` in `ChildTaskField.on_key()` and `SiblingCountField._on_pick()` callback (navigations from within the detail pane). Left it `False` for clicks from the left list (which should keep focus on the list).
- **Files affected:** `.aitask-scripts/codebrowser/history_detail.py`

## Final Implementation Notes
- **Actual work done:** Fixed three focus-loss bugs in history screen: (1) after go_back(), (2) after sibling selection, (3) after child task navigation. Also added full keyboard navigation to SiblingPickerModal matching LabelFilterModal pattern.
- **Deviations from plan:** Added `focus_after_render` parameter propagation through `show_task()` → `_load_and_render()` → `_render_task()` chain (not in original plan). This was discovered during user testing.
- **Issues encountered:** Focus loss after sibling/child navigation was caused by async render path (`@work(thread=True)`) where widgets are rebuilt on the main thread via `call_from_thread()` — the previously focused widget is removed during rebuild.
- **Key decisions:** Only callers within the detail pane set `focus_after_render=True`. Clicks from the left pane list keep the default `False` to avoid stealing focus.

## Step 9: Post-Implementation

Archive task and push changes.
