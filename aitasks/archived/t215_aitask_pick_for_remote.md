---
priority: high
effort: medium
depends: []
issue_type: feature
status: Done
labels: [claudeskills, aitask_pick, remove_support]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-23 08:19
updated_at: 2026-02-23 09:05
completed_at: 2026-02-23 09:05
---

Currently the aitask-pick skill support in theory development when running claude code web. In practice there are problems because on claude code web AskUserQuestion does not work as expected. so it would be a good a idea to have a separate aitask-pick skill where all usage of AskUserQuestion is removed and we configure it we execution profiles that must be expanded to include all questions needed. this will also simplify the current aitask-pick skll by removing the execution flow where running on remote is selected. so basically the new aitask-pick for remote dev should have two arguments 1) execution profile (extended, but basically unify with existing execution profile 2) no interactive task pick, 3) no worktree management, if this can simplify things. I am not sure if it is better integrate the new run mode in existing aitask-pick or separate one. but since we have already refactored the main part of aitask-pick as the task-workflow skill it make more sense to have a separate skill
