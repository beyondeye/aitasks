---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [aitask_pick]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-24 23:31
updated_at: 2026-02-25 15:58
---

the post implementation workflow (task_workflow skill) consistently try to use normal git operations when adding to git the final implementation plan, when committing the changes done with implementation. this happens consistently, because claude code try to git add with a single git add command both the code changes and the plan files, and the operation fails and claude code understand that it needs to make two separate git add one with regular git for code and one with ait git for task data modification (the task plan). we should fix this, it is just noise and overhead for nothing this is the log I see from claude code: ● User answered Claude's questions:
