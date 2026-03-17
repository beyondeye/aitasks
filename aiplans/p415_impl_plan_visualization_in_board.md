---
Task: t415_impl_plan_visualization_in_board.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

The TUI board (`ait board`) shows task details in a modal screen (`TaskDetailScreen`) with metadata fields and a Markdown widget rendering the task file content. Currently there's no way to view or edit the associated implementation plan file (`aiplans/p<N>_*.md`). Users must leave the board to check plans. This task adds a toggle between task file and plan file views, with the edit action context-aware.

## Implementation Plan

### Key files to modify
- `.aitask-scripts/board/aitask_board.py` — All changes are in this single file

### Step 1: Add plan file resolution method to `TaskDetailScreen`

Add `_resolve_plan_path()` returning the plan file `Path` (or `None`). Reuses logic from `_collect_delete_files`.

### Step 2: Add state tracking to `TaskDetailScreen.__init__`

- `self._showing_plan = False` — tracks which view is active
- `self._plan_path = None` — resolved plan path

### Step 3: Add view indicator label and toggle button to `compose()`

- `#view_indicator` label between metadata and markdown view
- `#btn_view` toggle button in `detail_buttons_file` row
- `v`/`V` key binding → `action_toggle_view`

### Step 4: Implement the toggle action

Toggle between task/plan content in the Markdown widget. Update indicator text, button label, and `#md_view` border color (orange `#FFB86C` for plan view).

### Step 5: Make edit action context-aware

- `edit_task()` returns `"edit_plan"` when `_showing_plan` is True
- `check_edit` callback handles `"edit_plan"` via `_resolve_plan_path_for()` helper on `KanbanApp`

### Step 6: Add CSS for the view indicator

`#view_indicator` style added to app CSS.

### Step 9: Post-Implementation
Archive task, commit, push per workflow.

## Final Implementation Notes

- **Actual work done:** Added plan file toggle to TUI board detail screen. All changes in `aitask_board.py` (78 lines added). Includes: `_resolve_plan_path()` on `TaskDetailScreen`, `_resolve_plan_path_for()` on `KanbanApp`, view toggle with dynamic border color, context-aware edit action, `#view_indicator` CSS.
- **Deviations from plan:** Added dynamic border color change on `#md_view` (orange when viewing plan) per user request — not in original plan. Initial `set_styles()` approach crashed because Textual's `set_styles()` doesn't resolve CSS variables at runtime; fixed by using `styles.border = None` to reset to CSS default.
- **Issues encountered:** `set_styles("border: solid $secondary-background;")` raised `DeclarationError` — CSS variable tokens aren't supported in inline style parsing. Resolved by setting `styles.border = None` which removes the inline override and lets the CSS rule take effect.
- **Key decisions:** Plan file frontmatter is stripped before display. Toggle button placed as first button in `detail_buttons_file` row. Used `("solid", "#FFB86C")` tuple for inline border style (plan view) since Textual's `styles.border` accepts color tuples directly.
