---
priority: high
effort: medium
depends: [t433_1]
issue_type: refactor
status: Implementing
labels: [task-archive]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-23 09:58
updated_at: 2026-03-23 12:28
---

## Context

Parent task t433 is refactoring the task archive system from a single `old.tar.gz` to numbered archives. The current `aitask_zip_old.sh` (518 lines) archives all eligible files into a single `$ARCHIVED_DIR/old.tar.gz`. This task creates a v2 version that groups files by their archive bundle and writes each group to the correct numbered archive path:

```
bundle = task_id / 100       (integer division)
dir    = bundle / 10          (integer division)
path   = archived/_b{dir}/old{bundle}.tar.gz
```

For example, task t253 goes to `archived/_b0/old2.tar.gz` (bundle=2, dir=0), and task t1250 goes to `archived/_b1/old12.tar.gz` (bundle=12, dir=1).

The v2 script is a separate file so that the current zip-old continues to work during development. The migration task (t433_7) will swap it in.

## Key Files to Modify

- `.aitask-scripts/aitask_zip_old_v2.sh` (new) -- v2 zip-old with numbered archive output

## Reference Files for Patterns

- `.aitask-scripts/aitask_zip_old.sh` lines 148-214 -- `collect_files_to_archive()` selection logic (reuse as-is)
- `.aitask-scripts/aitask_zip_old.sh` lines 218-291 -- `archive_files()` single-archive creation
- `.aitask-scripts/aitask_zip_old.sh` lines 298-358 -- `cmd_unpack()` extraction from single archive
- `.aitask-scripts/aitask_zip_old.sh` lines 360-518 -- `main()` with CLI parsing, dry-run, commit logic
- `.aitask-scripts/lib/archive_utils_v2.sh` (t433_1) -- `archive_bundle()`, `archive_dir()`, `archive_path_for_id()`
- `.aitask-scripts/lib/task_utils.sh` -- `task_git()`, directory defaults, helper patterns

## Implementation Plan

### Step 1: Script skeleton and constants

Create `.aitask-scripts/aitask_zip_old_v2.sh`:

```bash
#!/usr/bin/env bash
# aitask_zip_old_v2.sh - Archive old task and plan files to numbered tar.gz archives
# Groups files by 100-task bundles into _bN/oldM.tar.gz

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/terminal_compat.sh"
source "$SCRIPT_DIR/lib/task_utils.sh"
source "$SCRIPT_DIR/lib/archive_utils_v2.sh"

# --- Constants ---
TASK_ARCHIVED_DIR="aitasks/archived"
PLAN_ARCHIVED_DIR="aiplans/archived"

# --- Flags ---
DRY_RUN=false
NO_COMMIT=false
VERBOSE=false
```

### Step 2: Argument parsing and usage

Copy `usage()`, `parse_args()`, `verbose()` from the v1 script. The CLI is identical:

```
Usage: aitask_zip_old_v2.sh [OPTIONS]
       aitask_zip_old_v2.sh unpack <task_number>

Options:
  -n, --dry-run    Show what would be archived without making changes
  --no-commit      Archive files but don't commit to git
  -v, --verbose    Show detailed progress output
  -h, --help       Show this help message
```

### Step 3: Reuse selection logic

Copy these functions from v1 without modification -- they are archive-format-agnostic:

- `get_active_parent_numbers()` -- lists parent numbers with active children
- `get_dependency_task_ids()` -- collects dependency IDs from active tasks
- `is_parent_active()` -- checks if a parent has active children
- `is_dependency()` -- checks if a task ID is depended upon
- `collect_files_to_archive()` -- scans archived dir for eligible files, applying skip rules

These functions operate on loose files in the archived directory and have no knowledge of the tar.gz format.

### Step 4: Implement archive_files_v2()

This is the core change. Instead of appending all files to one archive, group by bundle:

```bash
# Archive files to numbered tar.gz bundles
# Args: $1=files (newline-separated, relative to base_dir), $2=base_dir, $3=prefix (t or p)
# Returns: number of files archived
archive_files_v2() {
    local files="$1"
    local base_dir="$2"
    local prefix="$3"
    local total_count=0

    [[ -z "$files" ]] && { echo "0"; return 0; }

    # Group files by archive bundle
    # Uses an associative array: key=archive_path, value=newline-separated file list
    declare -A bundle_groups

    while IFS= read -r f; do
        [[ -z "$f" ]] && continue
        local basename_f
        basename_f=$(basename "$f")

        # Extract parent task number from filename
        # Parent file: t100_name.md -> 100
        # Child file (in subdir): t129/t129_3_name.md -> 129
        local parent_num
        parent_num=$(echo "$basename_f" | sed "s/^${prefix}\([0-9]*\).*/\1/")

        local archive_path
        archive_path=$(archive_path_for_id "$base_dir" "$parent_num")

        if [[ -n "${bundle_groups[$archive_path]:-}" ]]; then
            bundle_groups[$archive_path]="${bundle_groups[$archive_path]}"$'\n'"$f"
        else
            bundle_groups[$archive_path]="$f"
        fi
    done <<< "$files"

    # Archive each bundle group
    for archive_path in "${!bundle_groups[@]}"; do
        local group_files="${bundle_groups[$archive_path]}"
        local dir
        dir=$(dirname "$archive_path")
        mkdir -p "$dir"

        # Reuse the single-archive logic for each bundle
        local count
        count=$(_archive_single_bundle "$archive_path" "$group_files" "$base_dir")
        ((total_count += count))
    done

    echo "$total_count"
}
```

### Step 5: Implement _archive_single_bundle()

Extract the per-archive logic from v1's `archive_files()`:

```bash
# Archive a group of files into a single tar.gz (create or append)
# Args: $1=archive_path, $2=files (newline-separated), $3=base_dir
# Returns: number of files added
_archive_single_bundle() {
    local archive_path="$1"
    local files="$2"
    local base_dir="$3"

    local temp_dir
    temp_dir=$(mktemp -d)
    trap "rm -rf '$temp_dir'" RETURN

    # If archive exists, extract it first to merge
    if [[ -f "$archive_path" ]]; then
        verbose "Extracting existing archive: $archive_path"
        if ! tar -xzf "$archive_path" -C "$temp_dir" 2>/dev/null; then
            warn "Warning: Existing archive appears corrupted. Creating backup."
            mv "$archive_path" "${archive_path}.bak"
            info "Backup saved as ${archive_path}.bak"
        fi
    fi

    # Copy new files to temp directory
    local count=0
    while IFS= read -r f; do
        [[ -z "$f" ]] && continue
        local src_path="$base_dir/$f"
        local dest_path="$temp_dir/$f"
        mkdir -p "$(dirname "$dest_path")"
        if [[ -f "$src_path" ]]; then
            verbose "Adding to archive: $f -> $(basename "$archive_path")"
            cp "$src_path" "$dest_path"
            ((count++))
        fi
    done <<< "$files"

    # Create archive
    verbose "Creating archive: $archive_path ($count files)"
    tar -czf "$archive_path" -C "$temp_dir" .

    # Verify integrity
    if ! tar -tzf "$archive_path" > /dev/null 2>&1; then
        die "Archive verification failed for $archive_path! Original files NOT deleted."
    fi

    # Delete originals
    while IFS= read -r f; do
        [[ -z "$f" ]] && continue
        local src_path="$base_dir/$f"
        if [[ -f "$src_path" ]]; then
            verbose "Removing original: $src_path"
            rm "$src_path"
            # Remove parent directory if empty
            local parent_dir
            parent_dir=$(dirname "$src_path")
            if [[ -d "$parent_dir" && "$parent_dir" != "$base_dir" ]]; then
                rmdir "$parent_dir" 2>/dev/null || true
            fi
        fi
    done <<< "$files"

    echo "$count"
}
```

### Step 6: Implement cmd_unpack_v2()

Instead of searching a single `old.tar.gz`, compute the exact archive path:

```bash
# Extract a task (and its children/plans) from numbered archives back to the filesystem.
# Falls back to legacy old.tar.gz if not found in numbered archive.
# Args: $1=task_number
cmd_unpack_v2() {
    local num="$1"
    local found=false

    # Process each archive type: (base_dir, dest_dir, prefix, output_tag)
    local archive_types=(
        "$TASK_ARCHIVED_DIR|$TASK_ARCHIVED_DIR|t|UNPACKED_TASK"
        "$PLAN_ARCHIVED_DIR|$PLAN_ARCHIVED_DIR|p|UNPACKED_PLAN"
    )

    for entry in "${archive_types[@]}"; do
        IFS='|' read -r base_dir dest_dir prefix output_tag <<< "$entry"

        # Compute the numbered archive path for this task
        local archive_path
        archive_path=$(archive_path_for_id "$base_dir" "$num")

        # Also check legacy path
        local legacy_path="$base_dir/old.tar.gz"

        # Try numbered archive first, then legacy
        local search_archives=()
        [[ -f "$archive_path" ]] && search_archives+=("$archive_path")
        [[ -f "$legacy_path" ]] && search_archives+=("$legacy_path")

        for arch in "${search_archives[@]}"; do
            local matches
            matches=$(tar -tzf "$arch" 2>/dev/null | grep -E "(^|/)${prefix}${num}_[^/]*\.md$|(^|/)${prefix}${num}/${prefix}${num}_[^/]*\.md$" || true)
            [[ -z "$matches" ]] && continue

            local temp_dir
            temp_dir=$(mktemp -d)
            tar -xzf "$arch" -C "$temp_dir"

            while IFS= read -r match; do
                [[ -z "$match" ]] && continue
                local src="$temp_dir/$match"
                [[ -f "$src" ]] || continue
                local clean_match="${match#./}"
                local dest="$dest_dir/$clean_match"
                mkdir -p "$(dirname "$dest")"
                cp "$src" "$dest"
                rm "$src"
                echo "${output_tag}:${dest}"
                found=true
            done <<< "$matches"

            # Remove empty subdirectories from temp
            find "$temp_dir" -mindepth 1 -type d -empty -delete 2>/dev/null || true

            # Rebuild or delete archive
            local remaining
            remaining=$(find "$temp_dir" -type f 2>/dev/null | head -1)
            if [[ -z "$remaining" ]]; then
                rm "$arch"
            else
                tar -czf "$arch" -C "$temp_dir" .
            fi

            rm -rf "$temp_dir"

            # If found in this archive, skip remaining archives for this type
            [[ "$found" == true ]] && break
        done
    done

    if [[ "$found" == false ]]; then
        echo "NOT_IN_ARCHIVE"
    fi
}
```

### Step 7: Implement main() with v2 archive calls

Follows the same flow as v1 `main()`:

1. Check for `unpack` subcommand -> call `cmd_unpack_v2`
2. `parse_args "$@"`
3. Compute `ACTIVE_PARENTS` and `DEPENDENCY_IDS`
4. `collect_files_to_archive` for tasks and plans (unchanged)
5. Dry-run: show files grouped by target bundle archive (enhanced output)
6. Archive: call `archive_files_v2` instead of `archive_files`
7. Git commit: `task_git add` all `_b*/old*.tar.gz` files plus removed files

Key difference in dry-run output -- show bundle grouping:

```bash
if $DRY_RUN; then
    # Group files by bundle for display
    echo ""
    info "Files that would be archived (by bundle):"
    # ... show each bundle group with its target archive path
fi
```

Key difference in git commit:

```bash
if ! $NO_COMMIT; then
    # Add all numbered archive files that were created/updated
    task_git add "$TASK_ARCHIVED_DIR"/_b*/old*.tar.gz 2>/dev/null || true
    task_git add "$PLAN_ARCHIVED_DIR"/_b*/old*.tar.gz 2>/dev/null || true
    task_git add -u "$TASK_ARCHIVED_DIR/" "$PLAN_ARCHIVED_DIR/" 2>/dev/null || true
    # ... commit message lists affected bundles
fi
```

### Step 8: Enhanced dry-run display

The v2 dry-run should show which bundle each file goes to:

```
=== DRY RUN MODE ===

Files that would be archived (by bundle):

Tasks:
  aitasks/archived/_b0/old1.tar.gz (tasks 100-199):
    - t129/t129_3_name.md
    - t150_old_feature.md
  aitasks/archived/_b0/old2.tar.gz (tasks 200-299):
    - t253_another.md

Plans:
  aiplans/archived/_b0/old1.tar.gz (plans 100-199):
    - p129/p129_3_name.md
```

## Verification Steps

1. **Shellcheck passes:** `shellcheck .aitask-scripts/aitask_zip_old_v2.sh`
2. **Source test:** Verify script loads without errors
3. **Dry-run test:** Create test loose files in `archived/`, run with `--dry-run`, verify correct bundle assignments:
   - Task t50 -> `_b0/old0.tar.gz`
   - Task t150 -> `_b0/old1.tar.gz`
   - Task t1050 -> `_b1/old10.tar.gz`
4. **Archive test:** Run without `--dry-run --no-commit`, verify:
   - Correct `_bN/oldM.tar.gz` files created in both task and plan archived dirs
   - Original loose files removed
   - Each archive contains only files from its bundle range
5. **Unpack test:** `aitask_zip_old_v2.sh unpack <N>`, verify:
   - Correct archive is searched (not iterating all archives)
   - Files extracted to correct location in `archived/`
   - Archive rebuilt without extracted files (or deleted if empty)
6. **Legacy fallback:** Place a file in `old.tar.gz`, verify `unpack` finds it
7. **Empty run:** Verify graceful exit when no files are eligible
8. **Verbose mode:** Verify `-v` shows bundle grouping and per-file operations
9. **Integration with t433_6 test suite** -- coordinate to ensure test coverage
