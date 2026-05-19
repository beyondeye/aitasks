---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Done
labels: [aitask-create, bash_scripts]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-19 12:08
updated_at: 2026-05-19 13:48
completed_at: 2026-05-19 13:48
---

in ait create bash script we currently can choose task dependencies for existing tasks with fzf search. but only for active tasks, not for archived tasks. sometimes we want to reference ARCHIVED tasks, not because they are dependency but because the work to be done in the new task need to refer what was done in a previous task. this is something similar on what happens for child tasks in task-workflow:  where we always get the full context of plans and tasks for completed sibling tasks. we want to extend this concept to add reference to other archived task not necessarily siblings and do it at the task creation stage. one possible options is that, like now that we can edit description sections intertwined we file references

we can extend the menu for adding file reference with an additional menu item: add archived task reference. and then an fzf menu that allow to search between archived task. the question is: should be able to search also in archived and zipped files? probably not for now.

ask me questions if you need clarifications
