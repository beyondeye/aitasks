---
priority: medium
effort: medium
depends: []
issue_type: refactor
status: Implementing
labels: [workflows, codeagent, model_selection]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-22 15:05
updated_at: 2026-03-22 15:06
---

currently in the task_workflow (and perhaps also in other skills) we run twice the procedure to identify the codeage/model that is running the task: once at the beginning when we set the property implemented_with (or something similar) property and once for the feedback procedure. can we simplify this, that is if the the metadata about the current implementing agent is avaialable, avoiding querying once again the code agent?
