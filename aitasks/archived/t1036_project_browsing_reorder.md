---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: []
issue_type: enhancement
status: Done
labels: [tui_switcher, project_groups]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-21 07:56
updated_at: 2026-06-21 10:25
completed_at: 2026-06-21 10:25
boardidx: 20
---

in tui switcher we have support for two level browsing of other projects and project groups. we want to redesign the way we iterate over projects and project groups with left/arrow keys and [ ] keys. we want to keep the same basic logic but we the following tuning: the new behavior: when a project group is selected, show only the projects associated to that project group, but now left right arrows will allow to cross the project group boundaries. that is when we have the last project in a project group selected and we press the right arrow, we move to the the FIRST project in the next project group (that is we also switch the current group). in a similar way when we have the first project in a project group selected and we press the left arrow, we switch to the last project in the previous project group. ask me questions if you need clarifications

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-21T06:58:42Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-21T06:58:43Z status=pass attempt=1 type=machine

> **✅ gate:review_approved** run=2026-06-21T07:23:14Z status=pass attempt=1 type=human
