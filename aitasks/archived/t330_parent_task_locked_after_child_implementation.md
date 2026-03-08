---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Done
labels: [aitask_pick]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-08 08:26
updated_at: 2026-03-08 08:59
completed_at: 2026-03-08 08:59
---

currently after implementing a child task, that was choosen interactively in aitask-pick, the parent task continue to be reported as locked (at least in the ait board tui) I am not sure if this is related to the fact that I run aitask-pick 131 (the parent task) and then chose the child task to implement or there some other issue that cause the parent task to show as locked even if the child task completed. need to investigate this issue and understand better if there is any reason to mark the parent task as locked while some child is implemented: I don't think that this required, also what would happen in different user want to imlpement in parallel different children of the task? probably this is not a good workflow, but showing the parent task as locked (unless it was explicitly locked by the user through the ait board, it is misleading: we should avoid completely locking/unlocking parent task when we are implementing child task. only child task should be locked. leave the locking/unlocking of parent task to be manual in ait board, if the user so chooses
