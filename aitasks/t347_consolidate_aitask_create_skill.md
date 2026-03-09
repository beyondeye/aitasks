---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [aitask-create]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-09 15:05
updated_at: 2026-03-09 15:32
---

there are currently to skills for creating a new task. this is confusing the models. consolidate the two skill in only one skill (delete aitask_create2) and add instruction in aitask-create skill that for non interactive task creation you should run the batch script call as currently specificed in the aitask-create2 skill. need also to update documentation in website about aitask-create and aitask-create2 skill about this change and make sure that all references to aitask-create2 in docs are moved to aitask-create (since we removed aitask-create2) also obviously remove aitask-create2 from documented skills
