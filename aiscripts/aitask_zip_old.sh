#!/bin/bash

# aitask_zip_old.sh - Archive old task and plan files to tar.gz
# Only archives files no longer relevant to active work

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

# --- Constants ---
TASK_ARCHIVED_DIR="aitasks/archived"
PLAN_ARCHIVED_DIR="aiplans/archived"
TASK_ARCHIVE="$TASK_ARCHIVED_DIR/old.tar.gz"
PLAN_ARCHIVE="$PLAN_ARCHIVED_DIR/old.tar.gz"

# --- Flags ---
DRY_RUN=false
NO_COMMIT=false
VERBOSE=false

# --- Counters ---
TASKS_ARCHIVED=0
PLANS_ARCHIVED=0

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

Archive old task and plan files to tar.gz archives.
Skips files still relevant to active work (siblings of active children, dependencies).

Options:
  -n, --dry-run    Show what would be archived without making changes
  --no-commit      Archive files but don't commit to git
  -v, --verbose    Show detailed progress output
  -h, --help       Show this help message

Examples:
  $(basename "$0")                  # Archive and commit
  $(basename "$0") --dry-run        # Preview what would be archived
  $(basename "$0") --no-commit      # Archive without git commit
  $(basename "$0") -v               # Verbose output
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

# --- Selection Functions ---

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
# Sets: _COLLECT_RESULT (newline-separated file list)
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

# Archive files to tar.gz (supports both flat files and subdirectory paths)
# Args: $1=archive_path, $2=files (newline-separated), $3=base_dir (for resolving relative paths)
archive_files() {
    local archive_path="$1"
    local files="$2"
    local base_dir="$3"
    local dir
    dir=$(dirname "$archive_path")

    if [[ -z "$files" ]]; then
        verbose "No files to archive for $archive_path"
        return 0
    fi

    local temp_dir
    temp_dir=$(mktemp -d)
    trap "rm -rf '$temp_dir'" RETURN

    # If archive exists, extract it first
    if [[ -f "$archive_path" ]]; then
        verbose "Extracting existing archive: $archive_path"
        if ! tar -xzf "$archive_path" -C "$temp_dir" 2>/dev/null; then
            warn "Warning: Existing archive appears corrupted. Creating backup."
            mv "$archive_path" "${archive_path}.bak"
            info "Backup saved as ${archive_path}.bak"
        fi
    fi

    # Copy new files to temp directory, preserving subdirectory structure
    # All paths are relative to base_dir (e.g., "t50_old.md" or "t10/t10_1_name.md")
    local count=0
    while IFS= read -r f; do
        [[ -z "$f" ]] && continue

        local src_path="$base_dir/$f"
        local dest_path="$temp_dir/$f"
        mkdir -p "$(dirname "$dest_path")"

        if [[ -f "$src_path" ]]; then
            verbose "Adding to archive: $f"
            cp "$src_path" "$dest_path"
            ((count++))
        fi
    done <<< "$files"

    # Create new archive
    verbose "Creating archive: $archive_path"
    tar -czf "$archive_path" -C "$temp_dir" .

    # Verify archive integrity
    verbose "Verifying archive integrity"
    if ! tar -tzf "$archive_path" > /dev/null 2>&1; then
        die "Archive verification failed! Original files NOT deleted."
    fi

    # Delete original files
    while IFS= read -r f; do
        [[ -z "$f" ]] && continue

        local src_path="$base_dir/$f"

        if [[ -f "$src_path" ]]; then
            verbose "Removing original: $src_path"
            rm "$src_path"

            # Try to remove parent directory if empty (for child directories)
            local parent_dir
            parent_dir=$(dirname "$src_path")
            if [[ -d "$parent_dir" && "$parent_dir" != "$base_dir" ]]; then
                rmdir "$parent_dir" 2>/dev/null || true
            fi
        fi
    done <<< "$files"

    echo "$count"
}

# --- Main ---

main() {
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

    if [[ -n "$task_files" ]]; then
        task_count=$(echo "$task_files" | wc -l)
    fi
    if [[ -n "$plan_files" ]]; then
        plan_count=$(echo "$plan_files" | wc -l)
    fi

    # Check if anything to do
    if [[ $task_count -eq 0 && $plan_count -eq 0 ]]; then
        info "No files to archive. All archived files are still relevant to active work (or directories are empty)."
        exit 0
    fi

    # Deduplicate skipped lists for display
    local unique_active_parents
    unique_active_parents=$(echo "$SKIPPED_ACTIVE_PARENTS" | tr ' ' '\n' | sort -un | tr '\n' ' ' | sed 's/^ *//;s/ *$//')
    local unique_deps
    unique_deps=$(echo "$SKIPPED_DEPS" | tr ' ' '\n' | sort -u | grep -v '^$' | tr '\n' ' ' | sed 's/^ *//;s/ *$//')

    # Dry run - show what would happen
    if $DRY_RUN; then
        echo ""

        if [[ -n "$unique_active_parents" || -n "$unique_deps" ]]; then
            info "Skipped (still relevant):"
            [[ -n "$unique_active_parents" ]] && echo "  Active parents: $unique_active_parents"
            [[ -n "$unique_deps" ]] && echo "  Dependencies: $unique_deps"
            echo ""
        fi

        info "Files that would be archived:"
        echo ""

        if [[ $task_count -gt 0 ]]; then
            echo "Tasks ($task_count files) -> $TASK_ARCHIVE:"
            echo "$task_files" | while read -r f; do
                [[ -n "$f" ]] && echo "  - $(basename "$f")"
            done
            echo ""
        fi

        if [[ $plan_count -gt 0 ]]; then
            echo "Plans ($plan_count files) -> $PLAN_ARCHIVE:"
            echo "$plan_files" | while read -r f; do
                [[ -n "$f" ]] && echo "  - $(basename "$f")"
            done
            echo ""
        fi

        exit 0
    fi

    # Archive task files
    if [[ $task_count -gt 0 ]]; then
        info "Archiving $task_count task file(s)..."
        TASKS_ARCHIVED=$(archive_files "$TASK_ARCHIVE" "$task_files" "$TASK_ARCHIVED_DIR")
    fi

    # Archive plan files
    if [[ $plan_count -gt 0 ]]; then
        info "Archiving $plan_count plan file(s)..."
        PLANS_ARCHIVED=$(archive_files "$PLAN_ARCHIVE" "$plan_files" "$PLAN_ARCHIVED_DIR")
    fi

    # Git commit (unless --no-commit)
    if ! $NO_COMMIT; then
        verbose "Committing changes to git..."

        git add "$TASK_ARCHIVE" "$PLAN_ARCHIVE" 2>/dev/null || true
        git add -u "$TASK_ARCHIVED_DIR/" "$PLAN_ARCHIVED_DIR/" 2>/dev/null || true

        local commit_msg="Archive old task and plan files

Archived to:
- $TASK_ARCHIVE
- $PLAN_ARCHIVE"

        if [[ -n "$unique_active_parents" || -n "$unique_deps" ]]; then
            commit_msg="$commit_msg

Skipped (still relevant):"
            [[ -n "$unique_active_parents" ]] && commit_msg="$commit_msg
- Active parents: $unique_active_parents"
            [[ -n "$unique_deps" ]] && commit_msg="$commit_msg
- Dependencies: $unique_deps"
        fi

        git commit -m "$commit_msg" 2>/dev/null || warn "Nothing to commit (no changes detected)"
    else
        info "Skipping git commit (--no-commit)"
    fi

    # Summary
    echo ""
    success "=== Archive Complete ==="
    echo ""
    echo "Task files archived: $TASKS_ARCHIVED"
    echo "Plan files archived: $PLANS_ARCHIVED"

    if [[ -n "$unique_active_parents" || -n "$unique_deps" ]]; then
        echo ""
        echo "Skipped (still relevant):"
        [[ -n "$unique_active_parents" ]] && echo "  Active parents: $unique_active_parents"
        [[ -n "$unique_deps" ]] && echo "  Dependencies: $unique_deps"
    fi

    echo ""
    echo "Archive sizes:"
    ls -lh "$TASK_ARCHIVE" "$PLAN_ARCHIVE" 2>/dev/null | awk '{print "  " $NF ": " $5}' || true
}

main "$@"
