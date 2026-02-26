---
Task: t195_8_code_viewer_rendering_hardening.md
Parent Task: aitasks/t195_python_codebrowser.md
Sibling Tasks: aitasks/t195/t195_5_*.md
Archived Sibling Plans: aiplans/archived/p195/p195_*_*.md
Branch: main
Base branch: main
---

# Plan: t195_8 — Code Viewer Rendering Hardening

## Steps

### 1. Binary file detection
- In `load_file()`: try `read_text()`, catch `UnicodeDecodeError`
- Or use `file -b --mime-encoding` subprocess
- Show "Binary file — cannot display" message

### 2. Tab normalization
- `expandtabs(4)` on each line before rendering

### 3. Long line handling
- `no_wrap=True` on code column
- Truncate lines exceeding max_width with `...` via `Rich.Text.truncate()`

### 4. Empty file handling
- 0 lines → show "(empty file)" static message

### 5. Unicode/emoji handling
- Test with wide characters
- Ensure Rich Table column alignment accounts for character width

### 6. CSS overflow
- Add `overflow: hidden` on code display widget

## Post-Review Changes

### Change Request 1 (2026-02-26)
- **Requested by user:** Mouse drag selection broken — selection jumps to wrong position when selecting outside the initial visible range, getting worse the further down the file
- **Changes made:** Fixed mouse coordinate handling in `on_mouse_down` and `on_mouse_move`. The root cause was a coordinate system mismatch: before `capture_mouse()`, Textual provides `event.y` in content coordinates (includes scroll offset), but after `capture_mouse()`, `event.y` is in viewport coordinates (relative to widget's visible area). The original code used `scroll_y + event.y` for both, which double-counted when the user had scrolled. Fixed by: using `event.y` alone in `on_mouse_down`, and `scroll_y + event.y` in `on_mouse_move` with cursor-relative edge scrolling (±1) to prevent a feedback loop with `_scroll_cursor_visible()`.
- **Files affected:** `aiscripts/codebrowser/code_viewer.py` (mouse handlers)

## Verification
- Binary files → "Binary file" message
- Long lines → truncated, no layout break
- Tabs → consistent spaces
- Empty files → "(empty file)"
- Unicode/emoji → no crash
- Mouse selection works correctly at any scroll position

## Final Implementation Notes
- **Actual work done:** All 5 planned hardening steps implemented plus a mouse selection coordinate bug fix discovered during testing. Added binary file detection (UnicodeDecodeError catch + null byte check), empty file handling ("(empty file)"), tab normalization (expandtabs(4)), long line truncation (>500 chars with `…`), CSS overflow-x:hidden. Fixed pre-existing mouse drag selection bug caused by coordinate system mismatch between captured and non-captured mouse events.
- **Deviations from plan:** (1) Used Python-native UnicodeDecodeError + null byte check for binary detection instead of `file -b --mime-encoding` subprocess — simpler, no external dependency. (2) Applied `expandtabs()` to the entire content string before splitting, not per-line — same result, cleaner. (3) Added `_reset_state()` and `_show_message()` helper methods to avoid code duplication across binary/empty/error early returns. (4) Mouse selection fix was not in the original plan but was discovered and fixed during user testing.
- **Issues encountered:** Mouse drag selection had a pre-existing coordinate system bug: Textual's VerticalScroll uses content coordinates for normal mouse events but viewport coordinates after `capture_mouse()`. The original code (from t250) used `scroll_y + event.y` for both handlers, which worked only when scroll_y=0. Fix required using different coordinate strategies for `on_mouse_down` (content coords) vs `on_mouse_move` (viewport coords with cursor-relative edge scrolling).
- **Key decisions:** `MAX_LINE_WIDTH = 500` as class constant for truncation threshold. Uses `line.copy()` before `truncate()` to avoid mutating the stored `_highlighted_lines` list.
- **Notes for sibling tasks:** The `_show_message()` helper can be reused for any non-code display state (e.g., "Loading..." for t195_9 viewport windowing). The mouse coordinate fix is important context — Textual's `capture_mouse()` changes the coordinate system for subsequent mouse events. The `_reset_state()` helper centralizes state cleanup for file loading.
