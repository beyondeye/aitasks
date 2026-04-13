---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [aitask_board]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-04-13 12:02
updated_at: 2026-04-13 12:21
---

aitask t475 is a parent task with siblings. most of its siblings where implemented. the remaining ones are not relevant anymore (changed designs, or implemented in other aitasks). I am not sure if the delete/archive operation button in task detail in ait board, will properly handle such kind of tasks: the parent task snould not be deleted, but remaining children should, and parent task should be prperly archived as completed. Also if we instead would delete all the remaining child task one by one by the delete/archive button, when the parent task remain we no more children to implement will be properly archived? I need to check this in the ait board code, and add proper support for this cases if it is missing. ask me questions if you need clarifications
