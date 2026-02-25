---
priority: low
effort: high
depends: [195_6]
issue_type: performance
status: Ready
labels: [codebrowser]
created_at: 2026-02-25 12:19
updated_at: 2026-02-25 12:19
---

## Context

This is child task 9 of t195 (Python Code Browser TUI) — a risk mitigation follow-up for Risk 2 (large file performance). After cursor navigation is implemented, this task optimizes the code viewer for large files (3000+ lines) by implementing viewport windowing: only rendering a window of ~200 lines around the cursor instead of the entire file.

## Key Files to Modify

- **`aiscripts/codebrowser/code_viewer.py`** (MODIFY):
  - Add viewport windowing mode: activated when file exceeds a threshold (e.g., >2000 lines)
  - Track viewport offset: `_viewport_start`, `_viewport_size` (default 200)
  - In `_rebuild_display()`: only build Rich Table rows for the viewport window
  - Add viewport indicator in the gutter or info bar: show "Lines 450-650 of 5000"
  - Shift viewport when cursor moves outside visible range
  - Cache rendered `Rich.Text` objects per line: invalidate only on annotation/selection change, not on cursor move
  - Performance measurement: log render times with `time.perf_counter()` for profiling

## Reference Files for Patterns

- `aiscripts/codebrowser/code_viewer.py` (from t195_3, t195_5, t195_6): Current `_rebuild_display()` — the method to optimize
- Rich `Syntax` API: supports `line_range=(start, end)` for partial rendering

## Implementation Plan

1. Add performance measurement:
   - In `_rebuild_display()`, wrap with `time.perf_counter()` timing
   - Log render time if >50ms: `self.log(f"Render took {elapsed:.1f}ms for {lines} lines")`

2. Add viewport state:
   - `self._viewport_mode: bool = False` (auto-activated for large files)
   - `self._viewport_start: int = 0` (first visible line index)
   - `self._viewport_size: int = 200` (number of lines to render)
   - `self._line_threshold: int = 2000` (activate viewport above this)

3. Modify `load_file()`:
   - Set `self._viewport_mode = len(lines) > self._line_threshold`
   - If viewport mode: set initial viewport centered on line 0

4. Modify `_rebuild_display()`:
   - If viewport mode: only iterate lines `_viewport_start` to `_viewport_start + _viewport_size`
   - Adjust line numbers to reflect actual file position (not viewport position)
   - Add visual indicators at top/bottom: `... (N lines above)` and `... (N lines below)`

5. Modify `move_cursor()`:
   - If cursor moves outside viewport: shift viewport to center on cursor
   - Avoid shifting on every cursor move — only when cursor exits viewport bounds
   - Smooth shift: move viewport by half-page rather than re-centering

6. Add line caching:
   - `self._line_cache: dict[int, Text] = {}` — cache syntax-highlighted Text objects per line
   - Invalidate cache on: file load, annotation change
   - Don't invalidate on: cursor move, selection change (these only affect row styles, not content)

7. Update info bar for viewport mode:
   - Show "Lines 450-650 of 5000 (viewport)" to indicate windowed rendering

## Verification Steps

1. Open `aitask_board.py` (~2900 lines) — should activate viewport mode
2. Cursor navigation should remain smooth (no visible lag)
3. Measure: cursor movement render time should be <50ms even for large files
4. Scrolling through the file should work: viewport shifts to follow cursor
5. Line numbers should always be correct (actual file line numbers, not viewport-relative)
6. Annotations should display correctly within the viewport
7. Open a small file (<2000 lines) — should NOT activate viewport mode
8. Compare render times: small file (full render) vs large file (viewport) should be similar
