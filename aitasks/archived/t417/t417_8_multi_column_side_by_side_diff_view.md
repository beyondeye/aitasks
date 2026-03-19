---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Done
labels: [tui, brainstorming]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-19 07:28
updated_at: 2026-03-19 09:52
completed_at: 2026-03-19 09:52
---

## Context

The current DiffViewerScreen (t417_6) shows diffs in a single interleaved view — both files' lines are mixed together with color coding. While functional, this makes it hard to visually compare the two plans side by side. This task adds a multi-column side-by-side diff view where each file gets its own column.

## Key Files to Modify

- `.aitask-scripts/diffviewer/diff_display.py` — Add a side-by-side rendering mode alongside the current interleaved mode
- `.aitask-scripts/diffviewer/diff_viewer_screen.py` — Add a keybinding to toggle between interleaved and side-by-side views
- `.aitask-scripts/diffviewer/diffviewer_app.py` — Add CSS for multi-column layout

## Reference Files for Patterns

- `.aitask-scripts/diffviewer/diff_display.py` — Current `_render_diff()` method using Rich Table
- `.aitask-scripts/diffviewer/diff_viewer_screen.py` — Current bindings and mode toggle pattern (e.g., `action_toggle_mode`)
- `.aitask-scripts/diffviewer/plan_manager_screen.py` — Horizontal layout pattern with percentage widths

## Implementation Plan

1. Add a side-by-side rendering method to `DiffDisplay`:
   - Create `_render_side_by_side()` that builds a Rich Table with columns: main_lineno | main_content | gutter | other_lineno | other_content
   - Align matching lines horizontally — equal lines side by side, inserts show blank on main side, deletes show blank on other side
   - Apply the same TAG_STYLES color coding per side

2. Add a toggle in `DiffViewerScreen`:
   - New binding: `key_v` / `action_toggle_layout` — "Layout" — switches between interleaved and side-by-side
   - Track `_side_by_side: bool` state
   - Update info bar to show current layout mode

3. Update `DiffDisplay` API:
   - Add `set_layout(side_by_side: bool)` method
   - `_render_diff()` dispatches to `_render_side_by_side()` or the existing interleaved render based on layout

## Verification

- Launch diff viewer with two plans
- Press `v` to toggle between interleaved and side-by-side views
- In side-by-side: equal lines align horizontally, inserts/deletes show blank on opposite side
- Cursor navigation (up/down/pgup/pgdn) works in both layouts
- Mode switching (m) and comparison cycling (n/p) work in both layouts
- Window resize re-renders correctly in side-by-side mode
