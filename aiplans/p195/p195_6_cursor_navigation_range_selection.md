---
Task: t195_6_cursor_navigation_range_selection.md
Parent Task: aitasks/t195_python_codebrowser.md
Sibling Tasks: aitasks/t195/t195_3_*.md, aitasks/t195/t195_5_*.md, aitasks/t195/t195_7_*.md
Archived Sibling Plans: aiplans/archived/p195/p195_*_*.md
Branch: main
Base branch: main
---

# Plan: t195_6 — Cursor Navigation and Range Selection

## Steps

### 1. Add cursor state to `CodeViewer`
- `_cursor_line: int = 0`
- `_selection_start: int | None = None`
- `_selection_end: int | None = None`
- `_total_lines: int = 0`

### 2. Add `CursorMoved` message class
- Attributes: `line: int`, `total: int`

### 3. Modify `_rebuild_display()`
- Per row: check if cursor line → apply `Style(bgcolor="grey27")`
- Check if within selection → apply `Style(bgcolor="dark_blue")`
- Cursor within selection takes cursor style (precedence)
- Use `table.add_row(*cols, style=row_style)`

### 4. Add cursor methods
- `move_cursor(line: int)`: clamp, set, rebuild, scroll to, post CursorMoved
- `extend_selection(direction: int)`: set start if None, move cursor, set end
- `clear_selection()`: reset start/end, rebuild
- `get_selected_range() -> tuple[int, int] | None`: return 1-indexed range

### 5. Create `GoToLineScreen(ModalScreen)`
- Input field + "Go" button
- Dismiss with line number on Enter/submit

### 6. Wire in app
- Bindings: up/down (cursor), shift+up/down (select), escape (clear), g (go-to-line)
- Handle CursorMoved: update info bar "Line X/Y"
- GoToLineScreen callback: move_cursor(line - 1)
- Focus guard: cursor keys only when code viewer focused

## Verification
- Arrow keys move cursor with highlight
- Shift+arrows extend selection
- Escape clears selection
- `g` opens go-to-line modal
- Info bar shows "Line X/Y"
- Auto-scroll follows cursor
