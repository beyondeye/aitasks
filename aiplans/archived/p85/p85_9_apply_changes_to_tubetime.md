---
Task: t85_9_apply_changes_to_tubetime.md
Parent Task: aitasks/t85_universal_install.md
Sibling Tasks: aitasks/t85/t85_10_write_readme.md, aitasks/t85/t85_11_aitask_update_basic_impl.md
Archived Sibling Plans: aiplans/archived/p85/p85_*_*.md
Worktree: N/A (working on current branch)
Branch: main
Base branch: main
---

## Context

Task t85_9: Apply the aitask framework migration to the tubetime project. The `beyondeye/aitasks` repo (at `~/Work/aitasks/`) has been set up with the reorganized directory structure (tasks 1-8 complete). Now we need to apply those same changes to tubetime where the framework originally lived.

## Implementation Plan

### Step 1: Remove old root-level bash scripts

```bash
git rm aitask_board.sh aitask_clear_old.sh aitask_create.sh aitask_issue_import.sh aitask_issue_update.sh aitask_ls.sh aitask_stats.sh aitask_update.sh
```

Note: The task file mentions `aitask_import.sh` but the actual file is `aitask_issue_import.sh`.

### Step 2: Remove old aitask_board/ directory

```bash
git rm -r aitask_board/
rm -rf aitask_board/__pycache__/
```

### Step 3: Copy new files from aitasks repo

```bash
cp ~/Work/aitasks/ait ./ait && chmod +x ./ait
cp ~/Work/aitasks/VERSION ./VERSION
cp -r ~/Work/aitasks/aiscripts/ ./aiscripts/
chmod +x ./aiscripts/*.sh
```

VERSION is `0.1.2`.

### Step 4: Update Claude Code skill files

```bash
for skill in aitask-create aitask-create2 aitask-pick aitask-stats aitask-cleanold; do
    cp ~/Work/aitasks/skills/$skill/SKILL.md .claude/skills/$skill/SKILL.md
done
```

### Step 5: Update .gitignore

Add `aiscripts/board/__pycache__/` entry.

### Step 6: Verify

- `./ait --version` → `0.1.2`
- `./ait ls -v 15` → lists tasks
- No old `aitask_*.sh` at root
- No old `aitask_board/` directory
- No old `./aitask_` references in skill files

## Final Implementation Notes
- **Actual work done:** All steps implemented as planned — removed 8 old root-level scripts, removed aitask_board/ directory, copied ait dispatcher + VERSION + aiscripts/ from aitasks repo, updated all 5 skill SKILL.md files, added .gitignore entry for aiscripts/board/__pycache__/.
- **Deviations from plan:** The task file referenced `aitask_import.sh` but the actual file was `aitask_issue_import.sh` (8 scripts total either way). VERSION is 0.1.2 (not 0.1.0 as original task stated).
- **Issues encountered:** After `git rm -r aitask_board/`, the `__pycache__/` directory remained as it was untracked. Required a separate `rm -rf aitask_board/` to fully clean up.
- **Key decisions:** Copied skill files directly from aitasks repo rather than manually updating references, since they were already correct.
- **Notes for sibling tasks:** The tubetime project now uses `./ait` dispatcher and `./aiscripts/` directory. All skill files reference `./aiscripts/aitask_*.sh` paths. The `aitask_board/__pycache__/` gitignore entry was replaced with `aiscripts/board/__pycache__/`.
