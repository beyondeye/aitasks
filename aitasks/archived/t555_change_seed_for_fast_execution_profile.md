---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Done
labels: [task_workflow]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-04-15 10:01
updated_at: 2026-04-15 10:47
completed_at: 2026-04-15 10:47
---

currently for fast.yaml exection profile, we have the setting post_plan_action set to start_implementation. lately we changed the way we manage implementation plan reviews because we found out that now claude code create very comprehensive plan and exhaust most of the llm context during the planning phase. this causes the fact that most of the time we start implementation with the claude code llm context almost full, in most cases. to mitigate this issue we have changed handling of handling of plan verification by adding exit point from the task workflow if the user see that llm context is too full. for the same reason we want to change to always stop after plan approval even in the fast.yaml execution profile, and make sure that in the askuserquestion there after plan approval we have the option to run the task abort procedure and keep the plan.
