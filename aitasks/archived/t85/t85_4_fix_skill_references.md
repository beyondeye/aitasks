---
priority: high
effort: low
depends: [t85_1]
issue_type: feature
status: Done
labels: [bash, aitasks]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-11 10:00
updated_at: 2026-02-11 12:50
completed_at: 2026-02-11 12:50
---

## Context

This is child task 4 of parent task t85 (Cross-Platform aitask Framework Distribution). The Claude Code skill files (SKILL.md) reference bash scripts with paths like `./aitask_create.sh`. Now that scripts live in `aiscripts/`, all these references must become `./aiscripts/aitask_create.sh`.

All work is in the `beyondeye/aitasks` repo at `~/Work/aitasks/skills/`.

## What to Do

### Bulk replacement

In all 5 SKILL.md files under `skills/`, replace every occurrence of `./aitask_` with `./aiscripts/aitask_`.

This can be done with a single sed command:
```bash
cd ~/Work/aitasks
sed -i 's|\./aitask_|./aiscripts/aitask_|g' skills/*/SKILL.md
```

### Files affected and specific references

**File: `skills/aitask-create/SKILL.md`**
- `./aitask_ls.sh` (appears ~2 times) → `./aiscripts/aitask_ls.sh`
- `./aitask_update.sh` (appears ~1 time) → `./aiscripts/aitask_update.sh`

**File: `skills/aitask-create2/SKILL.md`**
- `./aitask_create.sh` (appears ~4+ times) → `./aiscripts/aitask_create.sh`

**File: `skills/aitask-pick/SKILL.md`** (most references — ~12 total)
- `./aitask_ls.sh` (appears ~3 times) → `./aiscripts/aitask_ls.sh`
- `./aitask_update.sh` (appears ~5 times) → `./aiscripts/aitask_update.sh`
- `./aitask_issue_update.sh` (appears ~3 times) → `./aiscripts/aitask_issue_update.sh`
- `./aitask_create.sh` (appears ~1 time) → `./aiscripts/aitask_create.sh`

**File: `skills/aitask-stats/SKILL.md`**
- `./aitask_stats.sh` (appears ~5 times) → `./aiscripts/aitask_stats.sh`

**File: `skills/aitask-cleanold/SKILL.md`**
- `./aitask_clear_old.sh` (appears ~4 times) → `./aiscripts/aitask_clear_old.sh`

### Important: do NOT double-replace

If running sed multiple times, ensure you don't end up with `./aiscripts/aiscripts/aitask_...`. The pattern `./aitask_` specifically only matches the root-level references, not anything already under `./aiscripts/`.

### Commit

```bash
cd ~/Work/aitasks
git add skills/
git commit -m "Update skill files to reference scripts in aiscripts/ directory"
```

## Verification

1. `grep -r '\./aitask_' ~/Work/aitasks/skills/` should return NO matches (all replaced)
2. `grep -r '\./aiscripts/aitask_' ~/Work/aitasks/skills/` should show all the new correct references
3. Spot-check `skills/aitask-pick/SKILL.md` (the largest file) to ensure references look correct
