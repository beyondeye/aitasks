---
priority: medium
effort: low
depends: []
issue_type: feature
status: Implementing
labels: [ait_settings]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-02 15:49
updated_at: 2026-03-02 15:50
---

## Context

This is child task 1 of the "Allow mouse click to change option" feature (t286). The CycleField toggle widget in ait settings only supports keyboard (Left/Right arrows) for changing options. Clicking focuses the widget but doesn't select an option. Users expect clicking on a specific option text to select it directly.

## Key Files to Modify

1. **`aiscripts/settings/settings_app.py`** (~line 369-427)
   - The `CycleField` class extends `Static` from Textual
   - Add `_option_index_at()` helper and `on_click()` handler between `cycle_next` (line 410) and `on_key` (line 412)

## Reference Files for Patterns

- **`aiscripts/settings/settings_app.py`** lines 392-400 — The `render()` method that produces the displayed text. The rendered format (after Rich markup stripping) is:
  ```
    Label:  ◀ opt1 | opt2 | opt3 ▶
  ```
  Where prefix is `  {label}:  ◀ `, each option is ` {opt} ` (space-padded), separators are ` | ` (3 chars).

- **Textual API** — `event.get_content_offset(self)` returns click position relative to widget content area (accounts for padding/borders). Returns `None` if click is outside content.

## Implementation Plan

### Add `_option_index_at` helper method

Insert after `cycle_next()` (after line 410):

```python
def _option_index_at(self, cx: int) -> int | None:
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

## Verification Steps

1. Run `python3 aiscripts/settings/settings_app.py`
2. Navigate to a tab with CycleField widgets (e.g., Overwrite, Auto-refresh, Sync toggles)
3. Click on different option texts — verify the selection changes to the clicked option
4. Click on ◀/▶ arrows — verify cycling works
5. Click on separators (`|`) — verify no change occurs
6. Click on the label text — verify no change occurs
7. Verify keyboard Left/Right still works as before
