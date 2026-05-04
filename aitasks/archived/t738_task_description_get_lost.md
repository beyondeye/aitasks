---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Done
labels: [aitask_monitor, aitask_monitormini]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-05-04 15:56
updated_at: 2026-05-04 16:25
completed_at: 2026-05-04 16:25
---

in both ait monitor and ait minimonitor, we show codeagent information by scanning the associated task number and fetching the task type and information. there is "bug" in that when the task completes and it is archived, the task information is not shown anymore in monitor and minimonitor because task data get archived and the monitor and minimonitor don't find it anymore and at the next refresh the task information is "removed" because not found anumore. this should be avoided: once a codeagent has been succesfully associated witha  task there is no reason to remove this association later if the task data get moved or removed. or at least we should be able to find this information even later if it gets archived
