---
Task: t466_brainstorm_keyboard_nav_improvements.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

Task t466 improves keyboard navigation in the brainstorm TUI (`brainstorm_app.py`). Two issues:

1. **Up/Down arrows don't work without focus**: All up/down handling in `on_key()` checks `isinstance(self.focused, SomeRowType)`. If no row is focused (e.g., tab just activated, or focus is on a non-row widget), arrows do nothing. User must click first.

2. **Up arrow should reach the tab bar**: When the topmost focusable row is focused and user presses up, nothing happens (the handler stops at index 0). The desired behavior: focus moves to the `Tabs` widget inside `TabbedContent`, allowing left/right to switch tabs.

## File to Modify

`/home/ddt/Work/aitasks/.aitask-scripts/brainstorm/brainstorm_app.py`

## Implementation Plan

### Step 1: Add `Tabs` import

Add `Tabs` to the import from `textual.widgets`:
```python
from textual.widgets import (
    ...
    Tabs,
    ...
)
```

### Step 2: Add a unified navigation helper method

Add a method `_navigate_rows()` to `BrainstormApp` that handles up/down for any tab's focusable rows:

```python
def _navigate_rows(self, direction: int, container_id: str, row_types: tuple) -> bool:
    """Navigate up/down among focusable rows in a container.

    Returns True if the event was handled.
    direction: -1 for up, +1 for down.
    """
    try:
        container = self.query_one(f"#{container_id}", VerticalScroll)
    except Exception:
        return False

    focusable = [w for w in container.children if isinstance(w, row_types) and w.can_focus]
    if not focusable:
        return False

    focused = self.focused

    # If current focus is on the Tabs bar and direction is down, focus first row
    tabbed = self.query_one(TabbedContent)
    tabs_widget = tabbed.query_one(Tabs)
    if focused is tabs_widget or (focused is not None and focused.parent is tabs_widget):
        if direction == 1:
            focusable[0].focus()
            focusable[0].scroll_visible()
            return True
        return False

    # If no row is focused, focus the first (down) or last (up) row
    if not isinstance(focused, row_types):
        target = focusable[0] if direction == 1 else focusable[-1]
        target.focus()
        target.scroll_visible()
        return True

    # Find current index
    try:
        idx = focusable.index(focused)
    except ValueError:
        focusable[0].focus()
        focusable[0].scroll_visible()
        return True

    new_idx = idx + direction

    # At boundary: up past top → focus tabs; down past bottom → stop
    if new_idx < 0:
        tabs_widget.focus()
        return True
    if new_idx >= len(focusable):
        return True  # Stop at bottom, don't wrap

    focusable[new_idx].focus()
    focusable[new_idx].scroll_visible()
    return True
```

### Step 3: Refactor `on_key()` to use the helper

Replace the existing tab-specific up/down blocks with calls to `_navigate_rows()`:

**A. Dashboard tab** (currently has NO up/down navigation at all):
Add a new block before the Enter handler for NodeRow:
```python
# Up/down: navigate NodeRow items in Dashboard
if event.key in ("up", "down") and tabbed.active == "tab_dashboard":
    direction = 1 if event.key == "down" else -1
    if self._navigate_rows(direction, "node_list_pane", (NodeRow,)):
        event.prevent_default()
        event.stop()
        return
```

**B. Actions tab** (wizard steps 1-2, lines 941-959):
Replace the existing `isinstance(focused, OperationRow)` check with `_navigate_rows()`. Keep the disabled-row filtering by using a lambda or by filtering inside the helper. Actually, since `OperationRow` already sets `self.can_focus = not disabled`, the helper's `w.can_focus` check handles this.

Replace lines 941-959:
```python
if event.key in ("up", "down") and self._wizard_step in (1, 2):
    direction = 1 if event.key == "down" else -1
    if self._navigate_rows(direction, "actions_content", (OperationRow,)):
        event.prevent_default()
        event.stop()
        return
```

**C. Status tab** (lines 1031-1052):
Replace with:
```python
if event.key in ("up", "down") and tabbed.active == "tab_status":
    direction = 1 if event.key == "down" else -1
    if self._navigate_rows(direction, "status_content", (GroupRow, AgentStatusRow, StatusLogRow)):
        event.prevent_default()
        event.stop()
        return
```

### Step 4: Handle down-arrow from Tabs bar (all tabs)

Add a handler at the top of `on_key()` (after the modal check) for when the Tabs widget has focus and down is pressed:

```python
# Down from tab bar: focus first row in active tab
if event.key == "down":
    tabs_widget = tabbed.query_one(Tabs)
    if self.focused is tabs_widget:
        tab_to_container = {
            "tab_dashboard": ("node_list_pane", (NodeRow,)),
            "tab_actions": ("actions_content", (OperationRow,)),
            "tab_status": ("status_content", (GroupRow, AgentStatusRow, StatusLogRow)),
        }
        mapping = tab_to_container.get(tabbed.active)
        if mapping:
            if self._navigate_rows(1, mapping[0], mapping[1]):
                event.prevent_default()
                event.stop()
                return
```

### Step 5: Handle up arrow for tabs without rows (Graph, Compare)

For tabs that have no focusable rows, pressing up should still reach the tab bar:

```python
# Up on Graph/Compare tab: focus tab bar directly
if event.key == "up" and tabbed.active in ("tab_dag", "tab_compare"):
    tabs_widget = tabbed.query_one(Tabs)
    tabs_widget.focus()
    event.prevent_default()
    event.stop()
    return
```

## Summary of Behavior Changes

| Scenario | Before | After |
|----------|--------|-------|
| Dashboard: up/down pressed | Nothing | Cycles through NodeRow items |
| Any tab: nothing focused + down | Nothing | Focuses first focusable row |
| Any tab: nothing focused + up | Nothing | Focuses last focusable row |
| Any tab: topmost row + up | Nothing (stops) | Focuses tab bar |
| Tab bar focused + down | Default Textual behavior | Focuses first row in active tab |
| Tab bar focused + left/right | Already works (Textual built-in) | No change |
| Bottom row + down | Wraps to top (current) | Stops at bottom (no wrap) |

## Verification

1. Run the brainstorm TUI: `python3 .aitask-scripts/brainstorm/brainstorm_app.py <task_num>`
2. Test on Dashboard tab: press down/up without clicking first — should navigate NodeRow items
3. Test on Actions tab: press down without clicking — should focus first operation
4. Test on Status tab: same behavior
5. Test up past topmost item — should move focus to tab bar
6. Test left/right on tab bar — should switch tabs
7. Test down from tab bar — should focus first row in the active tab
8. Test Graph/Compare tabs — up should reach tab bar

## Final Implementation Notes
- **Actual work done:** Implemented exactly as planned — added `Tabs` import, `_navigate_rows()` helper, Dashboard tab navigation, tab-bar focus on up-past-top, down-from-tab-bar to content, Graph/Compare tab-bar focus, and refactored Actions/Status tab navigation to use the shared helper.
- **Deviations from plan:** Simplified the Tabs bar focus check in `_navigate_rows()` — used `focused is tabs_widget` instead of also checking `focused.parent is tabs_widget`, since `Tabs` is the focusable widget (individual `Tab` items have `can_focus = False`).
- **Issues encountered:** None. The plan's `w.can_focus` check in `_navigate_rows()` correctly handles disabled `OperationRow` widgets since they set `can_focus = not disabled`.
- **Key decisions:** Changed wrapping behavior from modulo (wrap around) to stop-at-boundary for down direction, and focus-tab-bar for up direction. This matches the user's requested behavior.

## Step 9 (Post-Implementation)
Archive task and plan after commit.
