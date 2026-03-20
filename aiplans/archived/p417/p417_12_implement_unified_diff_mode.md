---
Task: t417_12_implement_unified_diff_mode.md
Parent Task: aitasks/t417_diff_viewer_tui_for_brainstorming.md
Sibling Tasks: aitasks/t417/t417_11_*.md
Archived Sibling Plans: aiplans/archived/p417/p417_*_*.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: Implement Unified Diff Mode (t417_12)

## Context

The DiffViewerScreen has a `u` keybinding that toggles `_unified_mode`, but both code paths in `_load_current_view()` call the same `load_multi_diff(result, active_idx)` — making it a no-op. The unified mode should show all comparisons simultaneously on one scrollable screen, annotated with plan gutter letters (A, B, C...), eliminating the need for n/p navigation between comparisons.

## Files Modified

- `.aitask-scripts/diffviewer/diff_display.py` — Core changes: new field, new flattener, new load method, renderer updates
- `.aitask-scripts/diffviewer/diff_viewer_screen.py` — Wire unified mode, disable SBS in unified, section-jump navigation
- `tests/test_diff_display.py` — Tests for unified flattener

## Implementation Steps

### 1. Added `comparison_idx` field to `_DisplayLine`

New field `comparison_idx: int = -1` — when >= 0, the renderer uses this per-line index for gutter letter assignment instead of the global `_active_comparison_idx`.

### 2. Added `_flatten_unified()` module function

Concatenates all comparisons' diff hunks into one flat list. Per comparison:
1. Separator line (dim horizontal rule) between sections
2. Header line with plan letter and filename (colored)
3. Flattened hunks via existing `_flatten_hunks()` with context folding (3 lines before/after changes)
4. Fold indicators for skipped equal sections
5. All lines tagged with `comparison_idx`

Special tags: `"separator"`, `"header"`, `"fold"`.

### 3. Added `load_unified_diff()` method to `DiffDisplay`

Sets `_unified = True`, populates `_flat_lines` from `_flatten_unified()`, clears `_sbs_lines`.

### 4. Updated `_render_interleaved()` for unified mode

- Handles `separator`, `header`, `fold` tags with styled full-width content
- Uses `dl.comparison_idx` (when >= 0) instead of global `self._active_comparison_idx` for gutter letters

### 5. Updated `DiffViewerScreen`

- `_load_current_view()`: calls `load_unified_diff(result)` when unified mode active
- `action_toggle_layout()`: blocks SBS in unified mode with notification
- `action_next/prev_comparison()`: jumps between section headers in unified mode via `_jump_to_section()`

### 6. Added tests

4 tests in `TestFlattenUnified`: basic two-comparison, no-changes placeholder, context folding, comparison_idx assignment.

## Verification

- Run: `python -m unittest tests.test_diff_display -v` — 68 tests pass

## Final Implementation Notes

- **Actual work done:** Implemented unified diff mode with concatenated per-comparison sections. Each section has a colored header, context-folded hunks, and per-line comparison indices for correct gutter letter assignment. Added n/p section-jump navigation and SBS guard in unified mode.
- **Deviations from plan:** None — implementation followed the plan exactly.
- **Issues encountered:** None.
- **Key decisions:** Used concatenated section approach (each comparison shown back-to-back with context folding) rather than true N-way merge — this is clearer and more practical for brainstorming workflows where you want to see each plan's differences distinctly. Added `_unified` flag to DiffDisplay to track mode state across load/render cycles.
- **Notes for sibling tasks:** `DiffDisplay` now has `load_unified_diff(result)` as a new public API. The `_DisplayLine` dataclass has a new `comparison_idx` field. Three new tag types (`separator`, `header`, `fold`) are handled in `_render_interleaved()` — if sibling tasks modify the renderer they should preserve this handling.

## Post-Implementation

Step 9 of the task-workflow: archive task, push changes.
