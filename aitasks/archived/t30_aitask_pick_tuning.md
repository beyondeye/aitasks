---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Done
labels: [claudeskills, aitasks]
created_at: 2026-02-02 14:17
updated_at: 2026-02-02 14:30
completed_at: 2026-02-02 14:30
---

there is some fine tuning I want to do on the claude skill aaitask-pick in this repo. I want to make clear in the skill definition that when a parent task, because of its complexity is decomposed in children tasks. the children task definitions must contained detailed Context explaining why the task is needed, Context explaining why the task is neededm Key files to modifyReference files for patterns to follow Verification steps. All this information at the level of details that is currently in claude code context that caused the decision to define this specific child task. the assumption is that the children task will not be executed in the current claude code context so all information currently avaiable should be stored in the children task definition. so that we will be able to start any of the children task in a fresh context.

There is also a need to improve how competion of tasks is reported: currently the competion status is of a task is reported by adding some text that report the task completion inside the task definition with time and date of completion. Instead add a field completed_at field in the task frontmatter metadata that used the same time format as the other dateandtime fields there.

also make more clear that each time some aitask is updated need to update the dateandtime field in frontmatter metadata "updated_at"

also add a note that when adding children tasks the format for the names is t<parent-task-number>_<child-tasknumber>. It is not possible to insert a task [27;2;13~in-between", let's say between t10_1 and t10_2, insert task t10_1b, if you discover that you missed some implementation phase that is needed bettween t10_1 and t10_2: only use numbers for child subtasks identifier

Also the limit of top 5 tasks for picking the task to exectue is not enough: show top 10, and before doing all the processing that calculate priorities and select task ask the user he want to limit tasks with specific labels. The list of all labels is available in file
aitasks/metadata/labels.txt

you should also check if for implementing this new filtering features there is a need to update the aitask_ls.sh script
aitasks_ls.sh
