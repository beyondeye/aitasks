---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [aitask_monitor]
created_at: 2026-04-12 09:58
updated_at: 2026-04-12 09:58
---

in ait monitor tui we have the (n)next sibling command that allow to automate the sequence of command of terminating a codeagent session and automatically opening a new one for the next sibling of a child task. this currently work only when the selected codeagent is a child task. it should also work when a task is a parent task with children and simply select the one of the children with logic similar to the one to select between siblings as defined already for the next sibling command
