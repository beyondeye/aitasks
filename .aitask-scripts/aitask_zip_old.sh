#!/usr/bin/env bash

# aitask_zip_old.sh - Archive old task and plan files to numbered tar.gz archives
# Groups files by 100-task bundles into _bN/oldM.tar.gz
#
# Numbering scheme:
#   bundle = task_id / 100
#   dir    = bundle / 10
#   path   = archived/_b{dir}/old{bundle}.tar.gz

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"
# shellcheck source=lib/archive_utils.sh
source "$SCRIPT_DIR/lib/archive_utils.sh"

# --- Constants ---
TASK_ARCHIVED_DIR="aitasks/archived"
PLAN_ARCHIVED_DIR="aiplans/archived"

# --- Flags ---
DRY_RUN=false
NO_COMMIT=false
VERBOSE=false

# --- Computed sets (populated in main) ---
ACTIVE_PARENTS=""
DEPENDENCY_IDS=""
SKIPPED_ACTIVE_PARENTS=""
SKIPPED_DEPS=""

# --- Helper Functions ---

verbose() {
    if $VERBOSE; then
        echo -e "${BLUE}[verbose]${NC} $1" >&2
    fi
}

usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]
       $(basename "$0") unpack <task_number>

Archive old task and plan files to numbered tar.gz archives.
Groups files by 100-task bundles into _bN/oldM.tar.gz.
Skips files still relevant to active work (siblings of active children, dependencies).

Options:
  -n, --dry-run    Show what would be archived without making changes
  --no-commit      Archive files but don't commit to git
  -v, --verbose    Show detailed progress output
  -h, --help       Show this help message

Examples:
  $(basename "$0")                  # Archive and commit
  $(basename "$0") --dry-run        # Preview what would be archived (shows bundle grouping)
  $(basename "$0") --no-commit      # Archive without git commit
  $(basename "$0") -v               # Verbose output
  $(basename "$0") unpack 42        # Extract task 42 from numbered archive
EOF
}

# --- Argument Parsing ---

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -n|--dry-run)
                DRY_RUN=true
                shift
                ;;
            --no-commit)
                NO_COMMIT=true
                shift
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                die "Unknown option: $1. Use --help for usage."
                ;;
        esac
    done
}

# --- Selection Functions (unchanged from v1) ---

# Get parent numbers that still have active children (aitasks/t*/ directories)
get_active_parent_numbers() {
    local result=""
    for dir in aitasks/t*/; do
        [ -d "$dir" ] || continue
        local num
        num=$(basename "$dir" | sed 's/t//')
        result="$result $num"
    done
    echo "$result"
}

# Get task IDs referenced by depends: fields in active task files
get_dependency_task_ids() {
    local result=""
    # shellcheck disable=SC2086
    local files
    files=$(ls aitasks/t*_*.md aitasks/t*/t*_*.md 2>/dev/null || true)
    for f in $files; do
        local deps_line
        deps_line=$(grep '^depends:' "$f" 2>/dev/null || true)
        [[ -z "$deps_line" ]] && continue
        # Extract content between [ and ]
        local deps_content
        deps_content=$(echo "$deps_line" | sed 's/.*\[\(.*\)\].*/\1/')
        [[ -z "$deps_content" || "$deps_content" == "$deps_line" ]] && continue
        # Split by comma, strip quotes/spaces/t-prefix
        local saved_ifs="$IFS"
        IFS=','
        for dep in $deps_content; do
            dep=$(echo "$dep" | tr -d "' \"" | sed 's/^t//')
            [[ -n "$dep" ]] && result="$result $dep"
        done
        IFS="$saved_ifs"
    done
    echo "$result"
}

# Check if a parent number has active children
is_parent_active() {
    local num="$1"
    echo " $ACTIVE_PARENTS " | grep -q " $num "
}

# Check if a task ID is referenced as a dependency
is_dependency() {
    local id="$1"
    echo " $DEPENDENCY_IDS " | grep -q " $id "
}

# Collect files to archive from an archived directory
# Args: $1=base_dir (e.g., aitasks/archived), $2=prefix (t or p)
# Sets: _COLLECT_RESULT (newline-separated file list, relative to base_dir)
# Side effects: appends to SKIPPED_ACTIVE_PARENTS and SKIPPED_DEPS
# NOTE: Must be called directly (not in command substitution) to preserve globals
collect_files_to_archive() {
    local base_dir="$1"
    local prefix="$2"
    local result=""

    # Parent-level files (e.g., aitasks/archived/t100_name.md)
    for f in "$base_dir"/${prefix}*_*.md; do
        [ -e "$f" ] || continue
        local basename_f
        basename_f=$(basename "$f")
        # Extract parent number: t100_name.md -> 100
        local parent_num
        parent_num=$(echo "$basename_f" | sed "s/^${prefix}\([0-9]*\)_.*/\1/")

        if is_dependency "$parent_num"; then
            verbose "Skipping (dependency of active task): $basename_f"
            SKIPPED_DEPS="$SKIPPED_DEPS $parent_num"
            continue
        fi

        # Add basename (relative to base_dir)
        if [[ -n "$result" ]]; then
            result="${result}"$'\n'"${basename_f}"
        else
            result="$basename_f"
        fi
    done

    # Child subdirectories (e.g., aitasks/archived/t129/)
    for subdir in "$base_dir"/${prefix}*/; do
        [ -d "$subdir" ] || continue
        local parent_num
        parent_num=$(basename "$subdir" | sed "s/^${prefix}//")

        if is_parent_active "$parent_num"; then
            verbose "Skipping (active siblings): ${prefix}${parent_num}/"
            SKIPPED_ACTIVE_PARENTS="$SKIPPED_ACTIVE_PARENTS $parent_num"
            continue
        fi

        # Check individual children for dependency references
        for f in "$subdir"/${prefix}${parent_num}_*_*.md; do
            [ -e "$f" ] || continue
            local basename_f
            basename_f=$(basename "$f")
            # Extract child ID: t129_3_name.md -> 129_3
            local child_id
            child_id=$(echo "$basename_f" | sed "s/^${prefix}\([0-9]*_[0-9]*\)_.*/\1/")

            if is_dependency "$child_id"; then
                verbose "Skipping (dependency of active task): $basename_f"
                SKIPPED_DEPS="$SKIPPED_DEPS $child_id"
                continue
            fi

            # Relative path from base_dir for child files
            local rel_path="${prefix}${parent_num}/${basename_f}"
            if [[ -n "$result" ]]; then
                result="${result}"$'\n'"${rel_path}"
            else
                result="$rel_path"
            fi
        done
    done

    _COLLECT_RESULT="$result"
}

# --- V2 Archive Functions ---

# Archive a group of files into a single tar.gz (create or append-merge)
# Args: $1=archive_path, $2=files (newline-separated, relative to base_dir), $3=base_dir
# Output: number of files added
_archive_single_bundle() {
    local archive_path="$1"
    local files="$2"
    local base_dir="$3"

    local temp_dir
    temp_dir=$(mktemp -d)
    # shellcheck disable=SC2064  # Intentional: expand $temp_dir at definition time
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
        local src="$base_dir/$f"
        local dest="$temp_dir/$f"
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
        if [[ -f "$src" ]]; then
            verbose "Removing original: $src"
            rm "$src"
            # Remove empty parent dir
            local pdir
            pdir=$(dirname "$src")
            if [[ -d "$pdir" && "$pdir" != "$base_dir" ]]; then
                rmdir "$pdir" 2>/dev/null || true
            fi
        fi
    done <<< "$files"

    echo "$count"
}

# Archive files to numbered tar.gz bundles
# Args: $1=files (newline-separated, relative to base_dir), $2=base_dir, $3=prefix (t or p)
# Output: total number of files archived
archive_files() {
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

# --- Dry Run Display ---

# Show files grouped by target bundle archive
# Args: $1=files, $2=base_dir, $3=prefix (t or p), $4=label (Tasks or Plans)
_show_dry_run_bundles() {
    local files="$1"
    local base_dir="$2"
    local prefix="$3"
    local label="$4"
    [[ -z "$files" ]] && return

    declare -A groups
    while IFS= read -r f; do
        [[ -z "$f" ]] && continue
        local bname
        bname=$(basename "$f")
        local num
        num=$(echo "$bname" | sed "s/^${prefix}\([0-9]*\).*/\1/")
        local apath
        apath=$(archive_path_for_id "$num" "$base_dir")
        local bundle
        bundle=$(archive_bundle "$num")
        local range_lo=$((bundle * 100))
        local range_hi=$(( (bundle + 1) * 100 - 1 ))
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
        local apath range
        IFS='|' read -r apath range <<< "$key"
        echo "  $apath (${prefix}${range}):"
        echo "${groups[$key]}"
    done
}

# --- Unpack subcommand ---

# Extract a task (and its children/plans) from numbered archives back to the filesystem.
# Falls back to legacy old.tar.gz if not found in numbered archive.
# Args: $1=task_number
cmd_unpack() {
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

    if [[ "$found" == false ]]; then
        echo "NOT_IN_ARCHIVE"
    fi
}

# --- Main ---

main() {
    # Check for subcommands before the default archive flow
    if [[ $# -ge 1 && "$1" == "unpack" ]]; then
        shift
        if [[ $# -lt 1 ]]; then
            die "unpack requires a task number argument"
        fi
        local num="$1"
        # Strip optional t/p prefix
        num="${num#t}"
        num="${num#p}"
        if [[ ! "$num" =~ ^[0-9]+$ ]]; then
            die "Invalid task number: '$1' (expected a number like 42 or t42)"
        fi
        cmd_unpack "$num"
        exit 0
    fi

    parse_args "$@"

    if $DRY_RUN; then
        info "=== DRY RUN MODE ==="
    fi

    # Compute sets for selection rules
    ACTIVE_PARENTS=$(get_active_parent_numbers)
    DEPENDENCY_IDS=$(get_dependency_task_ids)
    verbose "Active parents:${ACTIVE_PARENTS:- (none)}"
    verbose "Dependency IDs:${DEPENDENCY_IDS:- (none)}"

    # Collect task files to archive
    verbose "Scanning $TASK_ARCHIVED_DIR..."
    collect_files_to_archive "$TASK_ARCHIVED_DIR" "t"
    local task_files="$_COLLECT_RESULT"

    # Collect plan files to archive
    verbose "Scanning $PLAN_ARCHIVED_DIR..."
    collect_files_to_archive "$PLAN_ARCHIVED_DIR" "p"
    local plan_files="$_COLLECT_RESULT"

    # Count files to archive
    local task_count=0
    local plan_count=0
    [[ -n "$task_files" ]] && task_count=$(echo "$task_files" | wc -l | tr -d ' ')
    [[ -n "$plan_files" ]] && plan_count=$(echo "$plan_files" | wc -l | tr -d ' ')

    # Check if anything to do
    if [[ $task_count -eq 0 && $plan_count -eq 0 ]]; then
        info "No files to archive. All archived files are still relevant to active work (or directories are empty)."
        exit 0
    fi

    # Deduplicate skipped lists for display
    local unique_active_parents
    unique_active_parents=$(echo "$SKIPPED_ACTIVE_PARENTS" | tr ' ' '\n' | sort -un | grep -v '^$' | tr '\n' ' ' | sed 's/^ *//;s/ *$//' || true)
    local unique_deps
    unique_deps=$(echo "$SKIPPED_DEPS" | tr ' ' '\n' | sort -u | grep -v '^$' | tr '\n' ' ' | sed 's/^ *//;s/ *$//' || true)

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
    local tasks_archived=0
    local plans_archived=0
    if [[ $task_count -gt 0 ]]; then
        info "Archiving $task_count task file(s) to numbered bundles..."
        tasks_archived=$(archive_files "$task_files" "$TASK_ARCHIVED_DIR" "t")
    fi
    if [[ $plan_count -gt 0 ]]; then
        info "Archiving $plan_count plan file(s) to numbered bundles..."
        plans_archived=$(archive_files "$plan_files" "$PLAN_ARCHIVED_DIR" "p")
    fi

    # --- Git commit ---
    if ! $NO_COMMIT; then
        verbose "Committing changes to git..."
        task_git add "$TASK_ARCHIVED_DIR"/_b*/old*.tar.gz 2>/dev/null || true
        task_git add "$PLAN_ARCHIVED_DIR"/_b*/old*.tar.gz 2>/dev/null || true
        task_git add -u "$TASK_ARCHIVED_DIR/" "$PLAN_ARCHIVED_DIR/" 2>/dev/null || true

        local commit_msg="ait: Archive old files to numbered bundles

Tasks archived: $tasks_archived
Plans archived: $plans_archived"

        task_git commit -m "$commit_msg" 2>/dev/null || warn "Nothing to commit (no changes detected)"
    else
        info "Skipping git commit (--no-commit)"
    fi

    # --- Summary ---
    echo ""
    success "=== Archive Complete ==="
    echo ""
    echo "Task files archived: $tasks_archived"
    echo "Plan files archived: $plans_archived"

    if [[ -n "$unique_active_parents" || -n "$unique_deps" ]]; then
        echo ""
        echo "Skipped (still relevant):"
        [[ -n "$unique_active_parents" ]] && echo "  Active parents: $unique_active_parents"
        [[ -n "$unique_deps" ]] && echo "  Dependencies: $unique_deps"
    fi
}

main "$@"
