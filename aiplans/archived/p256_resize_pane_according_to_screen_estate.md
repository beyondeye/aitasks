---
Task: t256_resize_pane_according_to_screen_estate.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan: Responsive Codebrowser Layout (t256)

## Context

The codebrowser TUI (`aiscripts/codebrowser/`) has fixed-width layout elements that cause the annotation column to be invisible on smaller screens. The annotation gutter (12 chars, column 3 of a Rich Table) gets pushed off-screen by long code lines because:
- Code column (column 2) has `no_wrap=True` and no width constraint, expanding to content width
- `#code_display` has `overflow-x: hidden`, clipping the annotation column
- File tree is fixed at 35 chars regardless of terminal width
- Annotation column space is always allocated even when annotations are toggled off

## Changes

### 1. Dynamic code column width in `_rebuild_display()` (code_viewer.py)

Calculate available width for code and truncate lines accordingly:

```python
available = self.size.width if self.size.width > 0 else 120
LINE_NUM_WIDTH = 5
show_ann = self._show_annotations and self._annotations
ann_width = (12 if available >= 80 else 10) if show_ann else 0
code_max_width = max(20, available - LINE_NUM_WIDTH - ann_width - 2)
```

- Set `width=code_max_width` on column 2 (explicit width so code column claims the space, not annotation)
- When annotations hidden: set annotation column `width=0` (saves 12 chars for code)
- Update existing truncation to use `min(MAX_LINE_WIDTH, code_max_width)`
- Floor of 20 chars for code to remain usable on very narrow terminals

### 2. Responsive file tree width via `on_resize()` (codebrowser_app.py)

Add `on_resize` handler to adjust tree width based on terminal width:

| Terminal Width | Tree Width |
|---------------|------------|
| >= 120        | 35         |
| 80-119        | 28         |
| < 80          | 22         |

### 3. CodeViewer `on_resize()` handler (code_viewer.py)

Add `on_resize` to trigger `_rebuild_display()` when widget size changes, so column widths recalculate dynamically on terminal resize.

## Files to Modify

- **`aiscripts/codebrowser/code_viewer.py`** — Primary: dynamic column width calc, annotation col width helper, `on_resize`, truncation update
- **`aiscripts/codebrowser/codebrowser_app.py`** — Secondary: `on_resize` for tree width

## Verification

1. Run `cd aiscripts/codebrowser && python codebrowser_app.py` in a normal-width terminal (~120+ cols) — verify no visual regression, annotation column visible when toggled on
2. Resize terminal to ~80 columns — verify tree shrinks and annotation column remains visible
3. Toggle annotations off with `t` — verify code column expands to use freed space
4. Test with a file containing very long lines — verify truncation with ellipsis and annotation column stays visible
5. Test viewport mode with a large file (>2000 lines) — verify no regressions

## Final Implementation Notes

- **Actual work done:** Implemented dynamic column width calculation in `_rebuild_display()`, responsive file tree width via `on_resize()`, and a `CodeViewer.on_resize()` handler. All three columns (line numbers, code, annotations) now have explicit widths computed from available space.
- **Deviations from plan:** Initially used `max_width` on column 2 (code), but during review discovered this caused extra space to be absorbed by the annotation column on wide terminals. Changed to explicit `width` so the code column claims the space.
- **Issues encountered:** Rich Table distributes unclaimed space to columns without explicit width. Using `width=` (fixed) instead of `max_width=` (cap) on the code column resolved this.
- **Key decisions:** Code column gets priority for available space. Annotation column is fixed at 12 chars (10 on narrow terminals). File tree adapts at breakpoints 120/80.

## Post-Review Changes

### Change Request 1 (2026-02-26 12:00)
- **Requested by user:** Fix annotation column absorbing extra space on wide terminals. Also update t251 with responsive layout integration notes.
- **Changes made:** Changed code column from `max_width=code_max_width` to `width=code_max_width`. Updated t251 with dependency on t256 and detailed notes about width distribution priority (code column gets 80+ chars first, then remaining goes to future detail pane).
- **Files affected:** `aiscripts/codebrowser/code_viewer.py`, `aitasks/t251_allow_viewing_details_of_tasks_that_originated_changes.md`

## Post-Implementation

See Step 9 (Post-Implementation) in task-workflow for cleanup, archival, and merge steps.
