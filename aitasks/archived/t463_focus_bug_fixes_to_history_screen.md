---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Done
labels: [codebrowser]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-25 11:48
updated_at: 2026-03-25 12:10
completed_at: 2026-03-25 12:10
---

there are some focus issues in the ait codebrowser in the history screen: when in the task detail we select the top line to move back to previous viewed task, the general focus remain on the task detail pane, that is correct, but by pressing up and down arrows we cannot focus any field in there, only if we pres left arrow and then back right arrow, the focusable fields becaome selecteble with up and down arrows keys

an additional bug is that in the sibling screen there are not keyboard shortcuts (up/down errors + enter) to select a sibling. the behavior in the dialog and keybindings should be analogous to what now existing in the modal dialog for selectiong filtering of task by label in the same task history screen
