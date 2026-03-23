---
Task: t433_4_v2_zip_old_script.md
Parent Task: aitasks/t433_refactor_task_archives.md
Sibling Tasks: aitasks/t433/t433_*_*.md
Worktree: (none -- current branch)
Branch: (current)
Base branch: main
---

## Context

Create `.aitask-scripts/aitask_zip_old_v2.sh` -- a v2 version of the zip-old script that writes to numbered archives (`_bN/oldM.tar.gz`) instead of a single `old.tar.gz`. The selection logic (which files are eligible for archiving) is unchanged. The archiving and unpacking logic is rewritten to use the bundle-based path scheme from t433_1.

## Dependencies

- **t433_1** (archive_utils_v2.sh) must be complete -- provides `archive_bundle()`, `archive_dir()`, `archive_path_for_id()`

## Implementation

### Step 1: Script skeleton

Create `.aitask-scripts/aitask_zip_old_v2.sh` with:

```bash
#!/usr/bin/env bash
# aitask_zip_old_v2.sh - Archive old task and plan files to numbered tar.gz archives
# Groups files by 100-task bundles into _bN/oldM.tar.gz

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/terminal_compat.sh"
source "$SCRIPT_DIR/lib/task_utils.sh"
source "$SCRIPT_DIR/lib/archive_utils_v2.sh"
```

Constants, flags, counters, computed sets -- same as v1.

### Step 2: Copy unchanged functions from v1

Copy verbatim from `aitask_zip_old.sh`:

- `verbose()` -- conditional stderr logging
- `usage()` -- update help text to mention numbered archives
- `parse_args()` -- identical CLI flags
- `get_active_parent_numbers()` -- scans active task dirs
- `get_dependency_task_ids()` -- extracts depends from active frontmatter
- `is_parent_active()` -- membership check
- `is_dependency()` -- membership check
- `collect_files_to_archive()` -- scans archived dir for loose eligible files

These are archive-format-agnostic and work identically.

### Step 3: Implement _archive_single_bundle()

Private helper that handles one archive file (create or append-merge):

```bash
_archive_single_bundle() {
    local archive_path="$1"
    local files="$2"        # newline-separated, relative to base_dir
    local base_dir="$3"

    local temp_dir
    temp_dir=$(mktemp -d)
    trap "rm -rf '$temp_dir'" RETURN

    # Extract existing archive to merge
    if [[ -f "$archive_path" ]]; then
        verbose "Merging with existing archive: $archive_path"
        if ! tar -xzf "$archive_path" -C "$temp_dir" 2>/dev/null; then
            warn "Warning: Existing archive corrupted. Creating backup."
            mv "$archive_path" "${archive_path}.bak"
        fi
    fi

    # Copy new files
    local count=0
    while IFS= read -r f; do
        [[ -z "$f" ]] && continue
        local src="$base_dir/$f" dest="$temp_dir/$f"
        mkdir -p "$(dirname "$dest")"
        if [[ -f "$src" ]]; then
            verbose "  + $f -> $(basename "$archive_path")"
            cp "$src" "$dest"
            ((count++))
        fi
    done <<< "$files"

    # Create archive and verify
    mkdir -p "$(dirname "$archive_path")"
    tar -czf "$archive_path" -C "$temp_dir" .
    tar -tzf "$archive_path" > /dev/null 2>&1 || die "Archive verification failed: $archive_path"

    # Remove originals
    while IFS= read -r f; do
        [[ -z "$f" ]] && continue
        local src="$base_dir/$f"
        [[ -f "$src" ]] && rm "$src"
        # Remove empty parent dir
        local pdir
        pdir=$(dirname "$src")
        [[ -d "$pdir" && "$pdir" != "$base_dir" ]] && rmdir "$pdir" 2>/dev/null || true
    done <<< "$files"

    echo "$count"
}
```

### Step 4: Implement archive_files_v2()

Groups files by archive bundle, then calls `_archive_single_bundle()` for each group:

```bash
archive_files_v2() {
    local files="$1"
    local base_dir="$2"
    local prefix="$3"
    local total=0

    [[ -z "$files" ]] && { echo "0"; return 0; }

    # Group by bundle using associative array
    declare -A bundle_groups

    while IFS= read -r f; do
        [[ -z "$f" ]] && continue
        local bname
        bname=$(basename "$f")
        # Extract parent number: t100_name.md -> 100, p129_name.md -> 129
        local num
        num=$(echo "$bname" | sed "s/^${prefix}\([0-9]*\).*/\1/")
        local apath
        apath=$(archive_path_for_id "$num" "$base_dir")
        if [[ -n "${bundle_groups[$apath]:-}" ]]; then
            bundle_groups[$apath]="${bundle_groups[$apath]}"$'\n'"$f"
        else
            bundle_groups[$apath]="$f"
        fi
    done <<< "$files"

    # Archive each bundle
    for apath in "${!bundle_groups[@]}"; do
        local group="${bundle_groups[$apath]}"
        verbose "Bundle: $apath"
        local cnt
        cnt=$(_archive_single_bundle "$apath" "$group" "$base_dir")
        ((total += cnt))
    done

    echo "$total"
}
```

### Step 5: Implement cmd_unpack_v2()

Targeted unpack -- computes the exact archive path instead of searching all archives:

```bash
cmd_unpack_v2() {
    local num="$1"
    local found=false

    local archive_types=(
        "$TASK_ARCHIVED_DIR|t|UNPACKED_TASK"
        "$PLAN_ARCHIVED_DIR|p|UNPACKED_PLAN"
    )

    for entry in "${archive_types[@]}"; do
        IFS='|' read -r base_dir prefix output_tag <<< "$entry"

        # Compute numbered archive path, plus legacy fallback
        local archive_path legacy_path
        archive_path=$(archive_path_for_id "$num" "$base_dir")
        legacy_path="$base_dir/old.tar.gz"

        local search_list=()
        [[ -f "$archive_path" ]] && search_list+=("$archive_path")
        [[ -f "$legacy_path" ]] && search_list+=("$legacy_path")

        for arch in "${search_list[@]}"; do
            local matches
            matches=$(tar -tzf "$arch" 2>/dev/null \
                | grep -E "(^|/)${prefix}${num}_[^/]*\.md$|(^|/)${prefix}${num}/${prefix}${num}_[^/]*\.md$" || true)
            [[ -z "$matches" ]] && continue

            local temp_dir
            temp_dir=$(mktemp -d)
            tar -xzf "$arch" -C "$temp_dir"

            while IFS= read -r match; do
                [[ -z "$match" ]] && continue
                local src="$temp_dir/$match"
                [[ -f "$src" ]] || continue
                local clean="${match#./}"
                local dest="$base_dir/$clean"
                mkdir -p "$(dirname "$dest")"
                cp "$src" "$dest"
                rm "$src"
                echo "${output_tag}:${dest}"
                found=true
            done <<< "$matches"

            # Clean up empty dirs in temp
            find "$temp_dir" -mindepth 1 -type d -empty -delete 2>/dev/null || true

            # Rebuild or remove archive
            local remaining
            remaining=$(find "$temp_dir" -type f 2>/dev/null | head -1)
            if [[ -z "$remaining" ]]; then
                rm "$arch"
                # Remove parent _bN dir if empty
                local bdir
                bdir=$(dirname "$arch")
                [[ -d "$bdir" ]] && rmdir "$bdir" 2>/dev/null || true
            else
                tar -czf "$arch" -C "$temp_dir" .
            fi

            rm -rf "$temp_dir"
            [[ "$found" == true ]] && break
        done
    done

    [[ "$found" == false ]] && echo "NOT_IN_ARCHIVE"
}
```

### Step 6: Implement main() with v2 calls

```bash
main() {
    # Subcommand: unpack
    if [[ $# -ge 1 && "$1" == "unpack" ]]; then
        shift
        [[ $# -lt 1 ]] && die "unpack requires a task number argument"
        local num="$1"
        num="${num#t}"; num="${num#p}"
        [[ ! "$num" =~ ^[0-9]+$ ]] && die "Invalid task number: '$1'"
        cmd_unpack_v2 "$num"
        exit 0
    fi

    parse_args "$@"
    $DRY_RUN && info "=== DRY RUN MODE ==="

    # Compute selection sets
    ACTIVE_PARENTS=$(get_active_parent_numbers)
    DEPENDENCY_IDS=$(get_dependency_task_ids)
    verbose "Active parents:${ACTIVE_PARENTS:- (none)}"
    verbose "Dependency IDs:${DEPENDENCY_IDS:- (none)}"

    # Collect eligible files
    verbose "Scanning $TASK_ARCHIVED_DIR..."
    collect_files_to_archive "$TASK_ARCHIVED_DIR" "t"
    local task_files="$_COLLECT_RESULT"

    verbose "Scanning $PLAN_ARCHIVED_DIR..."
    collect_files_to_archive "$PLAN_ARCHIVED_DIR" "p"
    local plan_files="$_COLLECT_RESULT"

    local task_count=0 plan_count=0
    [[ -n "$task_files" ]] && task_count=$(echo "$task_files" | wc -l | tr -d ' ')
    [[ -n "$plan_files" ]] && plan_count=$(echo "$plan_files" | wc -l | tr -d ' ')

    if [[ $task_count -eq 0 && $plan_count -eq 0 ]]; then
        info "No files to archive."
        exit 0
    fi

    # Deduplicate skipped lists
    local unique_active_parents unique_deps
    unique_active_parents=$(echo "$SKIPPED_ACTIVE_PARENTS" | tr ' ' '\n' | sort -un | tr '\n' ' ' | sed 's/^ *//;s/ *$//')
    unique_deps=$(echo "$SKIPPED_DEPS" | tr ' ' '\n' | sort -u | grep -v '^$' | tr '\n' ' ' | sed 's/^ *//;s/ *$//')

    # --- Dry run ---
    if $DRY_RUN; then
        # Show bundle grouping
        _show_dry_run_bundles "$task_files" "$TASK_ARCHIVED_DIR" "t" "Tasks"
        _show_dry_run_bundles "$plan_files" "$PLAN_ARCHIVED_DIR" "p" "Plans"
        # Show skipped
        if [[ -n "$unique_active_parents" || -n "$unique_deps" ]]; then
            echo ""
            info "Skipped (still relevant):"
            [[ -n "$unique_active_parents" ]] && echo "  Active parents: $unique_active_parents"
            [[ -n "$unique_deps" ]] && echo "  Dependencies: $unique_deps"
        fi
        exit 0
    fi

    # --- Archive ---
    local tasks_archived=0 plans_archived=0
    if [[ $task_count -gt 0 ]]; then
        info "Archiving $task_count task file(s) to numbered bundles..."
        tasks_archived=$(archive_files_v2 "$task_files" "$TASK_ARCHIVED_DIR" "t")
    fi
    if [[ $plan_count -gt 0 ]]; then
        info "Archiving $plan_count plan file(s) to numbered bundles..."
        plans_archived=$(archive_files_v2 "$plan_files" "$PLAN_ARCHIVED_DIR" "p")
    fi

    # --- Git commit ---
    if ! $NO_COMMIT; then
        task_git add "$TASK_ARCHIVED_DIR"/_b*/old*.tar.gz 2>/dev/null || true
        task_git add "$PLAN_ARCHIVED_DIR"/_b*/old*.tar.gz 2>/dev/null || true
        task_git add -u "$TASK_ARCHIVED_DIR/" "$PLAN_ARCHIVED_DIR/" 2>/dev/null || true
        local commit_msg="ait: Archive old files to numbered bundles

Tasks archived: $tasks_archived
Plans archived: $plans_archived"
        task_git commit -m "$commit_msg" 2>/dev/null || warn "Nothing to commit"
    fi

    # --- Summary ---
    echo ""
    success "=== Archive Complete ==="
    echo "Task files archived: $tasks_archived"
    echo "Plan files archived: $plans_archived"
}
```

### Step 7: Implement _show_dry_run_bundles() helper

```bash
_show_dry_run_bundles() {
    local files="$1" base_dir="$2" prefix="$3" label="$4"
    [[ -z "$files" ]] && return

    declare -A groups
    while IFS= read -r f; do
        [[ -z "$f" ]] && continue
        local bname num apath
        bname=$(basename "$f")
        num=$(echo "$bname" | sed "s/^${prefix}\([0-9]*\).*/\1/")
        apath=$(archive_path_for_id "$num" "$base_dir")
        local bundle
        bundle=$(archive_bundle "$num")
        local range_lo=$((bundle * 100)) range_hi=$(( (bundle + 1) * 100 - 1 ))
        local key="${apath}|${range_lo}-${range_hi}"
        if [[ -n "${groups[$key]:-}" ]]; then
            groups[$key]="${groups[$key]}"$'\n'"    - $f"
        else
            groups[$key]="    - $f"
        fi
    done <<< "$files"

    echo ""
    echo "$label:"
    for key in $(echo "${!groups[@]}" | tr ' ' '\n' | sort); do
        IFS='|' read -r apath range <<< "$key"
        echo "  $apath (${prefix}${range}):"
        echo "${groups[$key]}"
    done
}
```

### Step 8: Make script executable and run shellcheck

```bash
chmod +x .aitask-scripts/aitask_zip_old_v2.sh
shellcheck .aitask-scripts/aitask_zip_old_v2.sh
```

Fix any issues: quoting, declare -A in local scope (use at function top level), etc.

### Step 9: Manual integration test

Set up a test scenario:

```bash
# Create test archived files spanning multiple bundles
mkdir -p aitasks/archived aiplans/archived
echo "test" > aitasks/archived/t50_old_task.md
echo "test" > aitasks/archived/t150_old_task.md
echo "test" > aiplans/archived/p50_old_plan.md

# Dry run
bash .aitask-scripts/aitask_zip_old_v2.sh --dry-run -v

# Archive with no-commit
bash .aitask-scripts/aitask_zip_old_v2.sh --no-commit -v

# Verify files landed in correct bundles
tar -tzf aitasks/archived/_b0/old0.tar.gz  # should contain t50
tar -tzf aitasks/archived/_b0/old1.tar.gz  # should contain t150

# Unpack
bash .aitask-scripts/aitask_zip_old_v2.sh unpack 50
ls aitasks/archived/t50_old_task.md  # should exist again
```

### Step 10: Edge cases to handle

- **Empty file list:** `archive_files_v2` returns 0 gracefully
- **Corrupted existing archive:** backup and recreate (same as v1)
- **Mixed bundles in one run:** multiple `_bN/oldM.tar.gz` files created/updated in a single invocation
- **Child tasks in subdirectories:** `t129/t129_3_name.md` -- parent number extraction must handle the subdir prefix
- **`wc -l` portability:** pipe through `tr -d ' '` when comparing as string (per CLAUDE.md)
- **`declare -A` requires bash 4+:** the shebang `#!/usr/bin/env bash` picks up brew bash 5 on macOS (per CLAUDE.md)

## Final Implementation Notes

- **Actual work done:** Created `.aitask-scripts/aitask_zip_old_v2.sh` (~370 lines) implementing all planned functions: selection logic copied from v1 (unchanged), `_archive_single_bundle()` for per-archive create/merge, `archive_files_v2()` with associative-array grouping by bundle, `cmd_unpack_v2()` with O(1) archive lookup + legacy fallback, `_show_dry_run_bundles()` for bundle-grouped dry-run display, and `main()` wiring it all together.
- **Deviations from plan:**
  - Fixed `archive_path_for_id` argument order throughout (plan had `base_dir, num` but actual function signature is `task_id, archived_dir`). Caught during verification.
  - Added `|| true` to `grep -v '^$'` pipelines in the dedup section — `set -euo pipefail` (new in v2, v1 used only `set -e`) causes `grep` returning exit 1 on no-match to abort the script.
  - Removed unused `TASKS_ARCHIVED`/`PLANS_ARCHIVED` global counters (v2 uses locals in `main()`).
- **Issues encountered:** `pipefail` interaction with `grep -v '^$'` — when `SKIPPED_*` variables are empty, the grep produces no output and returns exit 1, triggering pipefail abort. Fixed by appending `|| true`.
- **Key decisions:** Kept `set -euo pipefail` (stricter than v1's `set -e`) since it caught the grep issue early. The trap in `_archive_single_bundle` intentionally uses early expansion (`SC2064` suppressed) to capture the temp dir path.
- **Notes for sibling tasks:** The v2 script is fully standalone and coexists with v1. It sources `archive_utils_v2.sh` for path computation. The `archive_files_v2()` and `_archive_single_bundle()` functions could be referenced by t433_5 (archive scanners) if needed. The bundle grouping pattern (associative array keyed by archive path) may be useful in t433_6 integration tests.
