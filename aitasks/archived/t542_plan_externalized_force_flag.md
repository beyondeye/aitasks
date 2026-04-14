---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Done
labels: [bash_scripts]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-04-14 10:58
updated_at: 2026-04-14 11:13
completed_at: 2026-04-14 11:13
---

currently the plan_externalize bash script treats externalizing a plan as no op if plan file already exists: in some cases, when running child tasks and during plan review plan changes where made, claude code tries to update the plan with same script but if fails, because externalizing is no op if plan already exists. this is basically relevant for child tasks or tasks with a pre-existing plan file that are run thorugh the task-workflow: see the attached log from claude code session:

● Bash(./.aitask-scripts/aitask_plan_externalize.sh 540_1 --internal /home/ddt/.claude/plans/memoized-leaping-rivest.md)
