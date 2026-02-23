---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [aitasks]
created_at: 2026-02-04 11:16
updated_at: 2026-02-04 11:16
boardidx: 30
boardcol: next
---

Add support to revert work of an alredy completed task, that has already (its changes to code ) committed to git, and (perhaps) its task file already archived. this is should be a new claude skill: aitask-revert. There are several steps involved 1) if a task number argument was not provided to the skill, explore the code base and list of completed tasks even in the archive directory (ask user completion date limit to when searching) search also in archived and olso in old.tar.gz. 2) once a list of candidate has been identified, (a list of filename paths) ask the user to choose one with the AskUserQuestion tool 3)once the user choose, need to identify the git commits associated with the task (commit with changes to the task file and to the source code itself) 4) once these commits has been identified, show then to user and ask for user confirmation with the message: Here are the commits that seems to be associated to the task. please confirm: this commits will be reverted 5) revert the changes of the commits associated tot he tasks, the task file description and plan file should be created back in aitasks and aiplans directory and deleted from archived directory and old.tar.gz. Take care when reverting the task description and plan file to revert to their LATEST version. Once the code is reverted. rebuild the project (if relevant) and check for compilation errors. if errors are found create a plan for fixing them, and ask confirmation from the user before executing the plan. once the everything compile succesfully, ask the user if he want to commit changes ..   This the flow for the aitask-revert command. ask me questions if you need clarifications
