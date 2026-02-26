---
Task: t250_allow_click_to_select_line.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

## Context

The codebrowser's `CodeViewer` widget only supports keyboard navigation (up/down arrows) and shift+arrow for range selection. Users expect to click on a line to move the cursor there, and click+drag to select a range — standard code editor behavior.

## Plan

### File to modify: `aiscripts/codebrowser/code_viewer.py`

**1. Add `_mouse_dragging` state variable**

In `__init__`, add `self._mouse_dragging: bool = False` alongside the existing selection state vars.

**2. Add `on_mouse_down` handler — click start / drag start**

- Left button only (`event.button == 1`)
- Convert viewport y to content line: `scroll_y + event.y`
- Move cursor and begin selection tracking
- `capture_mouse()` ensures drag events continue even if mouse leaves the widget

**3. Add `on_mouse_move` handler — drag selection**

- Only acts during an active drag
- Updates cursor and selection end to follow mouse
- Auto-scrolls viewport when dragging near edges (reuses `_scroll_cursor_visible()`)

**4. Add `on_mouse_up` handler — finalize click/drag**

- Releases mouse capture
- If start == end (no drag movement), clears selection — behaves like a simple click-to-position
- If start != end (drag occurred), keeps the selection active

### No changes to `codebrowser_app.py`

The app already listens for `CursorMoved` messages and handles `get_selected_range()` — both work unchanged with mouse-driven cursor/selection.

## Verification

1. Run: `cd aiscripts/codebrowser && python codebrowser_app.py`
2. Test single left-click moves cursor to the clicked line
3. Test click+drag selects a range of lines (highlighted in dark blue)
4. Test drag past viewport edges auto-scrolls
5. Test keyboard navigation (up/down, shift+up/down) still works after click
6. Test scrollbar still works independently
7. Test Escape clears mouse-initiated selection

## Final Implementation Notes
- **Actual work done:** Added mouse click (single-click to position cursor) and click+drag (range selection) support to CodeViewer via `on_mouse_down`, `on_mouse_move`, `on_mouse_up` handlers. Used Textual's `capture_mouse()`/`release_mouse()` for reliable drag tracking.
- **Deviations from plan:** Added an early-return optimization in `on_mouse_move` to skip redundant rebuilds when cursor line hasn't changed. This was added after user testing revealed slow response times during drag.
- **Issues encountered:** Full table rebuild on every mouse move event causes noticeable lag on large files. This is a pre-existing architectural issue — the entire Rich Table is rebuilt on every cursor change. Task t195_9 (viewport windowing) already targets this.
- **Key decisions:** Used `on_mouse_down`/`on_mouse_move`/`on_mouse_up` instead of `on_click` to support both click and drag with a single unified approach. Coordinate conversion uses `scroll_y + event.y` to map viewport position to content line index.
