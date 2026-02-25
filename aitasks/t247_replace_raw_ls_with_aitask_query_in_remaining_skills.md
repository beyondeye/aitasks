---
priority: medium
effort: low
depends: [246]
issue_type: chore
status: Ready
labels: [aitask_pick]
created_at: 2026-02-25 14:48
updated_at: 2026-02-25 14:48
---

Replace raw ls commands with aitask_query_files.sh calls in the remaining 4 skill files that still use them.

Skills to update:
- .claude/skills/aitask-pickrem/SKILL.md — ~5 ls calls
- .claude/skills/aitask-pickweb/SKILL.md — ~5 ls calls
- .claude/skills/aitask-fold/SKILL.md — ~2 ls calls
- .claude/skills/aitask-create/SKILL.md — ~2 ls calls (may need list-children subcommand added to aitask_query_files.sh)

Reference: t246 created aiscripts/aitask_query_files.sh with subcommands: task-file, has-children, child-file, sibling-context, plan-file, archived-children, resolve. The script is already whitelisted in settings.local.json. Follow the same replacement patterns used in aitask-pick and task-workflow skills.
