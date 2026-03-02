---
Task: t286_2_update_board_cyclefield_mouse.md
Parent Task: aitasks/t286_allow_mouse_click_to_change_option.md
Sibling Tasks: aitasks/t286/t286_1_update_settings_cyclefield_mouse.md
Archived Sibling Plans: aiplans/archived/p286/p286_1_*.md
Worktree: (none — current branch)
Branch: (current branch)
Base branch: main
---

# Plan: Add Mouse Click Support to CycleField in ait board (t286_2)

## Overview

Add `on_click` handler and `_option_index_at` helper to the `CycleField` class in `aiscripts/board/aitask_board.py`. Same change as t286_1 but for the board's duplicate CycleField.

## Steps

### 1. Add `_option_index_at` method

Insert after `cycle_next()` (after line 770) in `aiscripts/board/aitask_board.py`:

```python
def _option_index_at(self, cx):
    """Map content x-coordinate to option index, -1 for left arrow, -2 for right arrow."""
    prefix_len = len(f"  {self.label}:  \u25c0 ")
    if cx == prefix_len - 2:
        return -1
    pos = prefix_len
    for i, opt in enumerate(self.options):
        opt_width = len(opt) + 2
        if pos <= cx < pos + opt_width:
            return i
        pos += opt_width
        if i < len(self.options) - 1:
            pos += 3
    if cx == pos + 1:
        return -2
    return None
```

### 2. Add `on_click` method

Insert after `_option_index_at`:

```python
def on_click(self, event):
    """Select option directly when clicked."""
    content_offset = event.get_content_offset(self)
    if content_offset is None:
        return
    idx = self._option_index_at(content_offset.x)
    if idx == -1:
        self.cycle_prev()
    elif idx == -2:
        self.cycle_next()
    elif idx is not None and idx != self.current_index:
        self.current_index = idx
        self.refresh()
        self.post_message(self.Changed(self, self.current_value))
```

Note: Board file uses older type hint style (`id: str = None`), so new methods omit `-> None` and `-> int | None` type hints for consistency.

## Verification

1. Run `python3 aiscripts/board/aitask_board.py`
2. Open a task detail, find Priority/Effort/Status/Type toggles
3. Click option texts — verify selection changes
4. Click ◀/▶ arrows — verify cycling
5. Verify keyboard still works

## Step 9 Reference

Post-implementation: archive child task via `./aiscripts/aitask_archive.sh 286_2`
