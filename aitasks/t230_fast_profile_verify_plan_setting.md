---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [aitask_pick]
created_at: 2026-02-24 09:39
updated_at: 2026-02-24 09:39
boardcol: next
boardidx: 80
---

currently the fast exection profile for aitask-pick has the setting that if an existing plan is found for a task, the plan should be verified. need to think if this is the correct settings: probably yes: fast means less interactive questions, on the other hand this makes implementation slower. so perhaps this question (verify plan or not) should be left as INTERACTIVE QUESTION for the fast profile, while for the remote profile it should be set to verify
