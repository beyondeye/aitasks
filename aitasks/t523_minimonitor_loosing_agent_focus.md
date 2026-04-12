---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [aitask_monitormini]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-12 09:31
updated_at: 2026-04-12 09:43
---

in ait minimonitor that is spawned as companion pane to a codeagent pane in tmux (for example when running ait board pick action), we have there a list of current active codeagents across the current tmux session. every ~1 seconds approximately the current selected agent in the list loose focus. can you help me troubleshoot this? ask me questions if you need clarifications
actually I noticed, that the current selected codeagent not only loose focus, but the selection is completely reset (that is when we press up down arrow to focus/select a codeagent in the list it always start selecting the first codeagent in the list)
