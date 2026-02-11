---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Done
labels: [claudeskills, aitasks]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-09 08:39
updated_at: 2026-02-10 10:00
completed_at: 2026-02-10 10:00
boardcol: now
boardidx: 10
---

currently the aitask-pick skill, when completing a child task will archive their associated task and aiplan. But for maintaing context for execution of remaining child tasks it is important to keeep a link the executed child tasks, so we need to check if the aitask-pick skill correctly specify that at the phase where we gather context for task execution, we are able to correcly reference all sibling tasks and execution plan even for already completed child tasks so we must specify in the workflow to search for sibling tasks and task plan in the archived in the corresponding archived directory, for example for parent task t10, search in the path aiplans/archived/t10 and aitasks/archived/t10 for the executed sibling tasks and plan. it also important for the same reason that when each task complete execution it updates their final execution plan with all the actual work that was done, the issues found and they were resolved, so that the information can be passed on to sibling tasks where they will be executed in turns
