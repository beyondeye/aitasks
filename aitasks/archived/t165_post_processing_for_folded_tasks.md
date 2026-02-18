---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Done
labels: [aitask_pick]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-18 08:12
updated_at: 2026-02-18 11:01
completed_at: 2026-02-18 11:01
---

currently folded tasks are simply deleted in the post implementation step of the task-workflow claude skill. But if a folded task has a linked issue metadata field, then we should trigger the workflow of closed issue after implementation. currently this is done only for the main task being implemented, not its folded tasks. need to restructure the workflow to handle this
