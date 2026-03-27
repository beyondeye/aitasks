---
Task: t470_2_consumer_scripts_migration.md
Parent Task: aitasks/t470_migrate_archive_format_tar_gz_to_tar_zst.md
Sibling Tasks: aitasks/t470/t470_1_*.md, aitasks/t470/t470_3_*.md
Archived Sibling Plans: aiplans/archived/p470/p470_*_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# t470_2: Consumer Scripts Migration

## Overview
Update all scripts that call `_search_tar_gz()`/`_extract_from_tar_gz()` to use the new names from t470_1. Update format-specific output strings to format-agnostic versions. Update tests.

## Step 1: Update task_utils.sh

8 call sites to rename:
- `_search_tar_gz` → `_search_archive` (4 sites in resolve_task_file, 4 in resolve_plan_file)
- `_extract_from_tar_gz` → `_extract_from_archive` (2 sites)
- Update `old.tar.gz` fallback path refs to try `old.tar.zst` first:
  ```bash
  local legacy_zst="$ARCHIVED_DIR/old.tar.zst"
  local legacy_gz="$ARCHIVED_DIR/old.tar.gz"
  for legacy in "$legacy_zst" "$legacy_gz"; do
      [[ -f "$legacy" ]] || continue
      ...
  done
  ```
- Update comments referencing `_search_tar_gz`

## Step 2: Update aitask_query_files.sh

- Line 69: `ARCHIVED_TASK_TAR_GZ:<entry>` → `ARCHIVED_TASK_ARCHIVE:<entry>`
- Update help text description from "found in old.tar.gz" to "found in archive"

## Step 3: Update aitask_revert_analyze.sh

- `_find_file_location()`: rename `_search_tar_gz()` calls → `_search_archive()`
- Lines 365/369: update paths to try `.tar.zst` first, fall back to `.tar.gz`
- Line 39 and all output lines: location type `tar_gz` → `archive`
- Update any comments/docs referencing tar.gz

## Step 4: Update aitask_stats_legacy.sh

- Line 13: `ARCHIVE_TAR` — try `old.tar.zst` first:
  ```bash
  if [[ -f "$ARCHIVE_DIR/old.tar.zst" ]]; then
      ARCHIVE_TAR="$ARCHIVE_DIR/old.tar.zst"
  else
      ARCHIVE_TAR="$ARCHIVE_DIR/old.tar.gz"
  fi
  ```
- `collect_from_tarball()`: replace direct `tar -tzf`/`tar -xzf -O` with `_archive_list()`/`_archive_extract_file()` from archive_utils.sh (source if not already sourced)

## Step 5: Update .claude/skills/aitask-revert/SKILL.md

- Line 43: `ARCHIVED_TASK_TAR_GZ:<entry>` → `ARCHIVED_TASK_ARCHIVE:<entry>`, description → "found in deep archive"
- Line 358: `tar_gz` → `archive`

## Step 6: Rename and update test_resolve_tar_gz.sh → test_resolve_tar_zst.sh

- `git mv tests/test_resolve_tar_gz.sh tests/test_resolve_tar_zst.sh`
- Update fixture creation: `tar -czf` → `tar -cf - | zstd -q -o`
- Update all path assertions: `.tar.gz` → `.tar.zst`
- Update CLAUDE.md test list

## Step 7: Update test_query.sh

- Lines 298-355: create `.tar.zst` fixtures instead of `.tar.gz`
- Update `ARCHIVED_TASK_TAR_GZ:` assertions → `ARCHIVED_TASK_ARCHIVE:`
- Update `assert_not_contains "TAR_GZ"` patterns

## Step 8: Update test_claim_id.sh

- Line 291: `tar -czf aitasks/archived/old.tar.gz` → pipe approach with `.tar.zst`

## Step 9: Update test_t167_integration.sh

- Line 74: `TARBALL` path → `.tar.zst`
- Update tar commands to pipe approach

## Step 10: Verify

```bash
bash tests/test_resolve_tar_zst.sh
bash tests/test_query.sh
bash tests/test_claim_id.sh
bash tests/test_t167_integration.sh
shellcheck .aitask-scripts/lib/task_utils.sh .aitask-scripts/aitask_revert_analyze.sh .aitask-scripts/aitask_stats_legacy.sh
```

## Step 9 Reference
Post-implementation: user review, commit, archive task, push.
