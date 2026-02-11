---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [aitasks, claudeskills]
created_at: 2026-02-11 16:13
updated_at: 2026-02-11 16:13
---

currently this repo has a github workflow that when a new release is create build a tarbal with all the source needed for a user to install aitask scripts in his repo. currently the source of the claude skills to install are taken from the skills directory. change this so that the skills directory is created on the fly when running the github release workflow, on the basis of the aitask*** directories found in .claude/skills, in other words the current installed aitask skills in this project, make sure to copy only the skills that start with aitask, ask me questions if you need clarifications
