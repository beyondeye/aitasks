---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [aitask_monitormini]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-08 12:51
updated_at: 2026-06-08 13:11
---

in ait minimonitor when we open the TUI switcher we autoselect the inital selected project repo tmux context based on the current selected codeagent in the minimonitor. this does not work well for the minimonitor, instead we should choose as default project the one of the associated codeagent (that is now outside of the list, it is shown in a separate unselectable pane) ask me questions if you need clarifications
