---
priority: medium
effort: medium
depends: []
issue_type: performance
status: Ready
labels: [claudeskills, task_workflow]
created_at: 2026-02-19 08:02
updated_at: 2026-02-19 08:02
---

I want to refactor in step 4 of the task-workflow skill all the step for locking a task, and changing task metadata to assigned plus commit and push, that is all operation that are basically shell operation to a single aitask_own.sh script, for faster execution and avoiding to add to the llm context things that are not actually related to task implementation
