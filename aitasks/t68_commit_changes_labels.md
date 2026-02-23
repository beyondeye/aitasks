---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [aitasks, bash, scripting]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-09 10:22
updated_at: 2026-02-23 10:11
boardcol: backlog
boardidx: 10
---

currently in aitask_create bash script, if we add a new label that is not currently in labels.txt, the labels.txt file is updated but it is not commited to git. change the bash script so that when it commit the newly created task file to git to git, it also commit the updated labels.txt (if it was updated)
