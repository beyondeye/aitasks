---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Done
labels: [aitask_board, brainstorming]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-04-05 11:00
updated_at: 2026-04-09 11:15
completed_at: 2026-04-09 11:15
boardidx: 30
---

we want to add a new action in  ait board, that is available for tasks when the task detail is shown, that is brainstorm, that will initialize a brainstorm session for the specified task if the brainstorm session is not initialized yet (see ait brainstorm command and brainstorm tui). if the brainstorm session already exists then directly open the brainstorm tui for the task for (by the way, launching the brainstorm tui for a task will automatically initialize the brainstorm session for the task, so we can just launch the brainstorm tui, and it will take care of initialization, if needed). need to use the action chooser dialog similar to pick action so that we can integrate with tmux (same as pick show the tmux tab by default in the dialog for launching the ait brainstorm tui. ask me questions if you need clarificaitons
