---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Done
labels: [aitask_monitormini]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-04-16 12:55
updated_at: 2026-04-16 15:43
completed_at: 2026-04-16 15:43
---

in aitask minimonitor tui that is spawned as companion tui for codeagent windows pane, we have a "s" shortcut that allow to switch to the tmux window of the current selected agent. the expected behavior is that after the switch, the focused item in the ait minimonitor in the new focused window should match the codeagent running in that window. this is not working. is this even possible to implement. is it supposed to work? I thought that this was implemented but perhaps I am wrong, perhaps there is no such mechanism implemented in the code. and perhaps is not possible to be implemented. pleas help analyze code and decide.
