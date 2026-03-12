---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Done
labels: [task_workflow, testing]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-12 08:24
updated_at: 2026-03-12 09:08
completed_at: 2026-03-12 09:08
---

When writing code with llm one of the best way to garantee code quality is automated tests or in general testing. normally teling the llm to write automated tests, in the task description, or during planning is enough to have a good test covering for new code. but there are cases where this is not enough: for code that require more detailed unit testing or for complex features that require integration or end-to-end testing, there should be follow up tasks so that developer don't forget to add this tests or test manually what is difficult to test in an automated way. I want to add a step in the task-workflow, that has an associate new execution profile field that must documented in all places where exection profile are documented edited (in ait settings, and in website documentation, in particular in the aitask-pick subpages)that is called test_followup_task with possible values: yes, no, ask. the default values are for fast profile: ask, for remote profiles no. the question should be asked just before task archival. if the user asnwer yes. the code agent must create a follow up task (if thie current task is a child task as a sibling task) where the llm should insert a reference to the current tasks, and as the tesxt of the new task: brainstorm ways to add integration tests, deeper unit tests, of end to end test with regard to the feature implemented in the task. the llm should only add this test, and relevant references already in the context, it should not run additional explorations. at the end of the task execution the llm context is already pretty depleted. so just insert relevant context information about the task to test, that is already available. leave further exploration the the follow up task.
