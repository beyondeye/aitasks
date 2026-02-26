---
priority: medium
effort: low
depends: []
issue_type: performance
status: Ready
labels: [bash_scripts, task_workflow]
created_at: 2026-02-26 15:59
updated_at: 2026-02-26 15:59
boardidx: 20
---

currently at the end of the task_workflow (and possibly other similar workflow) we have a bash command (git status && echo "---" && git diff --stat)  fpr a summary of all changes made. the problem that this command is difficult to speciically whitelist for claude code, so perhaps encapsulate it in a custom small aitask_gitstatus.sh (internal command not exposed to users) and it to whitelisted command template in seed/claude_settings.local.json
