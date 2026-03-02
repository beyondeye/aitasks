---
priority: medium
effort: low
depends: [t286_1]
issue_type: feature
status: Ready
labels: [ui]
created_at: 2026-03-02 15:49
updated_at: 2026-03-02 15:49
---

## Context

This is child task 2 of the "Allow mouse click to change option" feature (t286). The CycleField toggle widget in ait board only supports keyboard (Left/Right arrows) for changing options. Clicking focuses the widget but doesn't select an option. Users expect clicking on a specific option text to select it directly.

**Depends on:** t286_1 (same change applied to settings first, use as reference)

The CycleField class in the board is a duplicate of the one in settings. The same two methods need to be added.

## Key Files to Modify

1. **`aiscripts/board/aitask_board.py`** (~line 728-787)
   - The `CycleField` class extends `Static` from Textual
   - Add `_option_index_at()` helper and `on_click()` handler between `cycle_next` (line 770) and `on_key` (line 772)

## Reference Files for Patterns

- **`aiscripts/board/aitask_board.py`** lines 752-760 — The `render()` method (identical to settings version). The rendered format is:
  ```
    Label:  ◀ opt1 | opt2 | opt3 ▶
  ```

- **`aiscripts/settings/settings_app.py`** — The sibling task (t286_1) adds the same methods here first. Use as direct reference for the implementation.

- **Textual API** — `event.get_content_offset(self)` returns click position relative to widget content area.

## Implementation Plan

### Add `_option_index_at` helper method

Insert after `cycle_next()` (after line 770):

```python
def _option_index_at(self, cx):
    """Map content x-coordinate to option index, -1 for ◀, -2 for ▶."""
    prefix_len = len(f"  {self.label}:  \u25c0 ")
    if cx == prefix_len - 2:
        return -1  # left arrow
    pos = prefix_len
    for i, opt in enumerate(self.options):
        opt_width = len(opt) + 2
        if pos <= cx < pos + opt_width:
            return i
        pos += opt_width
        if i < len(self.options) - 1:
            pos += 3  # " | "
    if cx == pos + 1:
        return -2  # right arrow
    return None
```

### Add `on_click` handler

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

Note: The board version uses `id: str = None` (older style) vs settings `id: str | None = None`. For consistency, use the board's style in the new methods (no type hints on return, or match the file's existing style).

## Verification Steps

1. Run `python3 aiscripts/board/aitask_board.py`
2. Open a task detail (click on a task card)
3. Find CycleField widgets (Priority, Effort, Status, Type)
4. Click on different option texts — verify the selection changes
5. Click on ◀/▶ arrows — verify cycling works
6. Click on separators — verify no change
7. Verify keyboard Left/Right still works
