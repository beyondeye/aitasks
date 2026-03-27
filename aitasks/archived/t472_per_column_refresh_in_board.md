---
priority: medium
effort: medium
depends: []
issue_type: performance
status: Done
labels: [aitask_board]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-27 08:25
updated_at: 2026-03-27 16:57
completed_at: 2026-03-27 16:57
boardidx: 70
---

currently in ait board in the main screen , each time we update any of the tasks, we simply reload all the tasks in order to update the ux with the updated data. this is extremly inefficient and make the UX experience very bad. we want to introduce primitives that instead of reloading data of all tasks from disks and rebuild the whole board ux from the new data, when only one, or a subset of tasks update. tha basic primitive should be 1) single task reload and update in ux 2) single column reload and update in ux, 3)two column reload and update. and in all place where now we force reload of all data. instead call the appropriate operations (obviously keep also the full task data reload and ux update that already exists.
