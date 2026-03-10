---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Done
labels: [aitask_pick]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-10 11:11
updated_at: 2026-03-10 11:46
completed_at: 2026-03-10 11:46
---

I have just run task 355. this task was explicitly defined was a "DESIGN" task with no code implementation. that created 7 child tasks. at the end pf the "implementation" that is after plan approval and creationg of all 7 child tasks and their plan, I got the following log of operation in claude code;

● Now revert the parent task status back to Ready (per the planning workflow — only child tasks

then claude code ask me the following question:

☐ Review

But THIS IS WRONG. If I archive the parent task t355, also the child tasks will be archived! note that exection profile was fast.yaml. this is the first time that this happend to me after a parent task that was decomposed in planning phase into multiple children.

this is what claude code answered me when I told him about it:   ● User answered Claude's questions:

CAN YOU HELP ADJUST THE WORKFLOW TO AVOID THIS SITUATION?
