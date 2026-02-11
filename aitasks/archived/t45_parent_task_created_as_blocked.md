---
priority: medium
effort: low
depends: []
issue_type: bug
status: Done
labels: [claudeskills, aitasks]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-05 11:22
updated_at: 2026-02-05 11:29
completed_at: 2026-02-05 11:29
---

Currently the aitask-pick skill when decomposing a prent task to child task will set the parent task as Blocked (by children) for example see task t40. the problem is that a blocked task will be filtered out by the initial task selection procedure using the aitask_ls script. The user can still select the task maanually. can you check why this happens, previously when creating child tasks the aitask-pick skill did not set the parent to the blocked status
