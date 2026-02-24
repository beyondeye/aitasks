---
Task: t229_double_click_to_expand_parent_task.md
Branch: main
Base branch: main
---

## Context

In the ait board TUI, double-clicking a task card always opens the detail view (`action_view_details()`). The user wants collapsed parent tasks with children to expand on double-click instead, making the interaction more intuitive — you see the children first, then can double-click again (when expanded) to open details.

## Plan

Modify `TaskCard.on_click()` in `aiscripts/board/aitask_board.py` (line 555-558).

**New behavior:**
```python
def on_click(self, event):
    self.focus()
    if event.chain == 2:
        # Collapsed parent with children → expand instead of opening details
        if not self.is_child:
            task_num, _ = TaskCard._parse_filename(self.task_data.filename)
            children = self.manager.get_child_tasks_for_parent(task_num)
            if children and self.task_data.filename not in self.app.expanded_tasks:
                self.app.action_toggle_children()
                return
        self.app.action_view_details()
```

**Logic:**
1. If the card is a parent (not `is_child`)
2. AND has children (`get_child_tasks_for_parent` returns non-empty)
3. AND is currently collapsed (filename NOT in `self.app.expanded_tasks`)
4. → Call `action_toggle_children()` to expand, and return early
5. Otherwise → open details as before (expanded parents, children, childless parents)

## Files to modify

- `aiscripts/board/aitask_board.py` — `TaskCard.on_click()` (lines 555-558)

## Verification

1. Run `./ait board`
2. Find a parent task with children (collapsed) → double-click → children should expand
3. Double-click the same (now expanded) parent → detail view should open
4. Double-click a child task → detail view should open
5. Double-click a task with no children → detail view should open

## Final Implementation Notes
- **Actual work done:** Modified `TaskCard.on_click()` to check if a double-clicked card is a collapsed parent with children, and expand instead of opening details. Exactly as planned.
- **Deviations from plan:** None
- **Issues encountered:** None
- **Key decisions:** Reused existing `action_toggle_children()` and `expanded_tasks` set rather than duplicating expand logic

## Post-Implementation

- Step 9: Archive task and plan
