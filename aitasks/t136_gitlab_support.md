---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [aitasks, scripting]
created_at: 2026-02-16 14:34
updated_at: 2026-02-16 14:34
boardcol: now
boardidx: 40
---

the claude skills aitask-issue-import and aitask-issue-update currently support only github, but basically all the github specific logic is encapsulated in the bash scripts aitask_issue_import.sh and aitask_issue_update.sh. I want to add support for gitlab. need also to update install instructions in README.md to mention the gitlab cli tool and how to authenticate. also in ait setup when running in a specific project repo need to autoinstall the gitlab cli dependency interact with with it in the issue_import and issue_update scripts, and in general to authenticate with it in order to support aitasks operations with git remote like git push. ask me questions if you need clarficaitonas. make sure to explore the current skills definitions and bash script to check all needed changes to support gitlab
