---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [task_workflow]
created_at: 2026-03-23 12:26
updated_at: 2026-03-23 12:26
---

at the end of the task workflow we update the plan with deviations and implementaiton details and finaally commit it before archiving the completed task. there is an issue with claude code that it keep the plan in its internal plan files and when it gets to the step where it need to write the plan in aiaplan before comit and archival, it does not find it: see associated claude code run log

Good. Now let me proceed to Step 8: User Review and Approval.

this is a currently a claude specific issue, so I am not sure how to handle this in away that is compatible with calude code, perhaps add claude code specifiic instructior in task-workflow to check if it is currently working with an internal plan file that was not exernalized yet, also I am asking myself, if claude code started working with a task that already has a plan (like child tasks) that claude code has verified and then started working on the task, does claude code internalize the plan and then perhaps when asked to update the plan with final impleentation details, do claude code update which plan? the internal plan or the externalized plan in aiplans? from my experience it seems to me that claude correctly work with then internal plan all the way during implementaiton and the externalize with all changes to the final aiplan. anyway when we get to final step of writing to the "external" plan files very frequeently we fail. so we must claude code specific instruction in the proper place of the workflow that if we are currently working with an internal plan file, need to copy first to the externalized file
