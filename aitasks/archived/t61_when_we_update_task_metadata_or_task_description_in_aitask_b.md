---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Done
labels: [aitask_board, aitasks]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-08 18:39
updated_at: 2026-02-09 22:22
completed_at: 2026-02-09 22:22
boardcol: now
boardidx: 50
---

when we update task metadata or task description in aitask_board, thre should be an option to show in the aitask box display with an asterisk, if the task is modified (vs the git repo) and add a keybord shortcut to commit changes to a sige selected task or for all changed tasks, at the same time making sure not to overwrite changes made by claude code to status of tasks. the updated_at metadata field should also be updated when we write new task metadata from the aitask_board app. need check if this is actually what happens in all places where we write updated task metadata from the aitask_board python app
