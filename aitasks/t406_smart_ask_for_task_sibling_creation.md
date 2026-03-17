---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [testing, task_workflow]
created_at: 2026-03-17 10:45
updated_at: 2026-03-17 10:45
---

we have the test-followup-task.md procedure in task-workflow to ask the user if he wants to create a follow-up task for tests. we always ask the questions even if tests where already created in the current tasks. I would like to change the workflow to skip this questions if automated tests, or in general tests were already created in the current task. add the new instructions in the procedure itself, not at the calling site
