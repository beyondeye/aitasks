---
priority: medium
effort: low
depends: []
issue_type: bug
status: Done
labels: [aitask_board, aitasks]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-09 10:37
updated_at: 2026-02-10 10:08
completed_at: 2026-02-10 10:08
boardcol: now
boardidx: 20
---

in aitask_board python script, when we select in the board a task and enter in the detail screen for the possible statuses of task, that can be change using the left and right arrow, there is the In Progress status that does not exists (it is called Implementing instead) please check the aitask_update.sh bash script for the actually valid values for the status field: check the whole script code, not only the help text, by the way verify that the aitask_update script behavior and its help matches
