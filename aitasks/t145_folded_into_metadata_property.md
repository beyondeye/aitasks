---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [aitask_fold, aitask_board, scripting]
created_at: 2026-02-17 10:29
updated_at: 2026-02-17 10:29
---

when a aitask is folded into another tasks a metadata property folded_tasks is added to the aitask where other tasks are folded in. but no metadata or status change is done the folded tasks: introduce an new task status: folded (in addition ti implementing/ready etc.) to identify folded tasks: tasks with such status must be opened as read-only in task details in the aitask python board. add also a metadata property folded_into to front matter of folded tasks with the number of the tasks into which the task was folded. add support in ait board parse and show the new folded_into property and allow when pressing enter in the task detail screen to navigate to the folded_into task. need also update the aitask_update shell script to support the new task status Folded, and the new metadata property folded_into. need to update claude skills aitask_explore and aitask_fold skills that support folding to update the folded tasks status to Folded and add to them the folded_into property. we can all of this with a single call to aitask_update shell script. this is a complex tasks, so it is probably better to split it into child tasks
