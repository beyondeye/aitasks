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

## Post-Review Changes

### Change Request 1 (2026-02-25 23:30)
- **Requested by user:** Cursor always pinned to top of screen when using arrow keys — should only scroll when cursor reaches viewport edge
- **Changes made:** Replaced `scroll_to(y=line)` with `_scroll_cursor_visible()` that checks viewport bounds and only scrolls with a 2-line margin when cursor nears edge
- **Files affected:** `aiscripts/codebrowser/code_viewer.py`

### Change Request 2 (2026-02-25 23:35)
- **Requested by user:** Selection should persist visually when moving cursor without shift, but reset when shift+arrow is pressed again after releasing shift
- **Changes made:** Added `_selection_active` flag. Plain movement marks selection inactive (keeps visual). Next shift+arrow detects inactive state and starts fresh selection from cursor position. Escape clears selection entirely.
- **Files affected:** `aiscripts/codebrowser/code_viewer.py`

## Final Implementation Notes
- **Actual work done:** All 6 plan steps implemented. Added `CursorMoved(Message)` nested class, `BINDINGS` for up/down/shift+up/shift+down/escape on `CodeViewer`, cursor state (`_cursor_line`, `_selection_start`, `_selection_end`, `_selection_active`), per-row styling in `_rebuild_display()` using `CURSOR_STYLE`/`SELECTION_STYLE` constants, `_scroll_cursor_visible()` with viewport-aware 2-line margin scrolling, `move_cursor()`, `extend_selection()`, `clear_selection()`, `get_selected_range()`, and action methods. Created `GoToLineScreen(ModalScreen)` in the app file following `CommitMessageScreen` pattern. Added `g` binding, `on_code_viewer_cursor_moved` handler, and refactored info bar to centralized `_update_info_bar()` helper with `_cursor_info`/`_annotation_info` state.
- **Deviations from plan:** (1) Moved `scroll_home(animate=False)` from `_rebuild_display()` to `load_file()` only — prevents scroll reset on every cursor move/selection change. (2) Replaced naive `scroll_to(y=line)` with `_scroll_cursor_visible()` after user feedback that cursor was always pinning to viewport top. (3) Added `_selection_active` flag for editor-standard selection behavior: selection persists visually during plain movement but resets on next shift+arrow press after shift release.
- **Issues encountered:** Initial scroll implementation always jumped cursor to top of viewport. Fixed with viewport-aware scrolling that only triggers when cursor nears edge (2-line margin).
- **Key decisions:** Used module-level `CURSOR_STYLE = Style(bgcolor="grey27")` and `SELECTION_STYLE = Style(bgcolor="dark_blue")` constants. Cursor style takes visual precedence over selection style. Bindings placed on `CodeViewer` widget (not App) so they only fire when the code viewer has focus. The `g` binding is on the App level since it pushes a modal screen.
- **Notes for sibling tasks:** `_rebuild_display()` no longer calls `scroll_home()` — callers handle scrolling. The `_selection_active` flag controls whether shift+arrow extends existing selection or starts fresh. `get_selected_range()` returns 1-indexed `(start, end)` tuple for use by t195_7 (Claude Code explain integration). The info bar is now managed centrally via `_update_info_bar()` which combines `_cursor_info` and `_annotation_info` — any new info bar fields should follow this pattern. `GoToLineScreen` CSS is defined in the App's CSS string.
