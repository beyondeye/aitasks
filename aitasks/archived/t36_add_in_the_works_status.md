---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Done
labels: [claudeskills, aitasks]
created_at: 2026-02-04 08:48
updated_at: 2026-02-04 22:48
completed_at: 2026-02-04 22:48
---

Currently aitasks-pick is designed for a single user in mind. but when multiple users make changes to a repo then there should a way to signal other users that somebody has picked an aitask and is working on it, so we need to add a new status for an aitask that is called "In progress" that is set when somebody pick the task for work (in ai-pick). need to modify the aitask_create script tot support the Implementing status when creating the task. and modify the aitask-skill to update the task and putting in the implmeenting status (and commit the change to repo) so everybody knows that somebody is working on it. need also to add an option at the several steps in the aitask-pick skill to abort work and revert changes including the current status for the aitask from implementing to Ready (or Editing status if we want to modify the task before other people pick it up). When somebody pick a task (using the aitask-pick skill) claude code should also add a metadata field with the email of who is actaully working on the issue. this email is optional. the skill should store the entered email in a line of aitasks/metadata/emails.txt similar to what is done with labels, so that if the userly previously entered an email this is will be stored there in will be possible to automatically pick it from there when running the aitask-create shell script (using a fzf menu like lables) or when running the aipick-skill using the AskUserQuestion tool.  ask me question questions if you need more clarifications
