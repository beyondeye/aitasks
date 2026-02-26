---
Task: t195_9_viewport_windowing_large_files.md
Parent Task: aitasks/t195_python_codebrowser.md
Sibling Tasks: aitasks/t195/t195_6_*.md
Archived Sibling Plans: aiplans/archived/p195/p195_*_*.md
Branch: main
Base branch: main
---

# Plan: t195_9 — Viewport Windowing for Large Files

## Steps

### 1. Add performance measurement
- Wrap `_rebuild_display()` with `time.perf_counter()` timing
- Log if >50ms

### 2. Add viewport state
- `_viewport_mode: bool` (auto-activated for files >2000 lines)
- `_viewport_start: int`, `_viewport_size: int = 200`
- `_viewport_threshold: int = 2000`, `_viewport_margin: int = 30`

### 3. Modify `_rebuild_display()` for viewport
- Only build rows for `[viewport_start, viewport_start + viewport_size]`
- Adjust line numbers to real file positions
- Show `··· N lines above/below ···` indicators
- Viewport-aware annotation gutter (`_build_annotation_gutter(vp_start, vp_end)`)

### 4. Modify `move_cursor()` for viewport
- `_ensure_viewport_contains_cursor()` shifts viewport when cursor nears margin
- `_scroll_cursor_visible()` uses viewport-relative cursor position

### 5. Mouse handler viewport offsets
- `on_mouse_down`: add `_viewport_start` offset and account for indicator row
- `on_mouse_move`: same offset, no viewport shifting during drag
- `on_mouse_up`: snap viewport to cursor position

### 6. Constant-speed edge scrolling
- Timer-based edge scroll (`_edge_scroll_tick` at 20Hz) when mouse exits visible area
- Direct viewport positioning during edge scroll (cursor at viewport edge, not margin)

### 7. Mouse wheel viewport shifting
- `on_mouse_scroll_down/up`: shift viewport when at scroll edges

### 8. Page Up/Page Down bindings

### 9. Update info bar
- Show selection range (`Sel 42–303`) instead of viewport info
- `viewport_info` property kept for debugging only

## Post-Review Changes

### Change Request 1 (2026-02-26)
- **Requested by user:** Opening large file only shows first 200 lines, can't scroll further
- **Changes made:** Added mouse wheel edge detection (`on_mouse_scroll_down/up`) that shifts viewport when scrolling reaches the rendered content boundary. Added Page Up/Page Down key bindings.
- **Files affected:** `aiscripts/codebrowser/code_viewer.py`

### Change Request 2 (2026-02-26)
- **Requested by user:** Mouse drag selection scrolls too fast (jumps from line 300 to 2500 in half a second)
- **Changes made:** Initially added throttle for `_ensure_viewport_contains_cursor()` during drag, then replaced with complete removal of viewport shifting during drag. Viewport now stays stable under the mouse during drag and snaps on mouse release.
- **Files affected:** `aiscripts/codebrowser/code_viewer.py`

### Change Request 3 (2026-02-26)
- **Requested by user:** Viewport shifts unexpectedly during mouse selection near line 200 boundary
- **Changes made:** Removed all viewport shifting from `on_mouse_move` — viewport is completely stable during mouse drag, only snaps on `on_mouse_up`.
- **Files affected:** `aiscripts/codebrowser/code_viewer.py`

### Change Request 4 (2026-02-26)
- **Requested by user:** Remove viewport indicator from info bar, show selection range instead
- **Changes made:** Replaced `viewport_info` display with selection range (`Sel X–Y`) in info bar. Kept `viewport_info` property for debugging.
- **Files affected:** `aiscripts/codebrowser/codebrowser_app.py`

### Change Request 5 (2026-02-26)
- **Requested by user:** During edge scrolling, cursor shown ~30 lines from screen edge instead of at the edge
- **Changes made:** Replaced `_ensure_viewport_contains_cursor()` in `_edge_scroll_tick()` with direct viewport positioning that places cursor 2-3 lines from the viewport window edge.
- **Files affected:** `aiscripts/codebrowser/code_viewer.py`

## Final Implementation Notes
- **Actual work done:** Viewport windowing for files >2000 lines (renders 200-line window), viewport-aware mouse handlers with separate coordinate translation for viewport mode, constant-speed timer-based edge scrolling (20Hz) during mouse drag, mouse wheel viewport shifting at content boundaries, Page Up/Page Down key bindings, selection range display in info bar, performance timing for `_rebuild_display()`.
- **Deviations from plan:** (1) Dropped line cache — `_highlighted_lines` already caches highlighted Text objects; the bottleneck is table row construction, not highlighting. (2) Info bar shows selection range instead of viewport position (user preference). (3) Edge scrolling uses timer-based constant-speed approach instead of per-event cursor movement for predictable scroll speed. (4) Viewport is completely stable during mouse drag — no shifting until mouse release — to prevent content jumping under the cursor. (5) Edge scroll tick uses direct viewport positioning (cursor at viewport edge) instead of margin-based `_ensure_viewport_contains_cursor()`.
- **Issues encountered:** (1) Mouse drag caused runaway scrolling because `_ensure_viewport_contains_cursor()` triggered on every high-frequency mouse event. Fixed by removing viewport shifts from `on_mouse_move` entirely. (2) During edge scrolling, cursor appeared ~30 lines from visible edge because `_ensure_viewport_contains_cursor()` uses a 30-line margin. Fixed by using direct viewport positioning in `_edge_scroll_tick()`. (3) Mouse coordinate translation needed to account for the "lines above" indicator row that appears when `viewport_start > 0`.
- **Key decisions:** `_viewport_threshold = 2000`, `_viewport_size = 200`, `_viewport_margin = 30` as instance variables (not class constants) for potential future configurability. Edge scroll rate at 20Hz (50ms interval). Mouse scroll edge detection uses `scroll_y >= max_scroll - 1` tolerance.
- **Notes for sibling tasks:** The `viewport_info` property returns a formatted string for debugging. `_viewport_content_height()` returns the rendered row count including indicators. During mouse drag, the viewport is completely frozen — this is a deliberate design choice to prevent content jumping. The edge scroll timer (`_edge_scroll_timer`) must be stopped on mouse release AND on any stop of drag.
