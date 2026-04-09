---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [aitask_monitormini]
created_at: 2026-04-09 22:04
updated_at: 2026-04-09 22:04
boardidx: 20
---

in ait minimonitor tui, that is shown in a side pane in tmux windows with running codeagents, we have a list of currently active codeagents and we have the "s" switch shortcut to switch to a different codeagent window. when this happens the codeagent pane get focused. It would be better, if we are switching to a tmux windows with a codeagent that has a minimonitor pane running, to have the focus go to the minimonitor window, so that the we can immeediately switch back to another code agent window. for this to work best as possible is also to make sure that the current selected item in the list of codeagent in the minimonitor is set to the one matching the current tmux window and also allow to navigate (change the focused agent window) in the list of codeagents with up/down arrow keys. ask me questions if you need clarifications
