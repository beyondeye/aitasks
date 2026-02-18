---
priority: medium
effort: medium
depends: []
issue_type: performance
status: Implementing
labels: [claudeskills, bash_scripts]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-18 08:19
updated_at: 2026-02-18 09:25
---

the post implementation step in the task-workflow claude skill is mainly about updating metadata and moving and commiting files. it could more efficientlu handled by an ad-hoc script that should be also white-listed in claude_settings.json (also add it seed file claude_settings.lcaol.json) so that claude code will not ask me every time about potential dangerous delete and move operations, now that they are incorporated in an ad-hoc script. the more we can offload to a bash script for post implementation, the better
