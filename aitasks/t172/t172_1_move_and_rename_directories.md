---
priority: high
effort: medium
depends: []
issue_type: refactor
status: Implementing
labels: [aitask_review]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-18 22:01
updated_at: 2026-02-18 22:45
---

## Context

Child task 1 of t172 (rename reviewmode to reviewguide). This task handles all physical directory/file moves and renames. Must be done first since all other child tasks depend on the new directory structure being in place.

## Key Changes

### 1. Move installed reviewmodes to project root as `aireviewguides/`

```bash
git mv aitasks/metadata/reviewmodes/ aireviewguides/
```

This moves all contents: subdirectories (general/, python/, android/, shell/), all .md files, vocabulary files (reviewtypes.txt, reviewlabels.txt, reviewenvironments.txt), and the ignore file.

### 2. Rename ignore file

```bash
git mv aireviewguides/.reviewmodesignore aireviewguides/.reviewguidesignore
```

### 3. Rename seed directory

```bash
git mv seed/reviewmodes/ seed/reviewguides/
```

Also rename the ignore file in seed:
```bash
git mv seed/reviewguides/.reviewmodesignore seed/reviewguides/.reviewguidesignore
```

### 4. Rename script file

```bash
git mv aiscripts/aitask_reviewmode_scan.sh aiscripts/aitask_reviewguide_scan.sh
```

### 5. Rename skill directories

```bash
git mv .claude/skills/aitask-reviewmode-classify/ .claude/skills/aitask-reviewguide-classify/
git mv .claude/skills/aitask-reviewmode-merge/ .claude/skills/aitask-reviewguide-merge/
```

### 6. Commit all moves

Single commit with all the `git mv` operations:
```
refactor: Move and rename reviewmode directories to reviewguide (t172_1)
```

## Important Notes

- This task ONLY does physical moves/renames. Content updates (fixing internal references) are handled by subsequent child tasks.
- After this task, many files will have broken internal references — that's expected and will be fixed by t172_2 through t172_5.
- The `git mv` preserves git history for all moved files.

## Verification

1. `ls aireviewguides/` — should contain general/, python/, android/, shell/, vocabulary .txt files, .reviewguidesignore
2. `ls seed/reviewguides/` — same structure
3. `ls aiscripts/aitask_reviewguide_scan.sh` — script renamed
4. `ls .claude/skills/aitask-reviewguide-classify/` — skill dir renamed
5. `ls .claude/skills/aitask-reviewguide-merge/` — skill dir renamed
6. `ls aitasks/metadata/reviewmodes/ 2>/dev/null` — should not exist
7. `git status` — clean after commit
