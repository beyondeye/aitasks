---
Task: t286_1_update_settings_cyclefield_mouse.md
Parent Task: aitasks/t286_allow_mouse_click_to_change_option.md
Sibling Tasks: aitasks/t286/t286_2_update_board_cyclefield_mouse.md
Archived Sibling Plans: (none yet)
Worktree: (none — current branch)
Branch: (current branch)
Base branch: main
---

# Plan: Add Mouse Click Support to CycleField in ait settings (t286_1)

## Overview

Add `on_click` handler and `_option_index_at` helper to the `CycleField` class in `aiscripts/settings/settings_app.py` so clicking an option text selects it directly.

## Steps

### 1. Add `_option_index_at` method

Insert after `cycle_next()` (after line 410) in `aiscripts/settings/settings_app.py`:

```python
def _option_index_at(self, cx: int) -> int | None:
    """Map content x-coordinate to option index, -1 for ◀, -2 for ▶."""
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
def on_click(self, event) -> None:
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

## Verification

1. Run `python3 aiscripts/settings/settings_app.py`
2. Click option texts on toggles — verify selection changes
3. Click ◀/▶ arrows — verify cycling
4. Click separators/label — verify no change
5. Verify keyboard Left/Right still works

## Final Implementation Notes

- **Actual work done:** Added `_option_index_at` and `on_click` methods to `CycleField` class in `settings_app.py`, exactly as planned.
- **Deviations from plan:** None — implemented as specified.
- **Issues encountered:** None.
- **Key decisions:** Used Textual's `get_content_offset()` API which correctly handles padding/border offsets. Arrow clicks (◀/▶) also supported for intuitive UX.
- **Notes for sibling tasks:** The board's `CycleField` (t286_2) is identical. Apply the same two methods. The board version uses older type hint style (`id: str = None`), so consider omitting return type hints on new methods for consistency — but either style works fine.

## Step 9 Reference

Post-implementation: archive child task via `./aiscripts/aitask_archive.sh 286_1`
