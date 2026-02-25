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

### 3. Modify `_rebuild_display()` for viewport
- Only build rows for `[viewport_start, viewport_start + viewport_size]`
- Adjust line numbers to real file positions
- Show `... (N lines above/below)` indicators

### 4. Modify `move_cursor()` for viewport
- Shift viewport when cursor exits bounds
- Move by half-page, not full re-center

### 5. Add line cache
- `_line_cache: dict[int, Text]` for syntax-highlighted lines
- Invalidate on file load or annotation change only

### 6. Update info bar
- Show "Lines X-Y of Z (viewport)" in viewport mode

## Verification
- Large files (2900+ lines) activate viewport
- Cursor navigation remains smooth (<50ms render)
- Small files render fully (no viewport)
- Line numbers correct in viewport mode
