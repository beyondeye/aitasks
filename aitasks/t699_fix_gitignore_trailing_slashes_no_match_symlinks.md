---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [ait_setup]
created_at: 2026-04-28 11:23
updated_at: 2026-04-28 11:23
boardidx: 60
boardcol: now
---

## Origin

Upstream defect surfaced during t687 diagnosis. Should have been
offered automatically by Step 8b but wasn't (see t698 for the meta-fix
to the workflow). Spawning manually here.

## Upstream defect

`.aitask-scripts/aitask_setup.sh:1170-1179` — `setup_data_branch`
appends `aitasks/` and `aiplans/` (with trailing slashes) to the
project's `.gitignore`. Trailing-slash gitignore patterns match
**directories only**, not symlinks. After `setup_data_branch` creates
the symlinks `aitasks -> .aitask-data/aitasks` and
`aiplans -> .aitask-data/aiplans`, those symlinks are NOT matched by
the trailing-slash rules and therefore appear as untracked in
`git status` — the same "dirty working tree after `ait setup`"
symptom family the user filed in beyondeye/aitasks#13.

## Reproduction (observed during t687 implementation)

After `ait setup` finishes in this repo, `git status` shows:

    Untracked files:
      aitasks
      aiplans

even though both entries exist in `.gitignore`. The same was visible
right after the t687 commit landed.

## Suggested fix

Drop the trailing slashes from the two entries in
`setup_data_branch`'s `.gitignore` block:

```diff
 # Task data (lives on aitask-data branch, accessed via symlinks)
 .aitask-data/
-aitasks/
-aiplans/
+aitasks
+aiplans
```

Plain `aitasks` / `aiplans` ignores BOTH directories AND symlinks.

## Migration

Existing repos already have the trailing-slash form committed in their
`.gitignore`. Two options:

1. Leave existing entries; only fix the seed for new installs.
2. Detect legacy trailing-slash entries during `ait setup` (or
   `ait upgrade`) and rewrite them to the symlink-safe form, then
   commit (mirroring the pattern `setup_python_cache_gitignore` now
   uses post-t687).

Option 2 is the user-visible fix — Option 1 leaves existing repos with
the dirty-tree symptom forever. Decide during planning.

## Files to consider

- `.aitask-scripts/aitask_setup.sh` — `setup_data_branch` lines
  1170-1179 (the gitignore append block)
- `tests/test_data_branch_setup.sh` and/or `tests/test_setup_git.sh`
  — add an assertion that `git status --porcelain` is clean after
  `setup_data_branch` runs and the symlinks are created
- Possibly `seed/` if a gitignore template exists there with the same
  pattern (grep for `^aitasks/$` and `^aiplans/$` under `seed/`)

## Verification

`git status --porcelain` after a fresh `bash install.sh
--dir /tmp/scratchXY` + `./ait setup` should be empty (no untracked
`aitasks` / `aiplans` symlinks).

## Related

- t687 (`aitasks/archived/t687_*.md`) — the task that fixed the
  `__pycache__/` half of beyondeye/aitasks#13. The user explicitly
  flagged this trailing-slash issue at the bottom of t687 as
  "possibly worth a separate issue."
- t698 — meta-fix to the task-workflow's upstream-defect detection
  that should have surfaced this automatically.
- Original issue: beyondeye/aitasks#13
