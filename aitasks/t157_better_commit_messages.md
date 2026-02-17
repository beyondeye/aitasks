---
priority: medium
effort: medium
depends: []
issue_type: refactor
status: Ready
labels: [bash, aitask_board, scripting]
created_at: 2026-02-17 16:28
updated_at: 2026-02-17 16:28
---

we should refactor all commit messages used in ALL aitasks claude code skills and in ALL scripts and python board TUI to use a common pattern according to the commit type if this is commit for specific for changes of task status, task creation, task backup, etc. prefix the commit message with "ait:", instead for commit made at task completion with actual implemented code, or documentation prefix the commit message with the corresponding task type, i.e. feature:, bug fix:, documentation: refactor:. it is very important for making it easier to parse commit history. ask me questions if you need clarifications
