---
priority: high
effort: high
depends: []
issue_type: refactor
status: Implementing
labels: [task-archive, archiveformat]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-27 13:08
updated_at: 2026-03-29 08:42
---

Migrate the two foundational bash libraries (archive_utils.sh + archive_scan.sh) from tar.gz to tar.zst, with backward compatibility fallback to tar.gz. Update corresponding tests.

## Context

This is the first and most critical child task of t470 (migrate archive format). All other child tasks depend on these core library changes. The pipe approach is decided: `zstd -dc file | tar -tf -` for reading, `tar -cf - -C dir . | zstd -q -o file` for writing. No `--zstd` flag, no platform detection.

## Key Files to Modify

### `.aitask-scripts/lib/archive_utils.sh`
- Rename `_search_tar_gz()` → `_search_archive()` — pipe: `zstd -dc "$archive" | tar -tf - 2>/dev/null | grep -E "$pattern"`
- Rename `_extract_from_tar_gz()` → `_extract_from_archive()` — pipe: `zstd -dc "$archive" | tar -xf - -O "$filename"`
- Add internal helpers that auto-detect format by file extension:
  - `_archive_list()` — lists archive contents (replaces `tar -tzf`)
  - `_archive_extract_file()` — extracts single file to stdout (replaces `tar -xzf -O`)
  - `_archive_extract_all()` — extracts all to directory (replaces `tar -xzf -C`)
  - For `.tar.zst`: use `zstd -dc | tar` pipe. For `.tar.gz`: use `tar -tzf`/`tar -xzf` (backward compat)
- Update `archive_path_for_id()` to return `.tar.zst` extension instead of `.tar.gz`
- Update `_search_all_archives()` glob from `old*.tar.gz` to `old*.tar.zst` with `.tar.gz` fallback
- Update `_search_numbered_then_legacy()` to try `.tar.zst` first, then `.tar.gz`
- Preserve EXIT trap cleanup logic for `_AIT_ARCHIVE_TMPDIR`
- Preserve the no-command-substitution pattern for `_extract_from_archive()`

### `.aitask-scripts/lib/archive_scan.sh`
- Update `scan_max_task_id()`: change globs `_b*/old*.tar.gz` → `_b*/old*.tar.zst` (with `.tar.gz` fallback), use new helper functions
- Update `search_archived_task()`: use new function names, change output format `ARCHIVED_TASK_TAR_GZ:` → `ARCHIVED_TASK_ARCHIVE:` (format-agnostic — archive format details must not leak into consumers/skills)
- Update `iter_all_archived_files()`: change globs and tar commands to new helpers

### `tests/test_archive_utils.sh` (48 test cases)
- Update `create_test_archive()` helper to create `.tar.zst` fixtures using `tar -cf - -C "$source_dir" . | zstd -q -o "$archive_path"`
- Update all path assertions from `.tar.gz` to `.tar.zst`
- Add backward compat test: create a `.tar.gz` archive and verify functions can still read it
- Keep `create_test_archive_gz()` helper for backward compat tests

### `tests/test_archive_scan.sh` (12 test cases)
- Update fixture creation to tar.zst
- Update assertions checking `ARCHIVED_TASK_TAR_GZ:` → `ARCHIVED_TASK_ARCHIVE:`
- Update glob patterns in test expectations

## Reference Files for Patterns
- Current `archive_utils.sh` functions (lines 77-162) show the tar.gz patterns to replace
- Current `archive_scan.sh` functions (lines 27-165) show the scanning patterns
- Task t470 description has the complete command pattern table

## Implementation Plan
1. Add new internal helper functions (`_archive_list`, `_archive_extract_file`, `_archive_extract_all`) at the top of `archive_utils.sh` — these auto-detect format by extension
2. Rename and update the public functions (`_search_archive`, `_extract_from_archive`)
3. Update `archive_path_for_id()` to return `.tar.zst`
4. Update `_search_all_archives()` and `_search_numbered_then_legacy()` globs and fallback logic
5. Update all `archive_scan.sh` functions
6. Update test fixtures and assertions in both test files
7. Run tests: `bash tests/test_archive_utils.sh && bash tests/test_archive_scan.sh`
8. Run shellcheck: `shellcheck .aitask-scripts/lib/archive_utils.sh .aitask-scripts/lib/archive_scan.sh`

## Verification
- `bash tests/test_archive_utils.sh` — all 48 tests pass
- `bash tests/test_archive_scan.sh` — all 12 tests pass
- `shellcheck .aitask-scripts/lib/archive_utils.sh .aitask-scripts/lib/archive_scan.sh` — no errors
