---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [aitask_monitor]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-30 12:16
updated_at: 2026-03-30 12:27
---

currently in ait monitor tui we show currently active codeagent with their window title: we could extract from the window title the task number they are working on and show some context information: first of all the actual task name, and also add an option to show the full task detail and plan without switching to ait board tui. this would probably require refactor some code from the ait board to a common widget (or perahps from codebrowser, where also we show task description/plan in the history screen. but actually none the codebrowser version nor ait board verssion are right for the monitor that should have a simple dialog that show the task text/ task plan markdown file
