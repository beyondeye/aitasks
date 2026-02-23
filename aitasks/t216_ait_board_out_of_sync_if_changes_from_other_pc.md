---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [aitask_board]
created_at: 2026-02-23 08:58
updated_at: 2026-02-23 08:58
boardidx: 30
---

the ait board, if work is done from other PCs can get out of sync, we need to issue a git pull + rebase command to retrieve tasks updated by other pcs. the problem is that running git pull + rebase when inside a claude session is relatively safer since claude code is smart enough handling possible conficts, in the python ait board I am not sure I want to to automate calling git pull to refresh the task list, perhaps this could be an action accessible only from the command palette, in any case the action should have git rebase support it should not be just a call to git pull. propose me possible solutions. ask me questions if you need clarifications
