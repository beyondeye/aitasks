---
priority: medium
effort: medium
depends: []
issue_type: performance
status: Done
labels: [aitask_board]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-26 15:23
updated_at: 2026-02-26 16:00
completed_at: 2026-02-26 16:00
boardidx: 10
---

after introducing in ait board support for checking tasks lock status, refresh of ait board has become very slow. this is a problem, because board refresh is called 1) when I close the task detail, 2)when a task is moved from column to column 3)when I move a task position in a column. board reaction to this action is too sluggish for a good user experience. need to fine a awy to refresh task lock status in a differnt way that does not affect UX, and board refresh performance. also perhap there should be a dedicated action to move a selected tasks to the top of a column or the bottom of a column, for making this common action faster perhaps ctrl+up and ctrl+down??
