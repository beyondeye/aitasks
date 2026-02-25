---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [aitask_pick]
created_at: 2026-02-25 13:09
updated_at: 2026-02-25 13:09
---

I am currently running a task with sibling tasks and claude code stops asking user consent: ❯ /aitask-pick 214_3

ls aiplans/archived/p214/ 2>/dev/null; echo "---"; ls aitasks/archived/t214/ 2>/dev/null;

how can we avoid this? perhaps define a helper script that is whitelisted to do the same? perhaps a general script that automatically run this ls commands encapsulated? please check the aitask_pick skill and where it is probable that calude code will issue this type of commands and propose a solution (please also check the task_workflow skill for similar issues)
