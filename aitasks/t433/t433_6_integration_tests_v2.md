---
priority: medium
effort: medium
depends: [433_3, 433_4, 433_5]
issue_type: test
status: Ready
labels: [task-archive]
created_at: 2026-03-23 09:58
updated_at: 2026-03-23 09:58
---

## Integration Tests for V2 Archive System

Create three test files exercising the v2 archive libraries end-to-end. These tests
verify that the resolve, zip-old, and scanner functions work correctly with the numbered
archive scheme (`_bN/oldM.tar.gz`), handle legacy `old.tar.gz` fallback, and behave
correctly at boundary conditions.

All tests follow the project's established pattern from `tests/test_resolve_tar_gz.sh`:
self-contained bash scripts with `assert_eq`/`assert_contains` helpers, temp directories,
and PASS/FAIL summary.

### Test file 1: `tests/test_resolve_v2.sh`

Tests for `resolve_task_file_v2()` and `resolve_plan_file_v2()` from
`.aitask-scripts/lib/task_resolve_v2.sh`.

**Test cases:**

1. **Resolve parent task from active dir** -- file in `$TASK_DIR/t50_*.md`
2. **Resolve parent task from archived dir** -- file in `$ARCHIVED_DIR/t50_*.md`
3. **Resolve parent task from numbered archive** -- file in
   `$ARCHIVED_DIR/_b0/old0.tar.gz`, extracted to temp
4. **Resolve child task from numbered archive** -- child `t130_2_*.md` in
   `$ARCHIVED_DIR/_b0/old1.tar.gz` (bundle 1, task 130)
5. **Resolve task from legacy old.tar.gz** -- numbered archive missing, falls back to
   `$ARCHIVED_DIR/old.tar.gz`
6. **Priority: active wins over numbered archive** -- both exist, active returned
7. **Priority: archived loose wins over archive** -- both exist, loose file returned
8. **Priority: numbered archive wins over legacy** -- both contain the file, numbered
   archive result returned
9. **Resolve plan from numbered archive** -- plan `p200_*.md` in
   `$ARCHIVED_PLAN_DIR/_b0/old2.tar.gz`
10. **Resolve plan from legacy fallback** -- plan in `$ARCHIVED_PLAN_DIR/old.tar.gz`
11. **Not found -- parent task dies** -- exits non-zero when task absent everywhere
12. **Not found -- plan returns empty** -- returns empty string, no error
13. **Temp file cleanup** -- extracted temp dir removed after shell exit
14. **Cross-bundle boundary** -- task 99 in `old0.tar.gz`, task 100 in `old1.tar.gz`

**Structure:**
- Reuse `setup_test_env()`, `create_test_archive()`, `source_task_utils()` helpers
  from `test_resolve_tar_gz.sh`
- Add `create_numbered_archive()` helper: creates `_bN/oldM.tar.gz` given task ID
  and staging directory
- Source `task_resolve_v2.sh` instead of (or in addition to) `task_utils.sh`

### Test file 2: `tests/test_zip_old_v2.sh`

Tests for `aitask_zip_old_v2.sh` from t433_4.

**Test cases:**

1. **Single task archived to correct bundle** -- task t50 -> `_b0/old0.tar.gz`
2. **Multiple tasks split across bundles** -- t50 and t150 -> `old0` and `old1`
3. **Child tasks archived with parent bundle** -- `t130/t130_2_*.md` -> `old1`
4. **Plans archived to separate plan bundles** -- `p200_*.md` -> plan `_b0/old2.tar.gz`
5. **Merge with existing numbered archive** -- pre-existing `old0.tar.gz` + new files
6. **Archive verification** -- `tar -tzf` on result matches expected entries
7. **Original files removed after archiving** -- source files gone, archive exists
8. **Empty child directories cleaned up** -- `t130/` removed after children archived
9. **Dry run produces no changes** -- `--dry-run` flag leaves filesystem untouched
10. **Unpack from numbered archive** -- `unpack 50` restores file from `_b0/old0.tar.gz`
11. **Unpack from legacy archive** -- `unpack 50` falls back to `old.tar.gz`
12. **Unpack removes file from archive** -- archive is rebuilt without extracted file
13. **High task IDs** -- t1050 -> `_b1/old10.tar.gz` (dir 1, bundle 10)
14. **Corrupted archive backup** -- pre-existing corrupt archive renamed `.bak`

**Structure:**
- Each test creates an isolated temp directory with `aitasks/archived/` and
  `aiplans/archived/`
- Override `TASK_ARCHIVED_DIR`, `PLAN_ARCHIVED_DIR` before calling the script
- Run the v2 script via `bash .aitask-scripts/aitask_zip_old_v2.sh --no-commit`
- Verify with `tar -tzf` and filesystem checks

### Test file 3: `tests/test_archive_scan_v2.sh`

Tests for `archive_scan_v2.sh` from t433_5.

**Test cases:**

1. **scan_max_task_id_v2 -- active only** -- max from `$TASK_DIR/t200_*.md` = 200
2. **scan_max_task_id_v2 -- archived loose** -- max from `$ARCHIVED_DIR/t300_*.md` = 300
3. **scan_max_task_id_v2 -- single numbered archive** -- max from `old3.tar.gz`
   containing t350 = 350
4. **scan_max_task_id_v2 -- multiple numbered archives** -- archives old0 (max 90),
   old1 (max 180), old2 (max 250) -> overall max 250
5. **scan_max_task_id_v2 -- legacy fallback** -- no numbered archives, old.tar.gz
   contains t400 -> max 400
6. **scan_max_task_id_v2 -- mixed** -- active t500, numbered archive t350, legacy t200
   -> max 500
7. **scan_max_task_id_v2 -- empty** -- no tasks anywhere -> 0
8. **search_archived_task_v2 -- found in numbered archive** -- task 150 in
   `_b0/old1.tar.gz` -> returns match
9. **search_archived_task_v2 -- found in legacy** -- task 150 in `old.tar.gz` -> returns
   match
10. **search_archived_task_v2 -- not found** -- returns `NOT_FOUND`
11. **search_archived_task_v2 -- O(1) lookup correctness** -- task 150 only checks
    `old1.tar.gz`, not `old0.tar.gz` (verify by absence of `old0.tar.gz`)
12. **iter_all_archived_files_v2 -- collects from multiple archives** -- callback
    accumulates all filenames across 3 numbered archives + legacy

**Structure:**
- Same helper pattern as other test files
- Create `setup_numbered_archive()` helper to build `_bN/oldM.tar.gz` with specified
  task files
- Source `archive_scan_v2.sh` with overridden directories

### Run instructions

```bash
bash tests/test_resolve_v2.sh
bash tests/test_zip_old_v2.sh
bash tests/test_archive_scan_v2.sh
```

Each file is self-contained and prints a PASS/FAIL summary at the end. Non-zero exit
on any failure.
