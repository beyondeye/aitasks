---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Done
labels: [task_workflow]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-23 11:23
updated_at: 2026-03-23 12:14
completed_at: 2026-03-23 12:14
---

when running the task-workflow.md, in the step when we push updates to the task-data branch (for the updated plans/tasks, archived status, and so on) we almost get conflicts at the first attempts. this is expected as there are most of the time multiple users pushing updated to the task-data branch. show here an excerpt of th calude code run log as an example: ● Step 9: Post-Implementation — No separate branch, so skipping merge. Verifying plan completeness for child task — done (Final Implementation Notes

this error happen almost always. claude code recover from the error almost immediately but this is visual notse and should be handled better since this is not an exception, it happens almost always. I am not sure how best handle it: define proper instructions for claude to check if rebase is needed first. but this will require multiple steps in claude code. perhaps this should be refactored to a common bash script white-listed, that handle ./ait git push with rebase if needed, and output error if some real merge conflict need to be resolved
