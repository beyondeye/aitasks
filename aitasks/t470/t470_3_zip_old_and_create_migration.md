---
priority: high
effort: high
depends: []
issue_type: refactor
status: Ready
labels: [task-archive, archiveformat]
created_at: 2026-03-27 13:09
updated_at: 2026-03-27 13:09
---

Update aitask_zip_old.sh (primary archive creation/management script) and aitask_create.sh to use tar.zst format with pipe approach. Update corresponding tests.

## Context

This task can run in parallel with t470_2 (both depend on t470_1 core libs). aitask_zip_old.sh is the only script that CREATES archives — all others only read. aitask_create.sh has 2 simple tar.gz references for querying the legacy archive.

## Key Files to Modify

### `.aitask-scripts/aitask_zip_old.sh`
This is the most complex file to migrate — it creates, merges, verifies, and unpacks archives.

**`_archive_single_bundle()` (lines ~226-281):**
- Line 239: `tar -xzf "$archive_path" -C "$temp_dir"` → use `_archive_extract_all()` helper from archive_utils.sh (auto-detects format), or pipe: `zstd -dc "$archive_path" | tar -xf - -C "$temp_dir"`
- Line 261: `tar -czf "$archive_path" -C "$temp_dir" .` → `tar -cf - -C "$temp_dir" . | zstd -q -o "$archive_path"` (always create as .tar.zst)
- Line 262: `tar -tzf "$archive_path" > /dev/null` → `zstd -dc "$archive_path" | tar -tf - > /dev/null` (verify)

**`cmd_unpack()` (lines ~372-440):**
- Line 395: `tar -tzf "$arch" 2>/dev/null | grep -E pattern` → use `_archive_list()` helper or pipe
- Line 401: `tar -xzf "$arch" -C "$temp_dir"` → use helper or pipe
- Line 429: `tar -czf "$arch" -C "$temp_dir" .` → pipe approach (recreate as .tar.zst)
- Lines 370/387: Legacy fallback paths `old.tar.gz` → try `old.tar.zst` first

**Git staging (lines ~532-533):**
- Change glob pattern `_b*/old*.tar.gz` → `_b*/old*.tar.zst`

**Help text and comments:**
- Update all references from `tar.gz` to `tar.zst`
- Numbering scheme comments (lines 4, 9, 50): update examples

### `.aitask-scripts/aitask_create.sh`
- Line 15: `ARCHIVE_FILE="aitasks/archived/old.tar.gz"` → try `old.tar.zst` first, fall back to `old.tar.gz`
- `get_max_child_for_parent()` (line 191): `tar -tzf "$ARCHIVE_FILE"` → use `_archive_list()` helper or pipe
- `get_next_task_id()` (line 663): same change

### `tests/test_zip_old.sh` (26 test cases)
This is the largest test file to update.
- Test fixture helpers that create archives: change from `tar -czf` to pipe approach
- Tests 9, 10: archive creation — verify `.tar.zst` files exist instead of `.tar.gz`
- Tests 20-26: unpack — update tar commands in verification
- All `tar -tzf` verification commands → pipe approach
- Path assertions: `.tar.gz` → `.tar.zst`
- Git add assertions: glob pattern changes

## Reference Files
- `archive_utils.sh` (after t470_1) provides `_archive_list()`, `_archive_extract_file()`, `_archive_extract_all()` helpers
- Task t470 description has the command pattern table

## Implementation Plan
1. Update `aitask_zip_old.sh` `_archive_single_bundle()` — this is the core create/merge logic
2. Update `aitask_zip_old.sh` `cmd_unpack()` — extract/rebuild logic
3. Update git staging globs and help text
4. Update `aitask_create.sh` (3 locations — small changes)
5. Update `tests/test_zip_old.sh` — systematically update all 26 tests
6. Run tests: `bash tests/test_zip_old.sh`
7. Run shellcheck: `shellcheck .aitask-scripts/aitask_zip_old.sh .aitask-scripts/aitask_create.sh`

## Verification
- `bash tests/test_zip_old.sh` — all 26 tests pass
- `shellcheck .aitask-scripts/aitask_zip_old.sh .aitask-scripts/aitask_create.sh`
- Manual test: create a small archive with `ait zip-old`, verify it produces `.tar.zst` output
