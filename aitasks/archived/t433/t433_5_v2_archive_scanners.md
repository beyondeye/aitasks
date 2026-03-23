---
priority: high
effort: medium
depends: [t433_1]
issue_type: refactor
status: Done
labels: [task-archive]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-23 09:58
updated_at: 2026-03-23 13:21
completed_at: 2026-03-23 13:21
---

## V2 Archive Scanners

Create `.aitask-scripts/lib/archive_scan_v2.sh` -- a shell library consolidating all
archive-scanning patterns that currently live scattered across `aitask_claim_id.sh`,
`aitask_query_files.sh`, and `aitask_stats.py`. These three scripts each implement
their own tar.gz iteration logic; the v2 library provides a single, well-tested set of
scanner functions that work with the numbered archive scheme (`_bN/oldM.tar.gz`) and
fall back to legacy `old.tar.gz`.

Also create `.aitask-scripts/lib/archive_iter_v2.py` -- the Python equivalent for
`aitask_stats.py`, which needs to iterate all archived markdown files to compute
completion statistics.

### Shell library: `archive_scan_v2.sh`

**Guard variable:** `_AIT_ARCHIVE_SCAN_V2_LOADED`

**Sources:** `terminal_compat.sh`, `archive_utils_v2.sh` (from t433_1)

**Functions:**

1. **`scan_max_task_id_v2(task_dir, archived_dir)`** -- Find the highest task number
   across all archive locations. Iterates:
   - Active task files in `$task_dir`
   - Loose archived files in `$archived_dir`
   - All numbered archives `$archived_dir/_b*/*.tar.gz`
   - Legacy `$archived_dir/old.tar.gz` (fallback)

   Returns: integer (the maximum task ID found, or 0)

   This replaces the `scan_max_task_id()` function in `aitask_claim_id.sh` lines 40-69,
   which currently only scans the single `old.tar.gz`.

2. **`search_archived_task_v2(task_num, archived_dir)`** -- Search for a specific task
   number in archives. Uses O(1) lookup via `archive_path_for_id()` to check the
   correct numbered archive first, then falls back to legacy `old.tar.gz`.

   Returns: `"ARCHIVED_TASK_TAR_GZ:<archive_path>:<match>"` or `"NOT_FOUND"`

   This replaces the `cmd_archived_task()` tar.gz search in `aitask_query_files.sh`
   lines 138-144.

3. **`iter_all_archived_files_v2(archived_dir, callback_cmd)`** -- Iterate every file
   across all numbered archives and legacy archive. For each file, invokes
   `$callback_cmd "$archive_path" "$filename_in_tar"`. This is the shell equivalent
   of what `aitask_stats.py`'s `iter_archived_markdown_files()` does for the tar.gz
   portion.

   This function is primarily for completeness; most callers will use the targeted
   `scan_max_task_id_v2` or `search_archived_task_v2` instead.

### Python library: `archive_iter_v2.py`

**File:** `.aitask-scripts/lib/archive_iter_v2.py`

A standalone Python module providing:

1. **`archive_path_for_id(task_id, archived_dir)`** -- Python equivalent of the shell
   function. Returns `Path` object: `archived_dir/_b{dir}/old{bundle}.tar.gz`.

2. **`iter_numbered_archives(archived_dir)`** -- Yield `(filename, text_content)` tuples
   from all `_bN/oldM.tar.gz` files found under `archived_dir`, using `tarfile` module.
   Skips non-`.md` files. Handles corrupted archives gracefully (log warning, continue).

3. **`iter_legacy_archive(archived_dir)`** -- Yield `(filename, text_content)` from the
   legacy `old.tar.gz` if it exists.

4. **`iter_all_archived_tar_files(archived_dir)`** -- Combines numbered + legacy
   iteration. This is the direct replacement for the `ARCHIVE_TAR` block in
   `aitask_stats.py` lines 599-612.

### Design decisions

- The shell scanner functions accept `task_dir` and `archived_dir` as explicit
  parameters rather than relying on globals, making them testable with overridden
  directories.
- The Python module uses `pathlib.Path` throughout, matching the style of
  `aitask_stats.py`.
- Both libraries sort archives by filename to ensure deterministic iteration order.
- Legacy fallback is always attempted last, so numbered archives take precedence
  during the transition period.

### Verification

- `shellcheck .aitask-scripts/lib/archive_scan_v2.sh` must pass
- Manual test: create temp directories with numbered archives and run
  `scan_max_task_id_v2` to verify it finds IDs across multiple bundles
- Python module: `python -c "from archive_iter_v2 import *; print('OK')"`
