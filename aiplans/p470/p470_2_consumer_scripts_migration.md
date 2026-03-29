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

## Final Implementation Notes
- **Actual work done:** Implemented all plan steps. Updated task_utils.sh (4 archive lookup blocks), aitask_query_files.sh (help text), aitask_revert_analyze.sh (_find_file_location), aitask_stats_legacy.sh (collect_from_tarball), aitask-revert SKILL.md (2 output format refs), renamed test_resolve_tar_gz.sh → test_resolve_tar_zst.sh with 15 tests including backward compat, updated test_query.sh and test_claim_id.sh, updated CLAUDE.md test list.
- **Deviations from plan:** (1) Used `_find_archive_for_task()` instead of `archive_path_for_id()` in task_utils.sh to properly handle .tar.zst/.tar.gz fallback for numbered archives — the plan said "no path changes needed" but this was necessary since `archive_path_for_id()` now returns .tar.zst which may not exist in unmigrated repos. (2) Removed plan Step 9 (test_t167_integration.sh) — verified it uses a distribution tarball for install.sh, not a task archive, so no migration needed. (3) Legacy fallback in task_utils.sh and aitask_revert_analyze.sh now loops over both .tar.zst and .tar.gz instead of checking a single hardcoded path.
- **Issues encountered:** None. All 3 test suites pass (15+75+23 tests).
- **Key decisions:** Used format-agnostic loop pattern (`for legacy in .tar.zst .tar.gz`) for legacy fallback paths throughout, ensuring backward compatibility with unmigrated repos.
- **Notes for sibling tasks:**
  - All consumer scripts now use `_search_archive()` and `_extract_from_archive()` from archive_utils.sh — no more direct `_search_tar_gz`/`_extract_from_tar_gz` calls outside the libraries.
  - Output prefix `ARCHIVED_TASK_ARCHIVE:` is now the standard (was `ARCHIVED_TASK_TAR_GZ:`). Location type is `archive` (was `tar_gz`).
  - `aitask_stats_legacy.sh` now uses `_archive_list()` and `_archive_extract_file()` helpers instead of direct tar commands.
  - `test_t167_integration.sh` does NOT need migration — it's a distribution tarball, not a task archive.
  - The `create_test_archive_gz()` helper was added to test_resolve_tar_zst.sh for backward compat test fixtures.
