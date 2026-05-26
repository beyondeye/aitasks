---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Done
labels: [aitask_monitor, tui_switcher]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-05-26 12:20
updated_at: 2026-05-26 13:31
completed_at: 2026-05-26 13:31
boardidx: 20
---

in ait monitor and ait minimonitor we can use j to open the tui switcher. when working with multiple sessions, the tui switcher currently always open with the first tmux session selected. we want to thcange this behaviour and define the session that get selected on tui switcher start based on the current coding agent that is selected in the monitor or minimonitor: if the selected coding agent (if any is selected) is from session <A> then open the tui switcher with secion <A> selected
