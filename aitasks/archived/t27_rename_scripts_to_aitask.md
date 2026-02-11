---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Completed
labels: [scripting]
created_at: 2026-02-02 10:38
updated_at: 2026-02-03 12:00
completed_at: 2026-02-03
---

## Completed

Standardized all script names to use `aitask` (singular) prefix:

### Renamed Scripts:
- `aitasks_create.sh` → `aitask_create.sh`
- `aitasks_ls.sh` → `aitask_ls.sh`
- `aitasks_update.sh` → `aitask_update.sh`
- `aitask_clear_old.sh` (already correct)

### Updated References in:
- `.claude/skills/aitask-create/SKILL.md`
- `.claude/skills/aitask-create2/SKILL.md`
- `.claude/skills/aitask-pick/SKILL.md`
- Internal help texts and cross-references in all scripts

### Notes:
- `.aider.conf.yml` had no script references, no changes needed
- Skill directory names already used correct `aitask-` prefix with hyphen
