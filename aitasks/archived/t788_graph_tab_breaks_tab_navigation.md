---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Done
labels: [ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7
created_at: 2026-05-18 15:51
updated_at: 2026-05-18 16:15
completed_at: 2026-05-18 16:15
---

in ait brainstorm we have top tab row that we can navigate with left/right arrows, and in all tabs pressing up arrow should in the end focus back the tab row if it is not already focused. this works in all tabs except the graph tab: as soon as the the graph tab get focused, ( event with left/right arrows moving focus between tabs in tab row) the focus GO AWAY from the tab row, to the graph nodes, and pressign up for focusing back the tab row (if no more nodes upper to curretn focused node are available) does not work. ask me questions if you need clarifications
