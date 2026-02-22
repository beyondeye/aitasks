---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [aitask_wrap, claudeskills]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-22 18:12
updated_at: 2026-02-22 18:15
---

currently in the aitask_wrap skill we don't check if there is an existing claude plan that has been just executed. we should cross check for such plan as it is useful information that can be included in the task definition from changes, in case we find sudh plan we should ask user if we want to use it or not (perhaps it is not actually relevant to current file changes)
