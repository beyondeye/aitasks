---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [aitask_monitor]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-09 10:23
updated_at: 2026-04-09 15:35
boardidx: 40
---

currently the user experience in ait monitor when a code agent complete a task with multiple siblings is not good. for starting (picking) the next sibling task we need to 1) kill the completed codeagent session 2) switch to ait board, and search the parent task 3) select the pick action from ait board. NOT GOOD. we should be able to do all this with a single keyboard shortcut from the ait board tui, when some codeagent is selected in the agent list panel. the "kill" part of the pick up next sibling keyboard shortcut should be done automatically if we detect that that correspondigly task is already marked as completed and the status of the task is committed (that is the end of the task-workflow has completed
