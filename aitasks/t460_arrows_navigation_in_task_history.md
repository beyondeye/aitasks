---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [codebrowser]
created_at: 2026-03-25 08:44
updated_at: 2026-03-25 08:44
---

in Task History Screen in ait codebrowser tui, we have two main panes. the left is the task list that we can "navigate" with up/dwon arrows. and the right pane that is the task/plan file that also allow for navigation of focusable fields with up/down arrow (pleas verify). we want to introduce also keybinding for left/right arrow to move focus selections between the two panes. that is. if one task in history list is currently focused and we press right, we move focus to first focusable field in right pane. and if a field in the right pane is focused and we press left we move focus the current opened task in the task list (if it is visible, if note focus the first current visible task in the task list). also we want to review which field can focusable in task/plan metadata in the right pane: only fields that have an "enter" action should be focusable, not purely static fields
