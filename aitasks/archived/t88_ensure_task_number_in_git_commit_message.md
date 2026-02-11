---
priority: medium
effort: low
depends: []
issue_type: feature
status: Done
labels: [claudeskills, aitasks]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-11 10:46
updated_at: 2026-02-11 11:26
completed_at: 2026-02-11 11:26
---

in the aitask-pick skill when we commit the code changes associated with a task execution we should add in the commit message the text "(t<task_id>)". there should explicit instructions in skill workflow for this. note only commits with prject source changes should contains this label, not commits when the aitask files or aiplans files are modified. the reason for this requirement is that the aitask_issue_update bash script that update a github issue after the implementaiton of the associated aitask, will search for commits associated to the aitask to reference them in the comment that is added to the github issue. please also verify that the aitask_issue_update use the actual pattern I specified "t<task_id>" to search for commits associated to the task. ask me questions if you need clarifications
