---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [aitasks, claudeskills, aitasks_explore]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-16 13:42
updated_at: 2026-02-16 14:28
boardcol: now
boardidx: 10
---

I have just run a aitasks_explore for documentation and succesfully createad and run the t133 tasks. the problem is that during the exploration phase claude code also read existing documentation gaps (partially not all actually) from the pending aitasks with type:docuentation and "partially" integrated those tasks. there are two issues with this behavior: 1)the exisitng documentation tasks were kept while there were actually integrated in the new t133 tasks, so afterh t133 implementation the included tasks are still present and not considered as done. 2) checking for existing aitasks related to the current exploration is actually a good idea, but there should be a more stuctured and controlled way to include/merge existing tasks with the current exploration. existing tasks related to the current exploration should be reported but user should give approval for merging any of them with the new tasks created, and if this is done explicit mention in the new task should be of the merging and explicit instreuction to archive the merged tasks as implemented IF THE NEW task with merged tasks IS IMPLEMENTED. So the merged tasks are kept unmodified, BUT new tasks that merge the old tasks should have instructions about handling the old tasks if the merged tasks is actually implemented, and also have references to the old tasks in the implementation plan and instruction to check if the original tasks has already implemented because this could change the implementation plan (actual this check should be done in the planning phase) also if we start implementing the merged task we should also set the status as implementing also for the included tasks. but this will cause the abort procedure for a task to be much more complicated so perhaps avoid to do this.
