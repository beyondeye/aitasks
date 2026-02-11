---
priority: medium
effort: low
depends: []
issue_type: feature
status: Done
labels: [aitasks, claudeskills]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-10 10:05
updated_at: 2026-02-10 10:15
completed_at: 2026-02-10 10:15
---

In the claude skill aitask-pick when we call the skill with an explicit argument that is the task number, currently we don't show the task detail until showing to the user to proposed implementation plan. in the immediate beginning of the aitask-pick workflow, if we picked a task by number, create a very brief summary of the task description and use AskUserQuestion if this is the correct choice or abort if this is the wrong task
