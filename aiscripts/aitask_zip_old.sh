#!/bin/bash

# aitask_zip_old.sh - Archive old task and plan files to tar.gz
# Keeps the most recent archived file uncompressed for aitask-create numbering

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
KEEP_TASK=""
KEEP_PLAN=""

# --- Helper Functions ---

verbose() {
    if $VERBOSE; then
        echo -e "${BLUE}[verbose]${NC} $1"
    fi
}

usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Archive old task and plan files to tar.gz archives, keeping only the most recent.

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

# --- Core Functions ---

# Find the most recent file by number prefix (e.g., t22 from t22_name.md)
# Args: $1=directory, $2=pattern (e.g., "t*_*.md"), $3=prefix letter (e.g., "t")
find_most_recent() {
    local dir="$1"
    local pattern="$2"
    local prefix="$3"

    # shellcheck disable=SC2086
    ls "$dir"/$pattern 2>/dev/null | \
        sed "s/.*\/${prefix}\([0-9]*\)_.*/\1 &/" | \
        sort -n | tail -1 | cut -d' ' -f2-
}

# Find most recent file in a child subdirectory (e.g., t1_2 from t1_2_name.md)
# Args: $1=subdirectory, $2=parent_num
find_most_recent_child() {
    local subdir="$1"
    local parent_num="$2"

    # Pattern: t<parent>_<child>_*.md
    ls "$subdir"/t${parent_num}_*_*.md 2>/dev/null | \
        sed "s/.*\/t${parent_num}_\([0-9]*\)_.*/\1 &/" | \
        sort -n | tail -1 | cut -d' ' -f2-
}

# Get list of files to archive (all except the most recent)
# Args: $1=directory, $2=pattern, $3=file_to_keep
get_files_to_archive() {
    local dir="$1"
    local pattern="$2"
    local keep_file="$3"

    if [[ -z "$keep_file" ]]; then
        return
    fi

    local keep_basename
    keep_basename=$(basename "$keep_file")

    # shellcheck disable=SC2086
    ls "$dir"/$pattern 2>/dev/null | grep -v "$keep_basename" || true
}

# Get list of files to archive from child subdirectories
# Args: $1=base_directory (e.g., aitasks/archived), $2=prefix (t or p)
# Returns: newline-separated list of relative paths (e.g., t1/t1_2_name.md)
get_child_files_to_archive() {
    local base_dir="$1"
    local prefix="$2"

    local result=""

    # Scan each child subdirectory
    for subdir in "$base_dir"/${prefix}*/; do
        [ -d "$subdir" ] || continue

        local parent_num
        parent_num=$(basename "$subdir" | sed "s/${prefix}//")

        # Find the most recent file in this subdirectory
        local keep_child
        keep_child=$(find_most_recent_child "$subdir" "$parent_num")

        # Get files to archive (all except most recent)
        for f in "$subdir"/${prefix}${parent_num}_*_*.md; do
            [ -e "$f" ] || continue
            if [[ -n "$keep_child" && "$f" == "$keep_child" ]]; then
                verbose "Will keep child: $(basename "$f")"
                continue
            fi
            # Return relative path from base_dir
            local rel_path="${prefix}${parent_num}/$(basename "$f")"
            if [[ -n "$result" ]]; then
                result="${result}"$'\n'"${rel_path}"
            else
                result="$rel_path"
            fi
        done
    done

    echo "$result"
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
    local count=0
    while IFS= read -r f; do
        [[ -z "$f" ]] && continue

        local src_path
        local dest_path

        # Check if it's a relative path (contains /) or absolute
        if [[ "$f" == */* ]]; then
            # Relative path (e.g., t1/t1_2_name.md)
            src_path="$base_dir/$f"
            dest_path="$temp_dir/$f"

            # Create subdirectory in temp if needed
            mkdir -p "$(dirname "$dest_path")"
        else
            # Just a filename
            src_path="$f"
            dest_path="$temp_dir/$(basename "$f")"
        fi

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

        local src_path
        if [[ "$f" == */* ]]; then
            src_path="$base_dir/$f"
        else
            src_path="$f"
        fi

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

    # Step 1: Find task files to archive (parent level)
    verbose "Scanning $TASK_ARCHIVED_DIR for parent task files..."
    KEEP_TASK=$(find_most_recent "$TASK_ARCHIVED_DIR" "t*_*.md" "t")
    local task_files
    task_files=$(get_files_to_archive "$TASK_ARCHIVED_DIR" "t*_*.md" "$KEEP_TASK")

    if [[ -n "$KEEP_TASK" ]]; then
        verbose "Will keep uncompressed: $(basename "$KEEP_TASK")"
    fi

    # Step 1b: Find child task files to archive
    verbose "Scanning $TASK_ARCHIVED_DIR for child task files..."
    local child_task_files
    child_task_files=$(get_child_files_to_archive "$TASK_ARCHIVED_DIR" "t")

    # Combine parent and child task files
    if [[ -n "$child_task_files" ]]; then
        if [[ -n "$task_files" ]]; then
            task_files="${task_files}"$'\n'"${child_task_files}"
        else
            task_files="$child_task_files"
        fi
    fi

    # Step 2: Find plan files to archive (parent level)
    verbose "Scanning $PLAN_ARCHIVED_DIR for parent plan files..."
    KEEP_PLAN=$(find_most_recent "$PLAN_ARCHIVED_DIR" "p*_*.md" "p")
    local plan_files
    plan_files=$(get_files_to_archive "$PLAN_ARCHIVED_DIR" "p*_*.md" "$KEEP_PLAN")

    if [[ -n "$KEEP_PLAN" ]]; then
        verbose "Will keep uncompressed: $(basename "$KEEP_PLAN")"
    fi

    # Step 2b: Find child plan files to archive
    verbose "Scanning $PLAN_ARCHIVED_DIR for child plan files..."
    local child_plan_files
    child_plan_files=$(get_child_files_to_archive "$PLAN_ARCHIVED_DIR" "p")

    # Combine parent and child plan files
    if [[ -n "$child_plan_files" ]]; then
        if [[ -n "$plan_files" ]]; then
            plan_files="${plan_files}"$'\n'"${child_plan_files}"
        else
            plan_files="$child_plan_files"
        fi
    fi

    # Count files to archive
    local task_count=0
    local plan_count=0

    if [[ -n "$task_files" ]]; then
        task_count=$(echo "$task_files" | wc -l)
    fi
    if [[ -n "$plan_files" ]]; then
        plan_count=$(echo "$plan_files" | wc -l)
    fi

    # Step 3: Check if anything to do
    if [[ $task_count -eq 0 && $plan_count -eq 0 ]]; then
        info "No old files to archive. The archived directories only contain the most recent files (or are empty)."
        exit 0
    fi

    # Step 4: Dry run - just show what would happen
    if $DRY_RUN; then
        echo ""
        info "Files that would be archived:"
        echo ""

        if [[ $task_count -gt 0 ]]; then
            echo "Tasks ($task_count files) -> $TASK_ARCHIVE:"
            echo "$task_files" | while read -r f; do
                [[ -n "$f" ]] && echo "  - $(basename "$f")"
            done
            if [[ -n "$KEEP_TASK" ]]; then
                echo "  (keeping: $(basename "$KEEP_TASK"))"
            fi
            echo ""
        fi

        if [[ $plan_count -gt 0 ]]; then
            echo "Plans ($plan_count files) -> $PLAN_ARCHIVE:"
            echo "$plan_files" | while read -r f; do
                [[ -n "$f" ]] && echo "  - $(basename "$f")"
            done
            if [[ -n "$KEEP_PLAN" ]]; then
                echo "  (keeping: $(basename "$KEEP_PLAN"))"
            fi
            echo ""
        fi

        exit 0
    fi

    # Step 5: Archive task files
    if [[ $task_count -gt 0 ]]; then
        info "Archiving $task_count task file(s)..."
        TASKS_ARCHIVED=$(archive_files "$TASK_ARCHIVE" "$task_files" "$TASK_ARCHIVED_DIR")
    fi

    # Step 6: Archive plan files
    if [[ $plan_count -gt 0 ]]; then
        info "Archiving $plan_count plan file(s)..."
        PLANS_ARCHIVED=$(archive_files "$PLAN_ARCHIVE" "$plan_files" "$PLAN_ARCHIVED_DIR")
    fi

    # Step 7: Git commit (unless --no-commit)
    if ! $NO_COMMIT; then
        verbose "Committing changes to git..."

        git add "$TASK_ARCHIVE" "$PLAN_ARCHIVE" 2>/dev/null || true
        git add -u "$TASK_ARCHIVED_DIR/" "$PLAN_ARCHIVED_DIR/" 2>/dev/null || true

        local keep_task_name=""
        local keep_plan_name=""
        [[ -n "$KEEP_TASK" ]] && keep_task_name=$(basename "$KEEP_TASK")
        [[ -n "$KEEP_PLAN" ]] && keep_plan_name=$(basename "$KEEP_PLAN")

        git commit -m "Archive old task and plan files

Archived to:
- $TASK_ARCHIVE
- $PLAN_ARCHIVE

Kept most recent:
- $keep_task_name
- $keep_plan_name" 2>/dev/null || warn "Nothing to commit (no changes detected)"
    else
        info "Skipping git commit (--no-commit)"
    fi

    # Step 8: Summary
    echo ""
    success "=== Archive Complete ==="
    echo ""
    echo "Task files archived: $TASKS_ARCHIVED"
    echo "Plan files archived: $PLANS_ARCHIVED"
    echo ""

    if [[ -n "$KEEP_TASK" ]]; then
        echo "Kept uncompressed (task): $(basename "$KEEP_TASK")"
    fi
    if [[ -n "$KEEP_PLAN" ]]; then
        echo "Kept uncompressed (plan): $(basename "$KEEP_PLAN")"
    fi

    echo ""
    echo "Archive sizes:"
    ls -lh "$TASK_ARCHIVE" "$PLAN_ARCHIVE" 2>/dev/null | awk '{print "  " $NF ": " $5}' || true
}

main "$@"
