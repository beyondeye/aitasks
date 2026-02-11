---
Task: t56_opening_dependency_from_task_dtail_screen.md
Branch: main (working on current branch)
---

# Plan: Open Dependency from Task Detail Screen (t56)

## Context

In the aitask_board Python TUI, the task detail modal shows a "Depends:" line as a ReadOnlyField.
Pressing Enter on it should open the detail screen for the referenced dependency task.
Also fix Escape key not closing modals.

## Steps

- [x] 1. Create `DependsField` widget — focusable field for depends, Enter opens dep
- [x] 2. Create `DependencyPickerScreen` — modal for selecting among multiple deps
- [x] 3. Create `DepPickerItem` — focusable selectable item in the picker
- [x] 4. Add CSS for picker dialog
- [x] 5. Modify `TaskDetailScreen` to accept `manager` param, use `DependsField`
- [x] 6. Update all `TaskDetailScreen` instantiation sites
- [x] 7. Fix Escape key: `action_focus_board` should dismiss modal if active
