---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [task_workflow]
created_at: 2026-03-12 23:49
updated_at: 2026-03-12 23:49
boardidx: 20
---

claude code has memory files at /home/ddt/.claude/projects/-home-ddt-Work-aitasks/memory where it stores feedback on rejects by user about how it executed user commands. create a plan to update existing task workflows with this feedback, then delete this memory files. we don't want any behavior that is implicit. we want reproducible behavior also in the other code agents we use
