---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: []
created_at: 2026-02-23 13:03
updated_at: 2026-02-23 13:03
---

In Claude Code Web (aitask-pickrem), ait setup is not run before picking tasks. When aitask-data branch mode is active, the worktree checkout and symlinks need to be initialized before any task operations work. Extract the worktree checkout + symlink setup from aitask_setup.sh into a lightweight script (e.g. aitask_init_data.sh) that checks if aitasks/ exists, creates .aitask-data/ worktree and symlinks if needed. Update aitask-pickrem SKILL.md to call it at startup.
