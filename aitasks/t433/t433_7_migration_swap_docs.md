---
priority: medium
effort: high
depends: [t433_6]
issue_type: refactor
status: Implementing
labels: [task-archive]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-23 09:59
updated_at: 2026-03-23 14:27
---

## Migration, Code Swap, and Documentation Update

This is the final task in the t433 refactoring series. It performs the actual migration
from the single `old.tar.gz` archive to the numbered archive scheme, swaps v2 functions
into all production scripts, updates existing tests, updates website documentation, and
cleans up the temporary v2-suffixed files.

### Prerequisites

All sibling tasks (t433_1 through t433_6) must be complete and their tests passing.
The v2 libraries must exist and be functional:
- `.aitask-scripts/lib/archive_utils_v2.sh`
- `.aitask-scripts/lib/task_resolve_v2.sh`
- `.aitask-scripts/lib/archive_scan_v2.sh`
- `.aitask-scripts/lib/archive_iter_v2.py`
- `.aitask-scripts/aitask_zip_old_v2.sh`

### Phase 1: Data Migration

Extract the existing `old.tar.gz` archives and redistribute their contents into
numbered archives using the bundle scheme from t433_1.

**Steps:**

1. Extract `aitasks/archived/old.tar.gz` to a temp directory
2. For each `.md` file, extract the parent task number from the filename
   (e.g., `t150_feature.md` -> 150, `t130/t130_2_subtask.md` -> 130)
3. Compute the target archive path via `archive_path_for_id()`
4. Group files by target archive and create each `_bN/oldM.tar.gz`
5. Verify all numbered archives with `tar -tzf`
6. Repeat for `aiplans/archived/old.tar.gz`
7. Remove the original `old.tar.gz` files only after verification passes
8. Commit the data migration separately:
   `ait git commit -m "ait: Migrate old.tar.gz to numbered archives (t433_7)"`

**Safety:** If the project has no `old.tar.gz` (new project or already empty), skip
this phase gracefully. Back up `old.tar.gz` as `old.tar.gz.premigration` before
removal.

### Phase 2: Code Swap

Replace current functions with v2 equivalents in production scripts.

**2a. `task_utils.sh`:**
- Add `source "${SCRIPT_DIR}/lib/archive_utils_v2.sh"` after existing library sources
- Add `source "${SCRIPT_DIR}/lib/archive_scan_v2.sh"`
- Replace `resolve_task_file()` body with the logic from `resolve_task_file_v2()`
  (three-tier: active -> archived -> numbered archives with legacy fallback)
- Replace `resolve_plan_file()` body with the logic from `resolve_plan_file_v2()`
- Remove `_search_tar_gz()` and `_extract_from_tar_gz()` -- replaced by v2 equivalents
- Remove `ARCHIVE_FILE` / `old.tar.gz` hardcoded path references
- Keep `_AIT_TASK_UTILS_LOADED` guard variable unchanged

**2b. `aitask_zip_old.sh`:**
- Replace entire script content with `aitask_zip_old_v2.sh` content
- Keep the original filename (`aitask_zip_old.sh`)
- Update the `ait` dispatcher if needed (it should already route `zip-old` to this file)

**2c. `aitask_claim_id.sh`:**
- Replace `scan_max_task_id()` with `scan_max_task_id_v2()` from `archive_scan_v2.sh`
- Source `archive_scan_v2.sh` at the top
- Remove the local `ARCHIVE_FILE` variable

**2d. `aitask_query_files.sh`:**
- Replace the tar.gz search in `cmd_archived_task()` (lines 138-144) with
  `search_archived_task_v2()` from `archive_scan_v2.sh`
- Source `archive_scan_v2.sh` at the top
- Remove `_search_tar_gz` direct calls

**2e. `aitask_stats.py`:**
- Import `archive_iter_v2` (add to `sys.path` if needed, or copy module to same dir)
- Replace `ARCHIVE_TAR` reference and the `tarfile.open` block in
  `iter_archived_markdown_files()` with a call to
  `iter_all_archived_tar_files(ARCHIVE_DIR)`
- Remove the `ARCHIVE_TAR` constant

### Phase 3: Update Existing Tests

**`tests/test_resolve_tar_gz.sh`:**
- Update `setup_test_env()` to create `_bN/` directories alongside `old.tar.gz`
- Update tests 3, 6, 7, 8 (tar.gz extraction tests) to use numbered archives
  as the primary archive, with legacy as fallback test
- Add tests for the cross-archive-format transition case
- Ensure all 14 existing tests still pass with the swapped functions

**`tests/test_zip_old.sh`** (if exists):
- Update to verify files go to `_bN/oldM.tar.gz` instead of single `old.tar.gz`

### Phase 4: Website Documentation

Update 4 pages:

**4a. `website/content/docs/commands/issue-integration.md` (lines 152-179):**
- Update "How it works" section for `ait zip-old`
- Replace "Archives all older files to `old.tar.gz`" with numbered bundle explanation
- Document the `_bN/oldM.tar.gz` naming scheme
- Keep the unpack subcommand documentation; update that it searches numbered archives

**4b. `website/content/docs/commands/board-stats.md` (line 81):**
- Update "Data sources" sentence to mention numbered archives:
  `"...and compressed archives (numbered _bN/oldM.tar.gz bundles)"`
  instead of `"...and compressed archives (old.tar.gz)"`

**4c. `website/content/docs/development/task-format.md`:**
- Add a section "Archive Storage" after "Parent-Child Hierarchies" explaining:
  - The numbered archive scheme
  - Bundle computation: `bundle = task_id / 100`
  - Directory computation: `dir = bundle / 10`
  - Path format: `archived/_b{dir}/old{bundle}.tar.gz`
  - Example mappings (task 50 -> `_b0/old0.tar.gz`, task 1050 -> `_b1/old10.tar.gz`)

**4d. `website/content/docs/development/_index.md`:**
- Update the Directory Layout table: add `aitasks/archived/_bN/` row for numbered
  archive bundles
- Update the Library Scripts section: add entries for `archive_utils_v2.sh`,
  `archive_scan_v2.sh`, and `archive_iter_v2.py`
- Update `resolve_task_file()` and `resolve_plan_file()` descriptions to mention
  numbered archive search

### Phase 5: Cleanup

1. Remove v2-suffixed files that have been merged into production:
   - `.aitask-scripts/lib/task_resolve_v2.sh` (merged into `task_utils.sh`)
   - `.aitask-scripts/aitask_zip_old_v2.sh` (merged into `aitask_zip_old.sh`)
2. Rename v2 libraries to drop the `_v2` suffix (optional -- only if cleaner):
   - `archive_utils_v2.sh` -> `archive_utils.sh`
   - `archive_scan_v2.sh` -> `archive_scan.sh`
   - `archive_iter_v2.py` -> `archive_iter.py`
   - Update all source/import references accordingly
   - Update guard variables accordingly
3. Remove v2-specific integration tests that are now redundant:
   - `tests/test_resolve_v2.sh` (covered by updated `test_resolve_tar_gz.sh`)
   - `tests/test_zip_old_v2.sh` (covered by updated `test_zip_old.sh`)
   - Keep `tests/test_archive_scan_v2.sh` renamed to `tests/test_archive_scan.sh`
4. Update `CLAUDE.md` Testing section if test filenames changed

### Verification

1. Run all existing tests:
   ```bash
   bash tests/test_resolve_tar_gz.sh
   bash tests/test_claim_id.sh
   bash tests/test_zip_old.sh
   ```
2. Run any remaining v2 tests
3. `shellcheck .aitask-scripts/aitask_*.sh`
4. `shellcheck .aitask-scripts/lib/archive_*.sh`
5. Manual end-to-end: `./ait zip-old --dry-run` on a real project
6. Website: `cd website && hugo build --gc --minify` -- no build errors
7. Verify `./ait create` still assigns correct next task ID
8. Verify `./ait query-files archived-task <N>` finds tasks in numbered archives

### Commit Strategy

Recommend 3 separate commits:
1. `ait: Migrate old.tar.gz data to numbered archives (t433_7)`
2. `refactor: Swap v2 archive functions into production scripts (t433_7)`
3. `documentation: Update website docs for numbered archive scheme (t433_7)`

Followed by cleanup commit:
4. `chore: Remove v2-suffixed files after migration (t433_7)`
