---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [aitask_pick, claudeskills]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-23 11:23
updated_at: 2026-02-23 11:45
---

currently when aitask-pick flow create child tasks, aftter presenting the plan for creating the child tasks, when the plan is approved, the skill automatically start child_task implementation (at least when FAST execution profile is selected). this is problematic, becauss usually when planning for child tasks, the claude code context at the end of planning is already quite full, and also an additional problem is that the child tasks plans are not written until implementatio of the first child is completed. so basically we should change the behavior so that even when the fast profile is selected, if we are currently creating child tasks we should stop and ask the user if to continue with first child implementation or stop here and only write plans, and in any case write child plans BEFORE starting child implementation
