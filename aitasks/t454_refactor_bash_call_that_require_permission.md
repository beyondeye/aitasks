---
priority: medium
effort: medium
depends: []
issue_type: performance
status: Ready
labels: [claudeskills, whitelists]
created_at: 2026-03-24 21:07
updated_at: 2026-03-24 21:07
boardidx: 130
---

in several aitasks claude code skills there are calls to bash scripts that require explicit user consent, that are not currently whiteisted and cannot be. need to investigate all skills for this issue: here I will report what I found manually

here is one in aitask-pick: see attached log:

another one at the end of task-workflow: see attached log: ● Import works. Now Step 8: User Review and Approval.

another one from the end to task-workflow:   ● Bash(./.aitask-scripts/aitask_create.sh --batch --commit \
