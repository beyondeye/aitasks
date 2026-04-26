---
priority: high
effort: medium
depends: []
issue_type: bug
status: Done
labels: [aitask_monitor, aitask_monitormini]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-26 17:15
updated_at: 2026-04-26 18:39
completed_at: 2026-04-26 18:39
---

there are some issue with ait monitor tui and minimonitor tui when showing codeagents from multiple tmux sessions associated to aitasks enabled projects. 1) the task description is shown only for the codeagent from the project where the ait monitor instance is running because the task data is read from the project directory from where ait monitor / minimonitor was started: THIS is BUG, the task data should be retrieved from the project directory associated to the codeagent. 2) related issue: in ait monitor, the "n" shortcut to pick the next sibiling between sibling of a parent task does not work when issued on codeagent that run in a different tmux session, again because task data is read from the wrong project repo.   ask me questions if you need clarifications
