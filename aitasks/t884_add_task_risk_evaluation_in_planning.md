---
priority: high
effort: high
depends: []
issue_type: enhancement
status: Ready
labels: [task_workflow, aitask-create]
children_to_implement: [t884_1, t884_2, t884_3, t884_4, t884_5, t884_6, t884_7]
created_at: 2026-05-31 18:35
updated_at: 2026-06-01 00:32
---

when writing code with coding agents it is sometimes difficult to evaluate if a feature we want the ai agent to implement will have negative effect on code stability, code quality, code maintanability. if we could have such an evaluation at the end of planning (store it as new task metadata field: risk with values high, med, low, readable in ait board) and updatable in ait update. it would be very useful, then we can a new special procedure: risk mitigation, that will spawn follow-up task to be run "before" and/or "after" the task implementation to mitigate possible risks associated to the task implementation. in the near future when we will have in place the gates feature (task 635) this can be integrated in the as many other parts of the task-workflow. this is complex task that need to be split in child tasks. ask me questions if you need clarifications. perhaps should also have an execution profile parameter to enable/disable the new risk evaluation procedure (and correspondingly update the execution profile editor in settings). the plan should have a risk session that details all risk identified, and link to follow-up/linked tasks for risk mitigation, if any of the risk mitigation tasks lands need to rerun the planning step / force reverify the plan when we pick the task again. needs to understand what mechanism to use in order to be sure that is forced to reverified after this linked tasks for risk mitigation are run.
