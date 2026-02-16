---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Done
labels: [aitasks_explore]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-16 17:09
updated_at: 2026-02-16 18:48
completed_at: 2026-02-16 18:48
---

I am now testing the aitask_explore skill. I have run it with the purpose of updating the current documentation of the aitask_workflow, at the stage of creating a task from the exploration the workflow correcly determined that no related tasks actually exists that can be folded in the new task created from the exploration, i forced the workflow to include as folded task t138. the workflow accepted that. then after task t140 creation, I told the workflow to start implementaiton. and it started it but, the workflow lost track of the current selected execution profile and started to ask me question at each step (like if I want to create a worktree). I don't know why this happened, please analyze the workflow and try understand what happened
