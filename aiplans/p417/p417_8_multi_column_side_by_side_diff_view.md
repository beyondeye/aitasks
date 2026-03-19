---
Task: t417_8_multi_column_side_by_side_diff_view.md
Parent Task: aitasks/t417_diff_viewer_tui_for_brainstorming.md
Sibling Tasks: aitasks/t417/t417_7_*.md, aitasks/t417/t417_9_*.md
Archived Sibling Plans: aiplans/archived/p417/p417_*_*.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: Multi-Column Side-by-Side Diff View (t417_8)

## Context

The DiffViewerScreen (t417_6) shows diffs in a single interleaved view — both files' lines are mixed together with color coding. This makes it hard to visually compare two plans side by side. This task adds a side-by-side layout where each file gets its own column, toggled with `v`.

## Files to Modify

- `.aitask-scripts/diffviewer/diff_display.py` — New dataclass, flattener, renderer, layout API
- `.aitask-scripts/diffviewer/diff_viewer_screen.py` — Toggle binding, state, info bar update
- `tests/test_diff_display.py` — Unit tests for side-by-side flattener

No CSS changes needed — side-by-side is a Rich Table column layout within the existing `Static` widget.

## Implementation Steps

### 1. Add `_SideBySideLine` dataclass (diff_display.py, after line 56)

```python
@dataclass
class _SideBySideLine:
    """One row in the side-by-side display, pairing left and right content."""
    main_lineno: int | None
    main_content: str
    other_lineno: int | None
    other_content: str
    tag: str
    source_plan: str = ""
```

### 2. Add `_flatten_hunks_side_by_side()` function (diff_display.py, after `_all_equal`)

Converts `DiffHunk` list into `_SideBySideLine` rows with horizontal alignment:
- **equal**: both sides populated
- **insert**: left blank, right has content
- **delete**: left has content, right blank
- **replace**: pair main/other lines row-by-row, pad shorter side with blanks (`max(len(main), len(other))` rows)
- **moved**: pair both sides row-by-row (same as replace logic)

### 3. Add state to `DiffDisplay.__init__`

Add `_sbs_lines: list[_SideBySideLine] = []` and `_side_by_side: bool = False`.

### 4. Add `_active_lines_count()` helper and `set_layout()` method

```python
def _active_lines_count(self) -> int:
    return len(self._sbs_lines) if self._side_by_side else len(self._flat_lines)

def set_layout(self, side_by_side: bool) -> None:
    if self._side_by_side == side_by_side:
        return
    self._side_by_side = side_by_side
    self._cursor_line = 0
    if self._active_lines_count() > 0:
        self._render_diff()
        self.scroll_home(animate=False)
```

### 5. Update all load methods to populate `_sbs_lines`

In `load_diff()`, `load_multi_diff()`, and `set_active_comparison()` — add:
```python
self._sbs_lines = _flatten_hunks_side_by_side(diff.hunks)
```
alongside existing `self._flat_lines = _flatten_hunks(diff.hunks)`.

Also update `_show_message()` to clear `self._sbs_lines = []`.

### 6. Refactor `_render_diff()` into dispatcher

Rename current body to `_render_interleaved()`, make `_render_diff()` dispatch:
```python
def _render_diff(self) -> None:
    if self._side_by_side:
        self._render_side_by_side()
    else:
        self._render_interleaved()
```

### 7. Add `_render_side_by_side()` method

5-column Rich Table: `main_lineno(5) | main_content(half) | gutter(3) | other_lineno(5) | other_content(half)`

Color application per tag:
- **equal**: both sides `dim`
- **delete**: left side gets `TAG_STYLES["delete"]` (white on red), right blank
- **insert**: right side gets `TAG_STYLES["insert"]` (white on green), left blank
- **replace**: both sides get `TAG_STYLES["replace"]` (white on goldenrod)
- **moved**: both sides get `TAG_STYLES["moved"]` (white on cyan)

Gutter: 3 chars wide (` X `) — shows tag gutter char or plan letter for multi-diff.

### 8. Update cursor navigation to use `_active_lines_count()`

Update `_move_cursor()`, `action_cursor_end()`, and `on_resize()` to use `self._active_lines_count()` instead of `len(self._flat_lines)`.

### 9. Add toggle to DiffViewerScreen

- Add `_side_by_side: bool = False` to `__init__`
- Add binding: `Binding("v", "toggle_layout", "Layout")`
- Add action:
  ```python
  def action_toggle_layout(self) -> None:
      self._side_by_side = not self._side_by_side
      display = self.query_one("#diff_viewer", DiffDisplay)
      display.set_layout(self._side_by_side)
      self._update_info_bar()
  ```
- Update `_update_info_bar()` to append layout label ("Side-by-side" or "Interleaved")
- Add `display.set_layout(self._side_by_side)` at end of `_load_current_view()` for sync

### 10. Add unit tests (test_diff_display.py)

Import `_SideBySideLine`, `_flatten_hunks_side_by_side`. Add `TestFlattenHunksSideBySide` class with tests for: equal, insert, delete, replace (uneven lengths), moved, empty hunks, and end-to-end with real test plans.

## Verification

- Launch diff viewer with test plans, press `v` to toggle layouts
- Side-by-side: equal lines align horizontally, inserts blank on left, deletes blank on right
- Replace hunks pair lines row-by-row with padding for uneven lengths
- Cursor navigation (up/down/pgup/pgdn/home/end) works in both layouts
- Mode switching (`m`) and comparison cycling (`n`/`p`) work in both layouts
- Info bar shows current layout mode
- Window resize re-renders correctly
- Run: `cd /home/ddt/Work/aitasks && python -m unittest tests.test_diff_display -v`

## Post-Review Changes

### Change Request 1 (2026-03-19 09:40)
- **Requested by user:** Colors make text nearly invisible in dark themes. The dark_goldenrod replace background with white text is hard to read. Colors should be theme-aware.
- **Changes made:** Updated `TAG_STYLES` to use bright, high-contrast hex colors matching `PLAN_COLORS` palette: insert=#50FA7B (green), delete=#FF5555 (red), replace=#FFB86C (orange), moved=#8BE9FD (cyan). Switched text to black for insert/replace/moved (bright backgrounds) and kept white for delete (red background).
- **Files affected:** `.aitask-scripts/diffviewer/diff_display.py`

## Final Implementation Notes

- **Actual work done:** Added `_SideBySideLine` dataclass, `_flatten_hunks_side_by_side()` module-level function, `_render_side_by_side()` method (5-column Rich Table), `set_layout()`/`_active_lines_count()` helpers. Refactored `_render_diff()` into dispatcher + `_render_interleaved()`. Updated all load methods and cursor navigation to support dual line lists. Added `v` keybinding and layout toggle to `DiffViewerScreen`. Updated info bar to show layout mode. Also updated `TAG_STYLES` color palette for better dark/light theme readability.
- **Deviations from plan:** Updated `TAG_STYLES` colors (not in original plan) per user feedback. Used bright hex colors (#50FA7B, #FF5555, #FFB86C, #8BE9FD) with black text on bright backgrounds instead of original dark_* named colors with white text.
- **Issues encountered:** Original `TAG_STYLES` used `dark_goldenrod` background with white text for replace, which was nearly invisible in dark themes. Fixed by switching to brighter background colors with black text.
- **Key decisions:** Both `_flat_lines` and `_sbs_lines` are populated eagerly on every load for instant layout switching. Side-by-side gutter is 3 chars wide (` X `) vs 1 char in interleaved for better visual separation. Rich Style objects cannot use Textual CSS design tokens, so hex colors were used instead.
- **Notes for sibling tasks:** `DiffDisplay` now exposes `set_layout(side_by_side: bool)` as public API. `_SideBySideLine` dataclass and `_flatten_hunks_side_by_side()` are exported for testing. Word-level (intra-line) diff highlighting for replace lines in side-by-side view is tracked as t417_9. The `TAG_STYLES` color palette was updated and affects both interleaved and side-by-side views.

## Post-Implementation

Step 9 of the task-workflow: archive task, push changes.
