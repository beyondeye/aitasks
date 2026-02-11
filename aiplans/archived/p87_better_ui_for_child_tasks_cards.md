---
Task: t87_better_ui_for_child_tasks_cards.md
Branch: main (working directly)
---

## Context

Child task cards in the aitask_board are currently only distinguished from parent cards by a 1-char left margin indent. This makes it hard to visually identify the parent-child hierarchy when a task is expanded with the "x" command.

## Approach: External Tree Connector

Add a "↳" connector symbol **outside** (to the left of) each child card, with no changes to the child card's border style. The connector provides a clear visual hierarchy indicator.

## Changes

### File: `aitask_board/aitask_board.py`

**1. Wrap child cards in a Horizontal container with a connector label** (in `KanbanColumn.compose()`, ~line 463-467):

Current:
```python
for child in children:
    yield TaskCard(child, self.manager, is_child=True, column_id=self.col_id)
```

New:
```python
for child in children:
    with Horizontal(classes="child-wrapper"):
        yield Static("↳", classes="child-connector")
        yield TaskCard(child, self.manager, is_child=True, column_id=self.col_id)
```

**2. Remove the left margin from child cards** (in `TaskCard.on_mount()`, ~line 421-422):

Change child margin from `(0, 0, 1, 1)` to `(0, 0, 1, 0)` since the Horizontal wrapper + connector now handles the left offset.

**3. Add CSS styles** (in `KanbanApp.CSS`, ~line 1102):

```css
.child-wrapper { height: auto; margin: 0 0 0 1; }
.child-connector { width: 2; height: auto; color: $text-muted; margin-top: 1; }
```

- `margin: 0 0 0 1` on the wrapper provides the overall left indent
- `width: 2` gives the connector enough space for "↳" + spacing
- `margin-top: 1` vertically aligns the connector with the card's top border line

## Verification

1. Run `python aitask_board/aitask_board.py`
2. Navigate to a parent task that has children
3. Press "x" to expand children
4. Verify: "↳" connector appears to the left of each child card
5. Verify: Arrow key navigation (up/down) still works correctly between parent and child cards
6. Verify: Child card focus/blur styling still works
7. Verify: Task movement actions are still disabled for child cards

## Post-Review Changes

### Change Request 1 (2026-02-11)
- **Requested by user:** Remove padding left/right of connector; child cards overflow column on right side
- **Changes made:** Added `padding: 0` to connector, added `.child-wrapper TaskCard { width: 1fr; }` to constrain card width
- **Files affected:** aitask_board/aitask_board.py

### Change Request 2 (2026-02-11)
- **Requested by user:** Connector still has right-side padding
- **Changes made:** Changed connector from `width: 2` to `width: auto` and set explicit `margin: 1 0 0 0`
- **Files affected:** aitask_board/aitask_board.py

### Change Request 3 (2026-02-11)
- **Requested by user:** Left margin on connector still present
- **Changes made:** Removed wrapper's `margin: 0 0 0 1`, making connector flush with column edge
- **Files affected:** aitask_board/aitask_board.py

## Final Implementation Notes
- **Actual work done:** Added external "↳" tree connector to the left of child task cards using a Horizontal wrapper with a Static connector widget
- **Deviations from plan:** Initial plan had wrapper left margin and fixed connector width, but user preferred flush alignment with auto-width connector
- **Issues encountered:** Textual widget sizing required iterative CSS tuning — `width: auto` on the connector and `width: 1fr` on the child card were needed to prevent overflow and eliminate extra spacing
- **Key decisions:** No border style changes to child cards (user preference); connector flush with column edge rather than indented
