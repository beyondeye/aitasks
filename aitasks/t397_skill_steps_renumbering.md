---
priority: medium
effort: medium
depends: []
issue_type: refactor
status: Ready
labels: []
created_at: 2026-03-15 22:22
updated_at: 2026-03-15 22:22
boardcol: now
boardidx: 50
---

after several additions to the skill (for example aitask-pick recently) the current step numebering in skill, is not very logical, it only reflects the need to insert steps between step between steps, 1a, 1b, etc. steps not necessarily because of correlation between steps byt because we had to insert a step without renumbering all others. this task for FINALLY renumbering steps in a logical way, according to the following principles: 1) try to avoid number+ letters, use only numbers. after renumbering update associated references to renumbred steps accordingly, make extra care to verify the step reference are not broken. note that thare are certain procedures that has references to their step outside their file. be super careful in particular with steps in planning.md and in the task-workflow.md. renumber staps for all skills. ask me questions if you need clarfications
Note also that references to the skill steps number can be in website docs for the skill. need to check carefully also that documentation
