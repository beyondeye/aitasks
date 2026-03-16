---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Done
labels: [aitask_board, child_tasks]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-16 10:37
updated_at: 2026-03-16 11:33
completed_at: 2026-03-16 11:33
---

it can happen that the same feature implementation is covered by multiple aitasks. for this reason we have the aitask_fold skill. but not always at implementation time we remember to fold a subperseded task into the new one. for normal tasks we can solve this by simply deleting the superseded/already implemented elsewhere task. but for child tasks this is not possible. currently the ait board does not allow to delete child tasks. for example task t376_4 has already been covered by another dcumentation task, and it is now superseded. there is a reason child task are note allowed to be deleted. before deleting a child task we should check if other child tasks depend on it, both explcitly (this we could actually check from task metadata), and implicitly (this is is harder would require ai review, or user review). also a child task that is superseded, perhaps should be "archived" instead of deleted anywy. help me design a fix to the ait board that allow to safely archive superseded child tasks (via the existing delete button in task detail that trigger a special execution path for child tasks, that take into consideration all the issue specified, with proper user prompts and confirmations
