---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Done
labels: [aitasks, bash]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-10 22:06
updated_at: 2026-02-10 22:31
completed_at: 2026-02-10 22:31
---

create a new bash script that given the task number of an archived file and optional a set of git commits (or automaically extract the git commits associated to a task implementation from git history) update  a git issue with the fix to the issue (a summary of what was done with reference to the archived aiplan for the task for the full details) and optionally alss close the github issue. the update for the fit issue should be done as a comment. no interactive mode for this script, call this script aitask_issue_update. implement it using the gh github cli, but structure the script to allow support of other github host site like github and bitbucket, in similar way as the aitask_import has been structure. also modify the sibling task t53_5 to depend on this task and use a call to this script for adding the option in the aitask-pick workflow to close/update a github issue associated to the task at task completion. note that the link to the issue is in the task metadata, it is not passed as a parameter to the script: to the aitask_issue_update we pass the task number, similarly as how we pask the task number to the aitask_update,sh script. ask me questions if you need clarifications
