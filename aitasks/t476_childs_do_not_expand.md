---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [aitask_board]
created_at: 2026-03-29 09:42
updated_at: 2026-03-29 09:42
---

after the last optimization of ait board ui main view update with specific operation to swap to adjacent tasks in a column, sometimes the board remain stack in a state where the "x" command to expand/collapse a parent task children has not effect. I am not sure if this is directly related to the new swap task logic or not. Anyway I notices that after forcing a board refresh with "r" the issue go away. I need to troubleshoot and fix this issue
