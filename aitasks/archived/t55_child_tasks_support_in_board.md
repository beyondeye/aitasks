---
priority: medium
effort: high
depends: []
issue_type: feature
status: Done
labels: [aitask_board, aitasks]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-08 10:29
updated_at: 2026-02-08 13:24
completed_at: 2026-02-08 13:24
boardidx: 20
---

currently aitask_boarthon TUI do not handle child tasks. Tasks are only read fom the main aitasks directory not from the task child subdirectory. This make sensense from the point of view of the task boards, but there should be some child tasks awareness in the TUI, for example when showing a tasks with child tasks, it should show the number of child tasks still to be implemented. and when the task details are open if a child task is clicked we should open the details of the child task. the child task detail should have in the metadata section a field: Parent that when clicked will show back the parent task detail. ask me questions if you need more clarifications
