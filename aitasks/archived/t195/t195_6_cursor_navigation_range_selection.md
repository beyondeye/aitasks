---
priority: medium
effort: medium
depends: [t195_3, t195_5]
issue_type: feature
status: Done
labels: [codebrowser]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-25 12:18
updated_at: 2026-02-25 23:18
completed_at: 2026-02-25 23:18
---

## Context

This is child task 6 of t195 (Python Code Browser TUI). It adds cursor navigation and range selection to the code viewer. Users need to move a cursor through the code (with up/down arrows) and select line ranges (with shift+arrows) to specify which code sections to explain via Claude Code (t195_7).

The code viewer (t195_3) renders a Rich Table into a Static widget. Cursor highlighting means applying a distinct background to the current line's row. Range selection means applying a different background to a contiguous block of lines.

## Key Files to Modify

- **`aiscripts/codebrowser/code_viewer.py`** (MODIFY):
  - Add cursor state: `_cursor_line: int = 0`, `_selection_start: int | None = None`, `_selection_end: int | None = None`
  - `move_cursor(line: int)`: update cursor line, scroll to make it visible, rebuild display
  - `extend_selection(direction: int)`: extend selection range by 1 line up or down
  - `clear_selection()`: clear selection start/end
  - `get_selected_range() -> tuple[int, int] | None`: return current selection range
  - In `_rebuild_display()`: apply cursor highlight (e.g., background `$primary 30%` on cursor row) and selection highlight (e.g., background `$accent 20%` on selected rows)
  - Emit `CursorMoved(line, total)` message for the info bar
  - Auto-scroll: use `scroll_to_region()` or `scroll_visible()` to keep cursor in view
- **`aiscripts/codebrowser/codebrowser_app.py`** (MODIFY):
  - Add bindings: `up`/`down` for cursor movement, `shift+up`/`shift+down` for selection, `escape` for clear selection, `g` for go-to-line
  - `action_cursor_up/down()`: call `code_viewer.move_cursor()`
  - `action_select_up/down()`: call `code_viewer.extend_selection()`
  - `action_clear_selection()`: call `code_viewer.clear_selection()`
  - `action_go_to_line()`: push a `GoToLineScreen` modal
  - Update file info bar: show "Line 42/300" from `CursorMoved` message
  - Handle focus: cursor keys only active when code viewer has focus
- **`aiscripts/codebrowser/codebrowser_app.py`** (NEW modal): `GoToLineScreen(ModalScreen)`:
  - Simple input field for line number
  - On submit: dismiss with the line number, app moves cursor to that line

## Reference Files for Patterns

- `aiscripts/codebrowser/code_viewer.py` (from t195_3, t195_5): `_rebuild_display()` method, Rich Table construction
- `aiscripts/board/aitask_board.py` (lines 1580-1626): `CommitMessageScreen(ModalScreen)` — pattern for simple input modal
- `aiscripts/board/aitask_board.py` (lines 2199-2350): Navigation action methods pattern (cursor_up, cursor_down, etc.)
- Rich `Table` API: `add_row()` accepts `style` parameter for row-level background

## Implementation Plan

1. Add cursor state to `CodeViewer`:
   - `self._cursor_line: int = 0`
   - `self._selection_start: int | None = None`
   - `self._selection_end: int | None = None`
   - `self._total_lines: int = 0`

2. Add message class: `class CursorMoved(Message)` with `line: int` and `total: int` attributes

3. Modify `_rebuild_display()`:
   - When building each table row, check:
     - If row index == `_cursor_line`: apply cursor style (e.g., `Style(bgcolor="grey27")`)
     - If row index is within selection range: apply selection style (e.g., `Style(bgcolor="dark_blue")`)
     - Both styles stack: cursor within selection gets cursor style (takes precedence)
   - Use `table.add_row(*columns, style=row_style)` for per-row styling

4. Add `move_cursor(line: int)`:
   - Clamp to [0, total_lines - 1]
   - Set `self._cursor_line = line`
   - Call `_rebuild_display()`
   - Scroll to cursor: `self.scroll_to_region(Region(0, line, 1, 1))` or equivalent
   - Post `CursorMoved(line + 1, self._total_lines)`

5. Add `extend_selection(direction: int)`:
   - If no selection: `_selection_start = _cursor_line`
   - Move cursor by direction (+1 or -1)
   - `_selection_end = _cursor_line`
   - Ensure start <= end (swap if needed for display)
   - Call `_rebuild_display()`

6. Add `clear_selection()`:
   - Reset `_selection_start = _selection_end = None`
   - Call `_rebuild_display()`

7. Add `get_selected_range() -> tuple[int, int] | None`:
   - If both start and end set: return `(min(start, end) + 1, max(start, end) + 1)` (1-indexed for user display)
   - Else: return None

8. Create `GoToLineScreen(ModalScreen)`:
   - `compose()`: Container with Label("Go to line:") + Input(type="integer") + Button("Go")
   - On submit/Enter: `self.dismiss(int(input.value))`
   - Cancel on Escape

9. Wire in `codebrowser_app.py`:
   - Bindings (only active when code viewer focused):
     - `Binding("up", "cursor_up", "Cursor up", show=False)`
     - `Binding("down", "cursor_down", "Cursor down", show=False)`
     - `Binding("shift+up", "select_up", "Select up", show=False)`
     - `Binding("shift+down", "select_down", "Select down", show=False)`
     - `Binding("escape", "clear_selection", "Clear selection", show=False)`
     - `Binding("g", "go_to_line", "Go to line")`
   - Action methods: delegate to `self.query_one(CodeViewer).move_cursor()` etc.
   - Handle `CursorMoved` message: update info bar "Line X/Y"
   - Handle `GoToLineScreen` callback: `code_viewer.move_cursor(line - 1)` (convert to 0-indexed)

## Verification Steps

1. Select a file, press down arrow — cursor highlight should move down through lines
2. Press up arrow — cursor moves up
3. Hold shift+down — selection range expands downward (different highlight color)
4. Press escape — selection clears, cursor stays
5. Press `g`, type "100", press Enter — cursor jumps to line 100
6. Cursor at bottom of file — doesn't go past last line
7. Cursor at top — doesn't go past line 1
8. File info bar shows "Line 42/300" format, updates in real-time
9. When cursor moves off-screen, view auto-scrolls to follow it
