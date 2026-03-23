---
Task: t433_7_migration_swap_docs.md
Parent Task: aitasks/t433_refactor_task_archives.md
Sibling Tasks: aitasks/t433/t433_*_*.md
Worktree: (none — current branch)
Branch: (current)
Base branch: main
---

## Implementation Plan: Migration, Code Swap, and Documentation

### Goal

This is the final task in the t433 series. It performs:
1. Data migration from `old.tar.gz` to numbered archives
2. Code swap of v2 functions into production scripts
3. Existing test updates
4. Website documentation updates
5. Cleanup of v2-suffixed temporary files

### Prerequisites Check

Before starting, verify all prior tasks are complete:

```bash
# All v2 tests must pass
bash tests/test_resolve_v2.sh
bash tests/test_zip_old_v2.sh
bash tests/test_archive_scan_v2.sh

# Existing tests must still pass
bash tests/test_resolve_tar_gz.sh
bash tests/test_claim_id.sh

# All v2 files must exist
ls -la .aitask-scripts/lib/archive_utils_v2.sh
ls -la .aitask-scripts/lib/task_resolve_v2.sh
ls -la .aitask-scripts/lib/archive_scan_v2.sh
ls -la .aitask-scripts/lib/archive_iter_v2.py
ls -la .aitask-scripts/aitask_zip_old_v2.sh
```

If any check fails, stop and resolve the dependency first.

---

## Phase 1: Data Migration

### Step 1: Create migration script

Create a one-time migration script `.aitask-scripts/migrate_to_numbered_archives.sh`
(will be deleted after migration):

```bash
#!/usr/bin/env bash
# migrate_to_numbered_archives.sh - One-time migration from old.tar.gz to numbered archives
# Usage: bash .aitask-scripts/migrate_to_numbered_archives.sh [--dry-run]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/terminal_compat.sh"
source "$SCRIPT_DIR/lib/archive_utils_v2.sh"

DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

migrate_archive() {
    local archive_path="$1"
    local base_dir="$2"
    local prefix="$3"   # "t" or "p"

    if [[ ! -f "$archive_path" ]]; then
        info "No archive at $archive_path — skipping"
        return
    fi

    info "Migrating $archive_path..."

    # Extract to temp
    local tmpdir
    tmpdir=$(mktemp -d)
    tar -xzf "$archive_path" -C "$tmpdir"

    # Group files by bundle
    declare -A bundle_files
    while IFS= read -r f; do
        [[ -z "$f" ]] && continue
        local bname
        bname=$(basename "$f")
        # Extract parent task number
        local num
        num=$(echo "$bname" | grep -oE "^${prefix}[0-9]+" | sed "s/^${prefix}//")
        if [[ -z "$num" ]]; then
            warn "Cannot extract number from: $bname — skipping"
            continue
        fi
        local target
        target=$(archive_path_for_id "$num" "$base_dir")
        if [[ -n "${bundle_files[$target]:-}" ]]; then
            bundle_files[$target]="${bundle_files[$target]}"$'\n'"$f"
        else
            bundle_files[$target]="$f"
        fi
    done < <(find "$tmpdir" -type f -name "*.md" | sed "s|^$tmpdir/||")

    # Create numbered archives
    local bundle_count=0
    for target in "${!bundle_files[@]}"; do
        local staging
        staging=$(mktemp -d)
        while IFS= read -r f; do
            [[ -z "$f" ]] && continue
            mkdir -p "$(dirname "$staging/$f")"
            cp "$tmpdir/$f" "$staging/$f"
        done <<< "${bundle_files[$target]}"

        if $DRY_RUN; then
            local count
            count=$(echo "${bundle_files[$target]}" | grep -c . || true)
            info "  [dry-run] Would create $target ($count files)"
        else
            mkdir -p "$(dirname "$target")"
            tar -czf "$target" -C "$staging" .
            tar -tzf "$target" >/dev/null 2>&1 || die "Verification failed: $target"
            info "  Created $target"
        fi
        rm -rf "$staging"
        ((bundle_count++))
    done

    rm -rf "$tmpdir"

    if ! $DRY_RUN; then
        # Backup original
        cp "$archive_path" "${archive_path}.premigration"
        rm "$archive_path"
        info "Migrated to $bundle_count numbered archives. Backup: ${archive_path}.premigration"
    else
        info "[dry-run] Would migrate to $bundle_count numbered archives"
    fi
}

migrate_archive "aitasks/archived/old.tar.gz" "aitasks/archived" "t"
migrate_archive "aiplans/archived/old.tar.gz" "aiplans/archived" "p"

if ! $DRY_RUN; then
    success "Migration complete."
    echo "Run verification:"
    echo "  bash tests/test_resolve_tar_gz.sh"
    echo "  bash tests/test_claim_id.sh"
fi
```

### Step 2: Run migration

```bash
# Preview
bash .aitask-scripts/migrate_to_numbered_archives.sh --dry-run

# Execute
bash .aitask-scripts/migrate_to_numbered_archives.sh

# Verify
ls -la aitasks/archived/_b*/
ls -la aiplans/archived/_b*/
ls -la aitasks/archived/old.tar.gz.premigration  # backup exists
ls -la aitasks/archived/old.tar.gz 2>/dev/null && echo "ERROR: old.tar.gz still exists" || echo "OK: removed"
```

### Step 3: Commit data migration

```bash
./ait git add aitasks/archived/_b*/
./ait git add aiplans/archived/_b*/
./ait git add -u aitasks/archived/old.tar.gz
./ait git add -u aiplans/archived/old.tar.gz
./ait git commit -m "ait: Migrate old.tar.gz to numbered archives (t433_7)"
```

Keep `.premigration` backups outside of git (add to `.gitignore` or delete after
verifying the migration commit).

---

## Phase 2: Code Swap

### Step 4: Update `task_utils.sh`

**File:** `.aitask-scripts/lib/task_utils.sh`

4a. Add source lines after existing library imports (near line 12):

```bash
# shellcheck source=archive_utils_v2.sh
source "${SCRIPT_DIR}/lib/archive_utils_v2.sh"
# shellcheck source=archive_scan_v2.sh
source "${SCRIPT_DIR}/lib/archive_scan_v2.sh"
```

4b. Replace `resolve_task_file()` implementation. The current function searches
    active -> archived -> single `old.tar.gz`. Replace the `old.tar.gz` block with
    the three-tier logic from `task_resolve_v2.sh`:
    - Keep tiers 1-2 (active + archived loose) unchanged
    - Replace tier 3: call `archive_path_for_id()` to compute the numbered archive
      path, search it with `_search_tar_gz_v2()`, fall back to legacy `old.tar.gz`
    - Extract using `_extract_from_tar_gz_v2()` with the v2 temp dir

4c. Replace `resolve_plan_file()` with same pattern (empty return instead of die).

4d. Remove old internal functions that are now superseded:
    - `_search_tar_gz()` -- replaced by `_search_tar_gz_v2()` from archive_utils_v2.sh
    - `_extract_from_tar_gz()` -- replaced by `_extract_from_tar_gz_v2()`
    - The `ARCHIVE_FILE` / `ARCHIVE_TAR` constant if defined

4e. Remove old temp directory cleanup that's been superseded by the v2 cleanup:
    - `_AIT_TASK_UTILS_TMPDIR` and its trap can be removed once `_AIT_ARCHIVE_V2_TMPDIR`
      handles extraction

**Preserve:** All non-archive functions (`extract_issue_url`, `extract_frontmatter_field`,
`extract_final_implementation_notes`, `task_git`, etc.) remain unchanged.

### Step 5: Update `aitask_zip_old.sh`

**File:** `.aitask-scripts/aitask_zip_old.sh`

Replace the entire content with the content from `aitask_zip_old_v2.sh`. Key changes:
- `source "$SCRIPT_DIR/lib/archive_utils_v2.sh"` added
- `archive_files_v2()` replaces old archiving logic
- `cmd_unpack_v2()` replaces old unpack
- Constants `TASK_ARCHIVE` and `PLAN_ARCHIVE` removed (no longer single files)
- Git add patterns use `_b*/old*.tar.gz` instead of `old.tar.gz`

### Step 6: Update `aitask_claim_id.sh`

**File:** `.aitask-scripts/aitask_claim_id.sh`

6a. Add source at top:
```bash
source "$SCRIPT_DIR/lib/archive_scan_v2.sh"
```

6b. Replace `scan_max_task_id()` function body to delegate to v2:
```bash
scan_max_task_id() {
    scan_max_task_id_v2 "$TASK_DIR" "$ARCHIVED_DIR"
}
```

Or inline the v2 logic directly. The wrapper approach is simpler and preserves the
existing call sites.

6c. Remove `ARCHIVE_FILE` variable (line 35).

### Step 7: Update `aitask_query_files.sh`

**File:** `.aitask-scripts/aitask_query_files.sh`

7a. Add source at top:
```bash
source "$SCRIPT_DIR/lib/archive_scan_v2.sh"
```

7b. In `cmd_archived_task()`, replace lines 138-144 (the `_search_tar_gz` call):

Before:
```bash
    local tar_match
    tar_match=$(_search_tar_gz "$ARCHIVED_DIR/old.tar.gz" "(^|/)t${num}_.*\.md$" || true)
    if [[ -n "$tar_match" ]]; then
        echo "ARCHIVED_TASK_TAR_GZ:$tar_match"
        return
    fi
```

After:
```bash
    local scan_result
    scan_result=$(search_archived_task_v2 "$num" "$ARCHIVED_DIR")
    if [[ "$scan_result" != "NOT_FOUND" ]]; then
        echo "$scan_result"
        return
    fi
```

Note: `search_archived_task_v2` already returns `ARCHIVED_TASK_TAR_GZ:...` format,
so the output protocol is preserved.

### Step 8: Update `aitask_stats.py`

**File:** `.aitask-scripts/aitask_stats.py`

8a. Add import at top (adjust path based on where archive_iter_v2.py lives):
```python
import sys
# Add lib/ to Python path for archive_iter_v2
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))
from archive_iter_v2 import iter_all_archived_tar_files
```

8b. In `iter_archived_markdown_files()`, replace the `ARCHIVE_TAR` block (lines 599-612):

Before:
```python
    if ARCHIVE_TAR.exists():
        try:
            with tarfile.open(ARCHIVE_TAR, "r:gz") as tf:
                for member in tf.getmembers():
                    ...
```

After:
```python
    for name, text in iter_all_archived_tar_files(ARCHIVE_DIR):
        yield name, text
```

8c. Remove `ARCHIVE_TAR` constant (line 27).

8d. The `tarfile` import can remain if it's used elsewhere; if not, remove it.

### Step 9: Commit code swap

```bash
git add .aitask-scripts/lib/task_utils.sh
git add .aitask-scripts/aitask_zip_old.sh
git add .aitask-scripts/aitask_claim_id.sh
git add .aitask-scripts/aitask_query_files.sh
git add .aitask-scripts/aitask_stats.py
git commit -m "refactor: Swap v2 archive functions into production scripts (t433_7)"
```

---

## Phase 3: Update Existing Tests

### Step 10: Update `tests/test_resolve_tar_gz.sh`

The resolve functions now use the v2 archive system internally. Update:

10a. In `setup_test_env()`, optionally create `_bN/` directory structure.

10b. Tests 3, 6, 7, 8 currently create `old.tar.gz` at the root of archived/. These
     should still pass because `resolve_task_file()` now falls back to legacy. But add
     additional test cases that use numbered archives:

- After test 3, add: "Resolve parent task from numbered archive"
- After test 6, add: "Resolve child task from numbered archive"

10c. Run to verify all 14+ tests pass:
```bash
bash tests/test_resolve_tar_gz.sh
```

### Step 11: Run all existing tests

```bash
bash tests/test_claim_id.sh
bash tests/test_resolve_tar_gz.sh
bash tests/test_zip_old.sh       # if exists
bash tests/test_detect_env.sh
bash tests/test_draft_finalize.sh
bash tests/test_task_lock.sh
bash tests/test_terminal_compat.sh
bash tests/test_setup_git.sh
bash tests/test_resolve_detected_agent.sh
bash tests/test_verified_update_flags.sh
bash tests/test_sed_compat.sh
bash tests/test_global_shim.sh
bash tests/test_t167_integration.sh
```

All must pass. Fix any regressions.

---

## Phase 4: Website Documentation

### Step 12: Update `website/content/docs/commands/issue-integration.md`

**Lines 152-179** (the `ait zip-old` section). Replace the "How it works" block:

```markdown
**How it works:**

1. Scans `aitasks/archived/` and `aiplans/archived/` for parent and child files
2. Keeps the most recent parent file and most recent child (per parent) uncompressed — this preserves task numbering for `ait create`
3. Groups eligible files by 100-task bundles and archives each group to a numbered archive:
   - **Bundle** = `task_id / 100` (integer division)
   - **Directory** = `bundle / 10` (integer division)
   - **Path** = `archived/_b{dir}/old{bundle}.tar.gz`
   - Example: task 150 → `archived/_b0/old1.tar.gz`, task 1050 → `archived/_b1/old10.tar.gz`
4. If a numbered archive already exists, merges new files into it
5. Verifies archive integrity before deleting originals
6. If an existing archive is corrupted, creates a backup before starting fresh
7. Removes empty child directories after archiving
8. Commits changes to git (unless `--no-commit`)
```

### Step 13: Update `website/content/docs/commands/board-stats.md`

**Line 81.** Replace:
```
and compressed archives (`old.tar.gz`)
```
With:
```
and compressed archives (numbered `_bN/oldM.tar.gz` bundles)
```

### Step 14: Update `website/content/docs/development/task-format.md`

Add a new section after "Parent-Child Hierarchies" (after line 79):

```markdown
---

## Archive Storage

Completed tasks move through the archive lifecycle:

1. **Archived directory** — `aitasks/archived/t150_feature.md` (loose files, recent)
2. **Numbered archives** — `aitasks/archived/_b0/old1.tar.gz` (compressed bundles)

The numbering scheme groups tasks by hundreds:

| Task IDs | Bundle | Directory | Archive Path |
|----------|--------|-----------|-------------|
| 0–99 | 0 | 0 | `archived/_b0/old0.tar.gz` |
| 100–199 | 1 | 0 | `archived/_b0/old1.tar.gz` |
| 900–999 | 9 | 0 | `archived/_b0/old9.tar.gz` |
| 1000–1099 | 10 | 1 | `archived/_b1/old10.tar.gz` |

**Computation:**
- `bundle = task_id / 100` (integer division)
- `directory = bundle / 10` (integer division)
- `path = archived/_b{directory}/old{bundle}.tar.gz`

The `_b` prefix on directory names avoids collision with task child directories (`t<N>/`).

Child tasks are archived with their parent's bundle (e.g., `t130/t130_2_subtask.md` goes into `old1.tar.gz` alongside `t130_feature.md`).

Plan archives follow the same scheme under `aiplans/archived/`.
```

### Step 15: Update `website/content/docs/development/_index.md`

15a. In the Directory Layout table, add after the `aitasks/archived/` row:

```markdown
| `aitasks/archived/_bN/` | Numbered archive bundles (`old0.tar.gz` through `old9.tar.gz` per directory) |
```

15b. In the Library Scripts section, add entries for the new libraries:

```markdown
### lib/archive_utils.sh

Archive path computation and search/extract primitives for the numbered archive scheme.

**Functions:**

- **`archive_bundle(task_id)`** — Compute bundle number (task_id / 100)
- **`archive_dir(bundle)`** — Compute directory number (bundle / 10)
- **`archive_path_for_id(task_id, archived_dir)`** — Full archive path for a task ID

### lib/archive_scan.sh

Consolidated archive scanning functions.

**Functions:**

- **`scan_max_task_id_v2(task_dir, archived_dir)`** — Find highest task ID across all locations
- **`search_archived_task_v2(task_num, archived_dir)`** — Search for a task in numbered and legacy archives
```

15c. Update `resolve_task_file` and `resolve_plan_file` descriptions to mention
     numbered archive search as the third tier.

### Step 16: Verify website builds

```bash
cd website && hugo build --gc --minify
```

No build errors. Spot-check the updated pages in the output.

### Step 17: Commit documentation

```bash
git add website/content/docs/commands/issue-integration.md
git add website/content/docs/commands/board-stats.md
git add website/content/docs/development/task-format.md
git add website/content/docs/development/_index.md
git commit -m "documentation: Update website docs for numbered archive scheme (t433_7)"
```

---

## Phase 5: Cleanup

### Step 18: Remove v2-suffixed files

```bash
# Files merged into production counterparts
rm .aitask-scripts/lib/task_resolve_v2.sh
rm .aitask-scripts/aitask_zip_old_v2.sh

# Tests merged into updated existing tests
rm tests/test_resolve_v2.sh
rm tests/test_zip_old_v2.sh
```

### Step 19: Rename libraries (drop `_v2` suffix)

```bash
git mv .aitask-scripts/lib/archive_utils_v2.sh .aitask-scripts/lib/archive_utils.sh
git mv .aitask-scripts/lib/archive_scan_v2.sh .aitask-scripts/lib/archive_scan.sh
git mv .aitask-scripts/lib/archive_iter_v2.py .aitask-scripts/lib/archive_iter.py
git mv tests/test_archive_scan_v2.sh tests/test_archive_scan.sh
```

Update all references:
- `task_utils.sh`: `source "${SCRIPT_DIR}/lib/archive_utils.sh"` (drop `_v2`)
- `task_utils.sh`: `source "${SCRIPT_DIR}/lib/archive_scan.sh"` (drop `_v2`)
- `aitask_claim_id.sh`: source line
- `aitask_query_files.sh`: source line
- `aitask_stats.py`: import line
- `aitask_zip_old.sh`: source line
- Guard variables: `_AIT_ARCHIVE_UTILS_V2_LOADED` -> `_AIT_ARCHIVE_UTILS_LOADED`, etc.
- Inside the renamed files: update guard variable names
- `CLAUDE.md`: update test list to use new names

### Step 20: Remove migration artifacts

```bash
rm .aitask-scripts/migrate_to_numbered_archives.sh
rm -f aitasks/archived/old.tar.gz.premigration
rm -f aiplans/archived/old.tar.gz.premigration
```

### Step 21: Final verification

```bash
# All tests
bash tests/test_resolve_tar_gz.sh
bash tests/test_claim_id.sh
bash tests/test_archive_scan.sh

# ShellCheck
shellcheck .aitask-scripts/aitask_*.sh
shellcheck .aitask-scripts/lib/archive_utils.sh
shellcheck .aitask-scripts/lib/archive_scan.sh

# Website
cd website && hugo build --gc --minify

# End-to-end
./ait zip-old --dry-run
./ait create --batch --name "test_cleanup_verify" --priority low
./ait query-files archived-task 1   # should search numbered archives
```

### Step 22: Commit cleanup

```bash
git add -u .aitask-scripts/ tests/ CLAUDE.md
git commit -m "chore: Remove v2-suffixed files after migration (t433_7)"
```

### Step 23: Update CLAUDE.md

Update the Testing section to reflect renamed test files:
- Remove `test_resolve_v2.sh`, `test_zip_old_v2.sh`
- Add `test_archive_scan.sh`

Update the Architecture section Key Directories if archive paths are mentioned.

---

## Verification Results (2026-03-23)

**Phases 1-3 are already complete (done by siblings + previous attempt):**

- **Phase 1 (Data Migration):** Verified correct. `old.tar.gz.premigration` backups exist.
  All 383 task files and 358 plan files migrated to numbered archives with correct bundle
  placement (old0=t0-99, old1=t100-199, old2=t200-299, old3=t300-399) and identical checksums.
  No `old.tar.gz` remaining.
- **Phase 2 (Code Swap):** All production scripts already use v2 functions:
  - `task_utils.sh` sources `archive_utils_v2.sh`, uses v2 resolve logic
  - `aitask_claim_id.sh` sources `archive_scan_v2.sh`, delegates to `scan_max_task_id_v2()`
  - `aitask_query_files.sh` sources `archive_scan_v2.sh`, uses `search_archived_task_v2()`
  - `aitask_stats.py` imports `archive_iter_v2`
  - `aitask_zip_old.sh` identical to `aitask_zip_old_v2.sh`
  - `task_resolve_v2.sh` is dead code (never sourced by anything)
- **Phase 3 (Tests):** All pass:
  - test_resolve_v2: 15/15, test_zip_old_v2: 28/28, test_archive_scan_v2: 23/23
  - test_resolve_tar_gz: 14/14, test_claim_id: 23/23
  - Additional file found: `tests/test_archive_utils_v2.sh` (not in original plan)

**Remaining work:** Phase 4 (website docs) and Phase 5 (v2 file cleanup/rename).
See detailed plan in steps above. Key changes:
- Skip Steps 1-11 (migration + code swap + test updates — already done)
- Start from Step 12 (website docs)
- Then Step 18-23 (cleanup, rename, final verification)

---

## Post-Implementation

### Step 24: Final Implementation Notes

_(To be filled in after implementation)_

- **Actual files created/modified:**
- **Issues encountered:**
- **Deviations from plan:**
- **ShellCheck result:**
- **All test results:**
- **Website build result:**
- **Premigration backup status:** (kept/deleted)
