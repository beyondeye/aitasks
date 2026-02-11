---
Task: t55_child_tasks_support_in_board.md
Branch: main
Base branch: main
---

# Plan: Add Child Task Support to aitask_board TUI

## Context

The aitask_board TUI currently only loads parent tasks from `aitasks/*.md` and shows `children_to_implement` as a read-only text field. Child tasks (stored in `aitasks/t{N}/t{N}_{M}_*.md`) are invisible to the board. This plan adds:
- Child count badges on parent task cards ("child 4/7")
- Interactive navigation from parent -> child task details
- A "Parent" field on child task details to navigate back
- Proper child task loading in TaskManager

All changes are in a single file: `/home/ddt/Work/tubetime/aitask_board/aitask_board.py`

## Implementation Steps

### 1. Fix `_parse_filename` for child task filenames
Modify `TaskCard._parse_filename` to try child pattern `^(t\d+_\d+)_(.+)$` first, then fall back to parent pattern.

### 2. Extend TaskManager with child task support
- Add `child_task_datas` dict, `load_child_tasks()`, `find_task_by_id()`, `get_child_tasks_for_parent()`, `get_parent_num_for_child()`

### 3. Add child count badge to TaskCard
- Pass manager to TaskCard, show child pending/total count

### 4. Create ChildrenField widget (interactive, similar to DependsField)

### 5. Create ChildPickerScreen and ChildPickerItem

### 6. Create ParentField widget

### 7. Update TaskDetailScreen.compose() to use ChildrenField and ParentField

### 8. Fix DependsField._find_task_by_number for child deps

### 9. Add CSS for new widgets
