---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [aitask_monitormini]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-10 00:18
updated_at: 2026-04-10 07:35
---

currently it appears that when the minimonitor tui pane is selected and multiple codeagent are running by switching with top/down arrow the selection between them, we automatically switch to the corresponding codegent window, without pressing "c" shortcut, this was not the intended behavior: the intended behavior was to automatically focus the minimonitor pane when we switch between codeagent tmux windows, and focus/select in the list of codeagent the one corresponding to the current selected codeagen window, BUT only switch between visible codeagent windows only when we press che switch shortcut
