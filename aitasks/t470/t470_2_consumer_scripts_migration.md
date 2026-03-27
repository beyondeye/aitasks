---
priority: high
effort: medium
depends: [t470_1]
issue_type: refactor
status: Ready
labels: [task-archive, archiveformat]
created_at: 2026-03-27 13:08
updated_at: 2026-03-27 13:08
---

Update all consumer scripts that depend on archive_utils.sh/archive_scan.sh to use the new function names and format-agnostic output strings. Update corresponding tests.

## Context

After t470_1 renames the core archive functions and changes output formats, all consumers must be updated. This includes task resolution (task_utils.sh), query commands, revert analysis, legacy stats, and the aitask-revert skill definition.

Key changes from t470_1 that consumers must adapt to:
- `_search_tar_gz()` → `_search_archive()`
- `_extract_from_tar_gz()` → `_extract_from_archive()`
- `ARCHIVED_TASK_TAR_GZ:` → `ARCHIVED_TASK_ARCHIVE:`
- `archive_path_for_id()` now returns `.tar.zst` instead of `.tar.gz`
- Location type `tar_gz` → `archive`

## Key Files to Modify

### `.aitask-scripts/lib/task_utils.sh`
- `resolve_task_file()` (lines ~185-251): 4 call sites using `_search_tar_gz`/`_extract_from_tar_gz` — rename to `_search_archive`/`_extract_from_archive`
- `resolve_plan_file()` (lines ~259-325): 4 call sites — same renames
- Update fallback path refs from `old.tar.gz` to try `old.tar.zst` first
- Comments referencing `_search_tar_gz` need updating

### `.aitask-scripts/aitask_query_files.sh`
- Line 69 help text: update `ARCHIVED_TASK_TAR_GZ:` → `ARCHIVED_TASK_ARCHIVE:`
- Update any doc strings referencing `old.tar.gz`

### `.aitask-scripts/aitask_revert_analyze.sh`
- `_find_file_location()` (lines ~354-423): calls `_search_tar_gz()` directly — rename
- Lines 365/369: `tar_path="$ARCHIVED_DIR/old.tar.gz"` → try `old.tar.zst` first
- Line 39: location type `tar_gz` → `archive` in documentation
- Update all `tar_gz` location type outputs to `archive`

### `.aitask-scripts/aitask_stats_legacy.sh`
- Line 13: `ARCHIVE_TAR="$ARCHIVE_DIR/old.tar.gz"` → try `old.tar.zst` first, fall back to `old.tar.gz`
- `collect_from_tarball()` (lines ~430-442): uses direct `tar -tzf`/`tar -xzf -O` commands — replace with pipe approach or use the new `_archive_list()`/`_archive_extract_file()` helpers from archive_utils.sh

### `.claude/skills/aitask-revert/SKILL.md`
- Line 43: `ARCHIVED_TASK_TAR_GZ:<entry>` → `ARCHIVED_TASK_ARCHIVE:<entry>`, update description from "found in deep archive (old.tar.gz)" to "found in deep archive"
- Line 358: location type `tar_gz` → `archive`

### `tests/test_resolve_tar_gz.sh` → rename to `tests/test_resolve_tar_zst.sh`
- Rename the file
- Update 14 test cases: fixture creation from `tar -czf` to `tar -cf - | zstd -q -o`
- Update path assertions from `.tar.gz` to `.tar.zst`
- Add backward compat test with `.tar.gz` fallback
- Update CLAUDE.md test list reference

### `tests/test_query.sh`
- Lines 298-355: archived-task tests create `old.tar.gz` with `tar -czf` → update to `old.tar.zst` with pipe approach
- Update assertions: `ARCHIVED_TASK_TAR_GZ:` → `ARCHIVED_TASK_ARCHIVE:`
- Update `assert_not_contains "TAR_GZ"` → update pattern

### `tests/test_claim_id.sh`
- Line 291: `tar -czf aitasks/archived/old.tar.gz` → `tar -cf - | zstd -q -o aitasks/archived/old.tar.zst`

### `tests/test_t167_integration.sh`
- Line 74: `TARBALL="/tmp/aitasks_test_t167.tar.gz"` → `.tar.zst` and update tar commands

## Implementation Plan
1. Update `task_utils.sh` function call names (8 call sites)
2. Update `aitask_query_files.sh` help text
3. Update `aitask_revert_analyze.sh` function calls, paths, and location type
4. Update `aitask_stats_legacy.sh` path and tar commands
5. Update `aitask-revert/SKILL.md` output format references
6. Rename and update `test_resolve_tar_gz.sh` → `test_resolve_tar_zst.sh`
7. Update `test_query.sh`, `test_claim_id.sh`, `test_t167_integration.sh`
8. Run all updated tests
9. Update CLAUDE.md test list

## Verification
- `bash tests/test_resolve_tar_zst.sh` — all 14 tests pass
- `bash tests/test_query.sh` — archive-related tests pass
- `bash tests/test_claim_id.sh` — passes
- `bash tests/test_t167_integration.sh` — passes
- `shellcheck .aitask-scripts/lib/task_utils.sh .aitask-scripts/aitask_revert_analyze.sh .aitask-scripts/aitask_stats_legacy.sh`
