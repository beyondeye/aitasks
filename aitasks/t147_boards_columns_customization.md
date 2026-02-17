---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [aitask_board]
folded_tasks: [58]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-17 11:40
updated_at: 2026-02-17 12:03
boardcol: now
boardidx: 20
---

I want to add a feature to allow to add or delete column to the task board, to edit their name and color. currently the customization available for columns is only to reorder them. these new features should be accessible from the command palette or by clicking on the column titles (for accessing the title names and column color)

---
*Folded from t58:* in the aitask_board python script it is already possible to move board columns with ctr+arrow. left / right, I would like the option rename a column, change its color and ADD a column. the board_config.json file already store information of the configured column, so editing and adding columns feature that is missing is only an issue of missing ui for these actions. I don't want keybinding for these actions it is good enough to have them in the app command palette that opens with control+p
