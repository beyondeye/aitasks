---
priority: high
effort: medium
depends: [t85_2, t85_3, t85_4, t85_5, t85_6]
issue_type: feature
status: Done
labels: [bash, aitasks]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-11 10:00
updated_at: 2026-02-11 14:24
completed_at: 2026-02-11 14:24
---

## Context

This is child task 9 of parent task t85 (Cross-Platform aitask Framework Distribution). After the `beyondeye/aitasks` repo is set up with all the reorganized files (tasks 1-8), this task applies the same changes back to the tubetime project where the framework originally lived.

**Working directory**: `~/Work/tubetime/` (the tubetime project)
**Source of truth**: `~/Work/aitasks/` (the new aitasks repo, with all fixes applied)

## What to Do

### 1. Remove old root-level bash scripts

These 8 scripts are being replaced by the `aiscripts/` directory structure:

```bash
cd ~/Work/tubetime
git rm aitask_create.sh
git rm aitask_ls.sh
git rm aitask_update.sh
git rm aitask_import.sh
git rm aitask_board.sh
git rm aitask_stats.sh
git rm aitask_clear_old.sh
git rm aitask_issue_update.sh
```

### 2. Remove old Python TUI directory

```bash
git rm -r aitask_board/
```

Note: There may be a `aitask_board/__pycache__/` that's untracked. Remove it too if present:
```bash
rm -rf aitask_board/__pycache__/
```

### 3. Copy new files from aitasks repo

```bash
# Copy the dispatcher
cp ~/Work/aitasks/ait ./ait
chmod +x ./ait

# Copy VERSION
cp ~/Work/aitasks/VERSION ./VERSION

# Copy all scripts (with fixes from t85_3 and t85_6 applied)
cp -r ~/Work/aitasks/aiscripts/ ./aiscripts/
chmod +x ./aiscripts/*.sh
```

### 4. Update Claude Code skill files

The skill files in `.claude/skills/` need their script references updated (from `./aitask_*.sh` to `./aiscripts/aitask_*.sh`). Copy the fixed versions from the aitasks repo:

```bash
for skill in aitask-create aitask-create2 aitask-pick aitask-stats aitask-cleanold; do
    cp ~/Work/aitasks/skills/$skill/SKILL.md .claude/skills/$skill/SKILL.md
done
```

### 5. Update .gitignore

Replace the old `aitask_board/__pycache__/` entry (if present) with:
```
aiscripts/board/__pycache__/
```

### 6. Verify everything works

Test each command from the project root:

```bash
# Basic dispatcher
./ait --version          # Should print "ait version 0.1.0"
./ait help               # Should print usage

# Task listing (core functionality)
./ait ls -v 15           # Should list tasks from aitasks/ directory

# Task creation help
./ait create --help      # Should show create options

# Board (Python TUI)
./ait board              # Should launch using ~/.aitask/venv/bin/python
                         # (press q to exit)

# Stats
./ait stats              # Should show completion statistics

# Setup (re-run is safe)
./ait setup              # Should report tools already installed
```

### 7. Check that no old references remain

```bash
# No root-level aitask scripts should exist
ls aitask_*.sh 2>/dev/null && echo "ERROR: old scripts still present" || echo "OK: old scripts removed"

# No old aitask_board directory
ls -d aitask_board/ 2>/dev/null && echo "ERROR: old board dir still present" || echo "OK: old board dir removed"

# Skills should reference aiscripts/
grep -r '\./aitask_[a-z]' .claude/skills/ && echo "ERROR: old skill refs found" || echo "OK: skill refs updated"
```

### 8. Commit

```bash
cd ~/Work/tubetime
git add ait VERSION aiscripts/ .claude/skills/
git add -u  # captures the removals
git commit -m "Migrate aitask framework to aiscripts/ directory structure

- Move 8 bash scripts to aiscripts/
- Move Python TUI to aiscripts/board/
- Add ait dispatcher for 'ait <command>' usage
- Update all skill files to reference new paths
- Add VERSION file (0.1.0)

Part of t85: cross-platform aitask framework distribution"
```

## Important Notes

- Do NOT remove `aitasks/` or `aiplans/` directories — those contain task data, not framework code
- Do NOT remove `.claude/skills/` — only update the SKILL.md files inside the aitask skill directories
- The `ait` script and `aiscripts/` directory should be committed to git (they are project files, not gitignored)
- After this change, collaborators will use `./ait create` instead of `./aitask_create.sh`

## Verification

1. `./ait ls -v 15` works and shows tasks
2. `./ait board` launches the TUI
3. `./ait --version` shows `0.1.0`
4. `ls aitask_*.sh 2>/dev/null` returns nothing (old scripts removed)
5. `ls -d aitask_board/ 2>/dev/null` returns nothing (old board dir removed)
6. `grep -r '\./aitask_[a-z]' .claude/skills/` returns nothing (all refs updated)
7. `git status` shows a clean state after commit
