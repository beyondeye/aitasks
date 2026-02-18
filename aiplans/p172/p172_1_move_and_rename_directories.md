---
Task: t172_1_move_and_rename_directories.md
Parent Task: aitasks/t172_rename_reviewmode_to_reviewguide.md
Sibling Tasks: aitasks/t172/t172_2_*.md, aitasks/t172/t172_3_*.md, aitasks/t172/t172_4_*.md, aitasks/t172/t172_5_*.md
Archived Sibling Plans: aiplans/archived/p172/p172_*_*.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

## Context

Child task 1 of t172 (rename reviewmode to reviewguide). This task handles all physical directory/file moves and renames. Must be done first since all other child tasks (t172_2 through t172_5) depend on the new directory structure being in place.

This task ONLY does physical moves/renames via `git mv`. Content updates (fixing internal references) are handled by subsequent child tasks.

## Plan

Execute these `git mv` operations in order:

### 1. Move installed reviewmodes to project root as `aireviewguides/`

```bash
git mv aitasks/metadata/reviewmodes/ aireviewguides/
```

Moves all contents: subdirectories (general/, python/, android/, shell/), vocabulary files (reviewtypes.txt, reviewlabels.txt, reviewenvironments.txt), and the .reviewmodesignore file.

### 2. Rename ignore file in new location

```bash
git mv aireviewguides/.reviewmodesignore aireviewguides/.reviewguidesignore
```

### 3. Rename seed directory

```bash
git mv seed/reviewmodes/ seed/reviewguides/
```

### 4. Rename ignore file in seed

```bash
git mv seed/reviewguides/.reviewmodesignore seed/reviewguides/.reviewguidesignore
```

### 5. Rename script file

```bash
git mv aiscripts/aitask_reviewmode_scan.sh aiscripts/aitask_reviewguide_scan.sh
```

### 6. Rename skill directories

```bash
git mv .claude/skills/aitask-reviewmode-classify/ .claude/skills/aitask-reviewguide-classify/
git mv .claude/skills/aitask-reviewmode-merge/ .claude/skills/aitask-reviewguide-merge/
```

### 7. Commit all moves

Single commit with message:
```
refactor: Move and rename reviewmode directories to reviewguide (t172_1)
```

## Verification

1. `ls aireviewguides/` — should contain general/, python/, android/, shell/, vocabulary .txt files, .reviewguidesignore
2. `ls seed/reviewguides/` — same structure with .reviewguidesignore
3. `ls aiscripts/aitask_reviewguide_scan.sh` — script renamed
4. `ls .claude/skills/aitask-reviewguide-classify/` — skill dir renamed
5. `ls .claude/skills/aitask-reviewguide-merge/` — skill dir renamed
6. `ls aitasks/metadata/reviewmodes/ 2>/dev/null` — should not exist
7. `git status` — clean after commit

## Final Implementation Notes

- **Actual work done:** All 6 `git mv` operations executed exactly as planned. 29 files renamed total (0 content changes).
- **Deviations from plan:** None — plan was followed exactly.
- **Issues encountered:** None.
- **Key decisions:** None needed — straightforward rename operations.
- **Notes for sibling tasks:**
  - The old directory `aitasks/metadata/reviewmodes/` no longer exists — all content is now at `aireviewguides/` (project root level)
  - The old `seed/reviewmodes/` is now `seed/reviewguides/`
  - The ignore file was renamed from `.reviewmodesignore` to `.reviewguidesignore` in both locations
  - Script renamed: `aiscripts/aitask_reviewmode_scan.sh` → `aiscripts/aitask_reviewguide_scan.sh`
  - Skill directories renamed: `aitask-reviewmode-classify` → `aitask-reviewguide-classify`, `aitask-reviewmode-merge` → `aitask-reviewguide-merge`
  - All file contents still reference "reviewmode" — that's expected and needs to be fixed by t172_2 through t172_5
  - The path change from `aitasks/metadata/reviewmodes/` to `aireviewguides/` is a significant path change (not just a rename) — scripts like install.sh will need path updates, not just text substitutions

## Post-Implementation

Step 9 from task-workflow: archive task and plan via `aitask_archive.sh 172_1`.
