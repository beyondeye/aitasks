---
priority: medium
effort: medium
depends: [t417_3]
issue_type: feature
status: Done
labels: [tui, brainstorming]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-18 12:22
updated_at: 2026-03-18 16:01
completed_at: 2026-03-18 16:01
---

## Context

This task creates the Textual widget that visually renders diffs with color coding, line numbers, and keyboard navigation. It's the core visual component of the diff viewer TUI. The widget follows the `CodeViewer` pattern from the codebrowser TUI — a `VerticalScroll` subclass that renders Rich Tables for efficient display of large diffs.

## Key Files to Create

- `.aitask-scripts/diffviewer/diff_display.py` — The DiffDisplay widget

## Reference Files for Patterns

- `.aitask-scripts/codebrowser/code_viewer.py` — Primary pattern: VerticalScroll + Rich Table rendering, cursor tracking, viewport windowing (~577 LOC). Follow this structure closely for consistency.
- `.aitask-scripts/board/aitask_board.py` — CSS patterns, color palette (PALETTE_COLORS), Static widget patterns
- `.aitask-scripts/diffviewer/diff_engine.py` (from t417_2) — DiffHunk, PairwiseDiff, MultiDiffResult data classes

## Implementation Plan

1. Create `diff_display.py` with `DiffDisplay(VerticalScroll)` class:
   - Follow `CodeViewer.__init__` pattern: store diff data, initialize cursor state
   - Instance variables: `_diff: PairwiseDiff | None`, `_multi_diff: MultiDiffResult | None`, `_cursor_line: int`, `_active_comparison_idx: int`

2. Implement rendering with Rich:
   - `_render_diff()` method that builds a Rich Table
   - Columns: line-num-main (right-aligned, dim), line-num-other (right-aligned, dim), gutter (1 char wide), content (full width)
   - Color scheme using Rich styles:
     - `equal`: default/dim text
     - `insert`: green background (`on green`)
     - `delete`: red background (`on red`)
     - `replace`: yellow background (`on dark_goldenrod`)
     - `moved`: blue/cyan background (`on dark_cyan`) — structural mode only
   - Gutter indicators: `+` for insert, `-` for delete, `~` for replace, `>` for moved, ` ` for equal
   - For multi-diff overlay: gutter shows colored plan identifier letter (A, B, C...) using distinct colors per comparison plan

3. Implement `load_diff(diff: PairwiseDiff)`:
   - Store the diff, build flattened line list from hunks for cursor navigation
   - Call `_render_diff()` and mount the Rich renderable

4. Implement `load_multi_diff(result: MultiDiffResult, active_idx: int = 0)`:
   - Store multi-diff result
   - Default to showing the first pairwise comparison
   - Support switching active comparison via `set_active_comparison(idx)`

5. Implement keyboard navigation (same pattern as CodeViewer):
   - `key_up` / `key_down`: move cursor, scroll viewport if needed
   - `key_page_up` / `key_page_down`: jump by viewport height
   - `key_home` / `key_end`: jump to start/end
   - Post `CursorMoved(line)` message on cursor movement
   - Highlight current line with a subtle background color

6. Define `CursorMoved(Message)` class for parent widgets to react to cursor changes

## Verification

- Instantiate DiffDisplay, call `load_diff()` with a PairwiseDiff: widget renders without error
- Colors match: insert lines green, delete lines red, replace yellow, equal dim
- Line numbers shown correctly for both sides
- Keyboard navigation: cursor moves, viewport scrolls
- `load_multi_diff()`: gutter shows plan identifiers in distinct colors
- Empty diff (identical plans): displays "No differences found" message
- Large diff (100+ hunks): renders without performance issues
