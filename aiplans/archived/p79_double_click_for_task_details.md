---
Task: t79_double_click_for_task_details.md
Worktree: N/A (working on current branch)
Branch: main
Base branch: main
---

# Plan: Add Double-Click to Open Task Details (t79)

## Context

Currently in the aitask_board TUI, task details can only be opened by pressing Enter on a focused TaskCard. The user wants to also support double-click to open task details, which is a natural and expected interaction pattern.

## Approach

Textual 7.5.0 provides built-in double-click detection via the `Click` event's `chain` attribute (`chain=2` means double-click). We'll add an `on_click` handler to `TaskCard` that opens the detail screen on double-click.

## Changes

**File:** `aitask_board/aitask_board.py`

### 1. Add `on_click` handler to `TaskCard` class (after `on_blur` at line 376)

```python
def on_click(self, event):
    self.focus()
    if event.chain == 2:
        self.app.action_view_details()
```

This:
- Focuses the card on any click (single or double), which also visually selects it
- On double-click (`chain == 2`), triggers the same `action_view_details()` that Enter uses
- Reuses existing logic — no code duplication needed

## Verification

1. Run the app: `python3 aitask_board/aitask_board.py`
2. Single-click a task card → card should get focus (cyan border)
3. Double-click a task card → task detail modal should open
4. Enter key should still work as before

## Final Implementation Notes
- **Actual work done:** Added `on_click` handler to `TaskCard` class at line 378 of `aitask_board/aitask_board.py`. Exactly as planned — 4 lines of code.
- **Deviations from plan:** None
- **Issues encountered:** None
- **Key decisions:** Used Textual's built-in `Click.chain` attribute for double-click detection rather than manual timing logic. Single click also focuses the card for consistent UX.
