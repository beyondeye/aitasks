---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [aitask_pick, codeagent]
created_at: 2026-03-06 10:00
updated_at: 2026-03-06 10:00
---

I have noticed in execution of aitask_pick of 319_1 that the task_workflow assigned the implementing agent as claude/opuse4_6: is this what is supposed to happen? should not be that be claudecode/opus4_6, also the task workflow, skip the interactive step after child plan verification, although there should be a specific instruction that for child tasks, even fast profile is selected, we should ask for plan confirmation even if child task plan exists and is verified, why this happened?
