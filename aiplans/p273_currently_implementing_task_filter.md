---
Task: t273_currently_implementing_task_filter.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: Add View Mode Filter to ait board (t273)

## Context

The ait board TUI currently only has a search bar for filtering tasks (substring match on filename + metadata). Users need a way to quickly see tasks that are currently being implemented. This task adds a unified view mode selector (All / Git / Implementing) on the same line as the search bar, with keyboard shortcuts to toggle between views. The "Implementing" view is the primary focus — it shows tasks with status "Implementing" and, for implementing child tasks, also shows the parent and all sibling tasks for context.

The Git view (from t260_8) is included here as a simple filter (tasks with `issue` or `pull_request` metadata).

## File to Modify

- `aiscripts/board/aitask_board.py` (~3345 lines)

## Implementation Steps

### 1. Add ViewSelector widget class
### 2. Add CSS for top bar layout
### 3. Modify compose() layout
### 4. Add view mode state to __init__()
### 5. Add keybindings
### 6. Implement view mode action methods
### 7. Extend apply_filter()
### 8. Implement filter set computation methods
### 9. Handle view mode in action_refresh_board()

## Verification

1. Run `./ait board` and verify the view selector appears on the same line as the search bar
2. Press `a`, `g`, `i` to switch views — active view should highlight
3. In implementing view: only tasks with status=Implementing and their parent/siblings should show
4. In git view: only tasks with issue/pull_request metadata should show
5. Search filter works in combination with view mode (intersection)
6. Switching to implementing view auto-expands parents with implementing children
7. Switching back to "All" collapses the auto-expanded parents
8. Board refresh (`r`) preserves the current view mode
9. Clicking on view labels switches the active view mode
10. "Task filter" title label appears above the view selector row

## Post-Review Changes

### Change Request 1 (2026-03-02)
- **Requested by user:** Make view labels clickable by mouse, add a "Task filter" title line above the filter selector
- **Changes made:** Added `on_click` handler to ViewSelector that maps click x-position to view modes. Added `Static("Task filter")` label with `#view_label` CSS above the top_bar. Added CSS rule for `#view_label`.
- **Files affected:** `aiscripts/board/aitask_board.py`

### Change Request 2 (2026-03-02)
- **Requested by user:** Position "Task filter" label aligned with search box top, with All/Git/Impl below it, both on the left side
- **Changes made:** Restructured layout to use a `Horizontal#filter_area` containing a `Container#view_col` (label + view selector stacked vertically) and the `Input` search box side by side. Used fixed width (26) for the view column.
- **Files affected:** `aiscripts/board/aitask_board.py`

## Final Implementation Notes
- **Actual work done:** Added ViewSelector widget with clickable mode buttons, view mode state management (all/git/implementing), keyboard shortcuts (a/g/i), extended apply_filter() with view-mode-aware filtering, implementing view auto-expansion of parent tasks, git view for issue/PR-linked tasks
- **Deviations from plan:** Layout went through several iterations to match user's desired positioning — final layout uses nested Horizontal > Container + Input structure instead of the originally planned simple Horizontal
- **Issues encountered:** CSS `dock: top` ordering caused visibility issues with the label; `width: auto` on Container inside Horizontal didn't constrain properly (Input's `1fr` consumed all space) — fixed with fixed width of 26 chars
- **Key decisions:** Click handling on ViewSelector uses x-position zone mapping (divides into three zones based on character positions); view mode keybindings are show=False since the ViewSelector widget already displays the shortcuts
