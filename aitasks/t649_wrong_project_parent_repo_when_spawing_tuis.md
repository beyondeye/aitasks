---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [statistics, tui_switcher, codebrowser]
created_at: 2026-04-26 12:29
updated_at: 2026-04-26 12:29
---

we have recently added support in TUI switcher dialog running in tmux, to swtich to codeagents/tuis running in other tmux session than current one. for example we are currently running two tmux sessions: aitasks and aitasks_mob, one for the ~/Work/aitasks project dir and one for ~/Work/aitasks_mobile project dir. the problem is that the tui switch does not actually "know" about each project main dir and so the tui switcher when asked to spawn for example "codebrowser" or "settings" or "board" or whatever tui in aitasks_mob, it actually spawn those tui running ait board, ait codebrowser, etc... commands from aitasks directory even if the aitasks_mob session is selected. this is not the desired behavior: TUI and brainstorm session should be specific for each tmux session that is identified as tmux session associated to the aitasks framework. ask me questions if you need clarification
