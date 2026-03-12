---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [aitask_fold, aitask_contribute]
created_at: 2026-03-12 11:28
updated_at: 2026-03-12 11:28
---

in the aitask-contribution-review skill wih can import issues and create from them aitasks. we check for overlapping issues, but we don't check for overlapping EXISTING tasks, on the other hand the mechanism for checking for overlapping tasks already exists, in aitask-explore and aitask-fold skills: the concept of folded tasks. we should integrate this also in the the aitask-cotribution-review skill. if overlap is found between existing tasks and the imported contribution, then should report to the user and ask he wants to fold the existing task in the new task we are creating from the imported contribution, or update the existing matching tasks to include the contributions and the contributors metadata. this is a complex task that should be splitted in child tasks, it also involve updating the aitask-contribution-review skill docs in the website

it should be decomposed in child tasks
