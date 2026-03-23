---
priority: high
effort: high
depends: []
issue_type: bug
status: Ready
labels: [agentcrew, brainstorming]
created_at: 2026-03-23 11:56
updated_at: 2026-03-23 11:56
---

we have tried to run an ait brainstorm for task 427, (see ./aitask-crews/crew-brainstorm-427). from the brainstorm tui we have triggered an initial explorer agent (see explorer_001 yaml files. the explorer does not seem to be running, also it seems that the whole aitask repository has be cloned inside the brainstorm directory (see .git file) this was unexpected and not required, the crew-brainstorm-427 branch/directory is for files striclty related to the brainstorm and agentcrew management: can you investigate what happened? look also at how the explore operation is triggered in ait brainstorm code
