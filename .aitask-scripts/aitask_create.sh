#!/usr/bin/env bash

# aitask_create.sh - Interactive AI task creation with fzf
# Creates task files in aitasks/ directory with YAML front matter

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
source "$SCRIPT_DIR/lib/task_utils.sh"
# shellcheck source=lib/archive_utils.sh
source "$SCRIPT_DIR/lib/archive_utils.sh"

TASK_DIR="aitasks"
ARCHIVED_DIR="aitasks/archived"
if [[ -f "aitasks/archived/old.tar.zst" ]]; then
    ARCHIVE_FILE="aitasks/archived/old.tar.zst"
elif [[ -f "aitasks/archived/old.tar.gz" ]]; then
    ARCHIVE_FILE="aitasks/archived/old.tar.gz"
else
    ARCHIVE_FILE=""
fi

# Batch mode variables
BATCH_MODE=false
BATCH_NAME=""
BATCH_DESC=""
BATCH_DESC_FILE=""
BATCH_PRIORITY="medium"
BATCH_EFFORT="medium"
BATCH_TYPE="feature"
BATCH_STATUS="Ready"
BATCH_LABELS=""
BATCH_DEPS=""
BATCH_VERIFIES=""
BATCH_COMMIT=false
BATCH_SILENT=false
BATCH_PARENT=""
BATCH_NO_SIBLING_DEP=false
BATCH_ASSIGNED_TO=""
BATCH_ISSUE=""
BATCH_PULL_REQUEST=""
BATCH_CONTRIBUTOR=""
BATCH_CONTRIBUTOR_EMAIL=""
BATCH_FILE_REFS=()
BATCH_AUTO_MERGE=false

# Draft/finalize mode variables
BATCH_FINALIZE=""
BATCH_FINALIZE_ALL=false
DRAFT_DIR="aitasks/new"

# --- Helper Functions ---

show_help() {
    cat << 'EOF'
Usage: aitask_create.sh [options]

Interactive mode (default):
  Run without arguments for interactive task creation with fzf.

Batch mode (for automation):
  --batch                Enable batch mode (non-interactive)
  --name, -n NAME        Task name (required, will be sanitized)
  --desc, -d DESC        Task description
  --desc-file FILE       Read description from file (use - for stdin)
  --priority, -p LEVEL   Priority: high, medium, low (default: medium)
  --effort, -e LEVEL     Effort: low, medium, high (default: medium)
  --type, -t TYPE        Issue type (see aitasks/metadata/task_types.txt, default: feature)
  --status, -s STATUS    Status: Ready, Editing, Implementing, Postponed (default: Ready)
  --assigned-to, -a EMAIL  Email of person assigned to task (optional)
  --issue URL            Issue tracker URL (e.g., GitHub issue URL)
  --labels, -l LABELS    Comma-separated labels
  --deps DEPS            Comma-separated dependency task numbers
  --verifies VERIFIES    Comma-separated task IDs this task manually verifies
                         (for issue_type: manual_verification)
  --file-ref REF         Append a file reference; repeatable. REF format:
                         PATH | PATH:N | PATH:N-M | PATH:N-M^N-M^...
                         (^ joins multiple ranges on the same path).
  --auto-merge           When used with --file-ref and --commit, fold any
                         pending Ready/Editing task that already references
                         the same file path(s) into the new task. Reuses
                         the aitask_fold_* scripts.
  --no-auto-merge        (default) Warn about matching tasks but do NOT
                         fold them. Use with --file-ref to preview.
  --parent, -P NUM       Create as child of specified parent task number
  --no-sibling-dep       Don't auto-add dependency on previous sibling (for child tasks)
  --commit               Claim real ID and commit to git immediately (auto-finalize)
  --finalize FILE        Finalize a specific draft from aitasks/new/ (claim ID, move, commit)
  --finalize-all         Finalize all drafts in aitasks/new/
  --silent               Output only the created filename (for scripting)
  --help, -h             Show this help

Draft workflow:
  By default (without --commit), batch mode creates a draft in aitasks/new/.
  Drafts use timestamp-based names and have no real task number.
  Use --finalize or --finalize-all to assign real IDs and commit.
  The --commit flag auto-finalizes immediately (requires network).

Examples:
  # Interactive mode (supports draft management)
  ./aitask_create.sh

  # Batch mode - creates draft (no network needed)
  ./aitask_create.sh --batch --name "fix_login_bug" --desc "Fix the login issue"

  # Batch mode - auto-finalize with real ID (requires network)
  ./aitask_create.sh --batch --name "add_feature" --desc "Add new feature" \
      --priority high --effort medium --type feature --labels "ui,urgent" --commit

  # Finalize a specific draft
  ./aitask_create.sh --batch --finalize draft_20260213_1423_fix_login.md

  # Finalize all pending drafts
  ./aitask_create.sh --batch --finalize-all

  # Create a child task of parent t1
  ./aitask_create.sh --batch --parent 1 --name "first_subtask" --desc "First subtask"

  # Create child without sibling dependency
  ./aitask_create.sh --batch --parent 1 --name "parallel_task" --desc "Can run in parallel" --no-sibling-dep

  # Read description from stdin
  echo "Long description here" | ./aitask_create.sh --batch --name "my_task" --desc-file -
EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --batch) BATCH_MODE=true; shift ;;
            --name|-n) BATCH_NAME="$2"; shift 2 ;;
            --desc|-d) BATCH_DESC="$2"; shift 2 ;;
            --desc-file) BATCH_DESC_FILE="$2"; shift 2 ;;
            --priority|-p) BATCH_PRIORITY="$2"; shift 2 ;;
            --effort|-e) BATCH_EFFORT="$2"; shift 2 ;;
            --type|-t) BATCH_TYPE="$2"; shift 2 ;;
            --status|-s) BATCH_STATUS="$2"; shift 2 ;;
            --labels|-l) BATCH_LABELS="$2"; shift 2 ;;
            --deps) BATCH_DEPS="$2"; shift 2 ;;
            --verifies) BATCH_VERIFIES="$2"; shift 2 ;;
            --parent|-P) BATCH_PARENT="$2"; shift 2 ;;
            --no-sibling-dep) BATCH_NO_SIBLING_DEP=true; shift ;;
            --assigned-to|-a) BATCH_ASSIGNED_TO="$2"; shift 2 ;;
            --issue) BATCH_ISSUE="$2"; shift 2 ;;
            --pull-request) BATCH_PULL_REQUEST="$2"; shift 2 ;;
            --contributor) BATCH_CONTRIBUTOR="$2"; shift 2 ;;
            --contributor-email) BATCH_CONTRIBUTOR_EMAIL="$2"; shift 2 ;;
            --file-ref) validate_file_ref "$2"; BATCH_FILE_REFS+=("$2"); shift 2 ;;
            --auto-merge) BATCH_AUTO_MERGE=true; shift ;;
            --no-auto-merge) BATCH_AUTO_MERGE=false; shift ;;
            --commit) BATCH_COMMIT=true; shift ;;
            --finalize) BATCH_FINALIZE="$2"; shift 2 ;;
            --finalize-all) BATCH_FINALIZE_ALL=true; shift ;;
            --silent) BATCH_SILENT=true; shift ;;
            --help|-h) show_help; exit 0 ;;
            *) die "Unknown option: $1" ;;
        esac
    done
}

# --- Step 1: Task Number Functions ---
# Note: get_next_task_number() removed. Parent task IDs are now assigned via
# aitask_claim_id.sh (atomic counter) during finalization.
# get_next_task_number_local() is defined later as a fallback.
# Child task IDs use get_next_child_number() (local scan + mkdir-based lock).
# The lock serializes concurrent child creation for the same parent, which can
# happen when the planning workflow creates multiple children in parallel.

# --- Parent/Child Task Functions ---

# Check if a task is a parent (has child directory)
is_parent_task() {
    local task_num="$1"
    [[ -d "$TASK_DIR/t${task_num}" ]]
}

# Get parent task file path from task number
get_parent_task_file() {
    local parent_num="$1"
    local parent_file
    parent_file=$(ls "$TASK_DIR"/t${parent_num}_*.md 2>/dev/null | head -1)
    echo "$parent_file"
}

# Get next child number for a parent task
get_next_child_number() {
    local parent_num="$1"
    local child_dir="$TASK_DIR/t${parent_num}"
    local max_child=0
    local num

    # Check active children
    if [[ -d "$child_dir" ]]; then
        for f in "$child_dir"/t${parent_num}_*_*.md; do
            [[ -e "$f" ]] || continue
            num=$(basename "$f" | grep -oE "^t${parent_num}_[0-9]+" | sed "s/t${parent_num}_//")
            [[ -n "$num" && "$num" -gt "$max_child" ]] && max_child="$num"
        done
    fi

    # Check archived children
    if [[ -d "$ARCHIVED_DIR/t${parent_num}" ]]; then
        for f in "$ARCHIVED_DIR/t${parent_num}"/t${parent_num}_*_*.md; do
            [[ -e "$f" ]] || continue
            num=$(basename "$f" | grep -oE "^t${parent_num}_[0-9]+" | sed "s/t${parent_num}_//")
            [[ -n "$num" && "$num" -gt "$max_child" ]] && max_child="$num"
        done
    fi

    # Check compressed archive for children
    if [[ -n "$ARCHIVE_FILE" && -f "$ARCHIVE_FILE" ]]; then
        while IFS= read -r line; do
            num=$(echo "$line" | grep -oE "t${parent_num}_[0-9]+" | head -1 | sed "s/t${parent_num}_//")
            [[ -n "$num" && "$num" -gt "$max_child" ]] && max_child="$num"
        done < <(_archive_list "$ARCHIVE_FILE" | grep -E "t${parent_num}/t${parent_num}_[0-9]+")
    fi

    echo $((max_child + 1))
}

# Acquire per-parent lock for child task creation (prevents parallel races).
# Uses mkdir which is atomic on POSIX (Linux + macOS).
acquire_child_lock() {
    local parent_num="$1"
    local lock_dir="/tmp/aitask_child_lock_${parent_num}"
    local max_retries=20
    local retry=0

    while ! mkdir "$lock_dir" 2>/dev/null; do
        retry=$((retry + 1))
        if [[ $retry -ge $max_retries ]]; then
            die "Failed to acquire child creation lock for parent $parent_num after $max_retries attempts"
        fi
        # Check for stale lock (older than 120 seconds)
        # stat -c %Y is GNU (Linux), stat -f %m is BSD (macOS)
        if [[ -d "$lock_dir" ]]; then
            local lock_age
            lock_age=$(( $(date +%s) - $(stat -c %Y "$lock_dir" 2>/dev/null || stat -f %m "$lock_dir" 2>/dev/null || echo "0") ))
            if [[ "$lock_age" -gt 120 ]]; then
                warn "Removing stale child lock for parent $parent_num (age: ${lock_age}s)"
                rmdir "$lock_dir" 2>/dev/null || true
                continue
            fi
        fi
        sleep 0.5
    done
}

release_child_lock() {
    local parent_num="$1"
    local lock_dir="/tmp/aitask_child_lock_${parent_num}"
    rmdir "$lock_dir" 2>/dev/null || true
}

# Interactive selection of parent task
select_parent_task() {
    local tasks
    # Get all tasks (including all statuses) for parent selection
    tasks=$("$SCRIPT_DIR/aitask_ls.sh" -v -s all 99 2>/dev/null || echo "")

    if [[ -z "$tasks" ]]; then
        echo ""
        return
    fi

    local options
    options=$(echo -e "None - create standalone task\n$tasks")

    local selected
    selected=$(echo "$options" | fzf --prompt="Parent task: " --height=15 --no-info \
        --header="Select parent task (or None for standalone)")

    if [[ -z "$selected" ]] || echo "$selected" | grep -q "^None"; then
        echo ""
        return
    fi

    # Extract task number from selected line (format: t10_name.md [...])
    echo "$selected" | grep -oE '^t[0-9]+' | sed 's/t//'
}

# Update parent's children_to_implement list
update_parent_children_to_implement() {
    local parent_num="$1"
    local child_id="$2"  # e.g., "t1_2"

    local parent_file
    parent_file=$(get_parent_task_file "$parent_num")

    if [[ -z "$parent_file" || ! -f "$parent_file" ]]; then
        echo -e "${YELLOW}Warning: Could not find parent task t$parent_num to update${NC}" >&2
        return 1
    fi

    # Read current children_to_implement from parent file
    local current_children=""
    while IFS= read -r line; do
        if [[ "$line" =~ ^children_to_implement: ]]; then
            # Extract list: [t1_1, t1_2] -> t1_1,t1_2
            current_children=$(parse_yaml_list "$(echo "$line" | sed 's/children_to_implement://')")
            break
        fi
    done < "$parent_file"

    # Add new child to list
    if [[ -z "$current_children" ]]; then
        current_children="$child_id"
    else
        current_children="$current_children,$child_id"
    fi

    # Update the parent file using aitask_update.sh if available, otherwise inline update.
    # Route stdout to stderr so silent callers (e.g. --silent mode capturing $(aitask_create.sh))
    # don't pick up the "Updated: <file>" announcement as if it were the created filename.
    if [[ -x "$SCRIPT_DIR/aitask_update.sh" ]]; then
        "$SCRIPT_DIR/aitask_update.sh" --batch "$parent_num" --add-child "$child_id" >&2 2>/dev/null || {
            # Fallback: inline update if aitask_update.sh doesn't support --add-child yet
            update_parent_children_inline "$parent_file" "$current_children"
        }
    else
        update_parent_children_inline "$parent_file" "$current_children"
    fi
}

# Inline update of parent's children_to_implement (fallback)
update_parent_children_inline() {
    local parent_file="$1"
    local children_list="$2"

    local children_yaml
    children_yaml=$(format_yaml_list "$children_list")

    # Read file content
    local content
    content=$(cat "$parent_file")

    # Check if children_to_implement already exists
    if grep -q "^children_to_implement:" "$parent_file"; then
        # Replace existing line
        content=$(echo "$content" | sed "s/^children_to_implement:.*$/children_to_implement: $children_yaml/")
    else
        # Add after labels line (before created_at)
        content=$(echo "$content" | awk -v line="children_to_implement: $children_yaml" '/^labels:/{print; print line; next}1')
    fi

    # Update timestamp
    local timestamp
    timestamp=$(get_timestamp)
    content=$(echo "$content" | sed "s/^updated_at:.*$/updated_at: $timestamp/")

    # Write back
    echo "$content" > "$parent_file"
}

# Create child task file in parent's subdirectory
create_child_task_file() {
    local parent_num="$1"
    local child_num="$2"
    local task_name="$3"
    local priority="$4"
    local effort="$5"
    local deps="$6"
    local description="$7"
    local issue_type="$8"
    local status="$9"
    local labels="${10}"
    local issue="${11:-}"
    local pull_request="${12:-}"
    local contributor="${13:-}"
    local contributor_email="${14:-}"
    local file_references="${15:-}"
    local verifies="${16:-}"

    local child_dir="$TASK_DIR/t${parent_num}"
    mkdir -p "$child_dir"

    local child_id="t${parent_num}_${child_num}"
    local filename="${child_id}_${task_name}.md"
    local filepath="$child_dir/$filename"

    local timestamp
    timestamp=$(get_timestamp)

    local deps_yaml
    deps_yaml=$(format_yaml_list "$deps")

    local labels_yaml
    labels_yaml=$(format_yaml_list "$labels")

    # Create the file with YAML front matter (same format as regular tasks)
    {
        echo "---"
        echo "priority: $priority"
        echo "effort: $effort"
        echo "depends: $deps_yaml"
        echo "issue_type: $issue_type"
        echo "status: $status"
        echo "labels: $labels_yaml"
        # Only write verifies if present
        if [[ -n "$verifies" ]]; then
            local verifies_yaml
            verifies_yaml=$(format_yaml_list "$verifies")
            echo "verifies: $verifies_yaml"
        fi
        # Only write file_references if present
        if [[ -n "$file_references" ]]; then
            local file_refs_yaml
            file_refs_yaml=$(format_yaml_list "$file_references")
            echo "file_references: $file_refs_yaml"
        fi
        # Only write issue if present
        if [[ -n "$issue" ]]; then
            echo "issue: $issue"
        fi
        if [[ -n "$pull_request" ]]; then
            echo "pull_request: $pull_request"
        fi
        if [[ -n "$contributor" ]]; then
            echo "contributor: $contributor"
        fi
        if [[ -n "$contributor_email" ]]; then
            echo "contributor_email: $contributor_email"
        fi
        echo "created_at: $timestamp"
        echo "updated_at: $timestamp"
        echo "---"
        echo ""
        echo "$description"
    } > "$filepath"

    echo "$filepath"
}

# --- Draft and Finalization Functions ---

# Generate draft filename with timestamp
get_draft_filename() {
    local task_name="$1"
    local timestamp
    timestamp=$(date '+%Y%m%d_%H%M')
    echo "draft_${timestamp}_${task_name}.md"
}

# Create a draft task file in DRAFT_DIR
create_draft_file() {
    local task_name="$1"
    local priority="$2"
    local effort="$3"
    local deps="$4"
    local description="$5"
    local issue_type="$6"
    local status="$7"
    local labels="$8"
    local assigned_to="${9:-}"
    local issue="${10:-}"
    local parent_num="${11:-}"
    local pull_request="${12:-}"
    local contributor="${13:-}"
    local contributor_email="${14:-}"
    local file_references="${15:-}"
    local verifies="${16:-}"

    mkdir -p "$DRAFT_DIR"

    local draft_name
    draft_name=$(get_draft_filename "$task_name")
    local filepath="$DRAFT_DIR/$draft_name"

    local timestamp
    timestamp=$(get_timestamp)

    local deps_yaml
    deps_yaml=$(format_yaml_list "$deps")

    local labels_yaml
    labels_yaml=$(format_yaml_list "$labels")

    {
        echo "---"
        echo "priority: $priority"
        echo "effort: $effort"
        echo "depends: $deps_yaml"
        echo "issue_type: $issue_type"
        echo "status: $status"
        echo "labels: $labels_yaml"
        # Only write verifies if present
        if [[ -n "$verifies" ]]; then
            local verifies_yaml
            verifies_yaml=$(format_yaml_list "$verifies")
            echo "verifies: $verifies_yaml"
        fi
        if [[ -n "$file_references" ]]; then
            local file_refs_yaml
            file_refs_yaml=$(format_yaml_list "$file_references")
            echo "file_references: $file_refs_yaml"
        fi
        echo "draft: true"
        if [[ -n "$assigned_to" ]]; then
            echo "assigned_to: $assigned_to"
        fi
        if [[ -n "$issue" ]]; then
            echo "issue: $issue"
        fi
        if [[ -n "$pull_request" ]]; then
            echo "pull_request: $pull_request"
        fi
        if [[ -n "$contributor" ]]; then
            echo "contributor: $contributor"
        fi
        if [[ -n "$contributor_email" ]]; then
            echo "contributor_email: $contributor_email"
        fi
        if [[ -n "$parent_num" ]]; then
            echo "parent: $parent_num"
        fi
        echo "created_at: $timestamp"
        echo "updated_at: $timestamp"
        echo "---"
        echo ""
        echo "$description"
    } > "$filepath"

    echo "$filepath"
}

# Extract task name from a draft filename
# draft_20260213_1423_fix_login.md -> fix_login
extract_name_from_draft() {
    local draft_file="$1"
    local basename_f
    basename_f=$(basename "$draft_file" .md)
    # Remove "draft_YYYYMMDD_HHMM_" prefix
    echo "$basename_f" | sed 's/^draft_[0-9]*_[0-9]*_//'
}

# Extract parent number from draft frontmatter (if it's a child task draft)
extract_parent_from_draft() {
    local draft_path="$1"
    local in_yaml=false
    while IFS= read -r line; do
        if [[ "$line" == "---" ]]; then
            if [[ "$in_yaml" == true ]]; then break; fi
            in_yaml=true
            continue
        fi
        if [[ "$in_yaml" == true && "$line" =~ ^parent:[[:space:]]*(.*) ]]; then
            echo "${BASH_REMATCH[1]}" | tr -d '[:space:]'
            return
        fi
    done < "$draft_path"
    echo ""
}

# Finalize a single draft: claim real ID, move to aitasks/, commit
finalize_draft() {
    local draft_path="$1"
    local silent="${2:-false}"

    if [[ ! -f "$draft_path" ]]; then
        die "Draft file not found: $draft_path"
    fi

    local task_name
    task_name=$(extract_name_from_draft "$draft_path")
    local parent_num
    parent_num=$(extract_parent_from_draft "$draft_path")

    local task_id filepath

    if [[ -n "$parent_num" ]]; then
        # Child task: lock to prevent parallel races on child number assignment
        acquire_child_lock "$parent_num"
        trap 'release_child_lock "$parent_num"' EXIT

        local child_num
        child_num=$(get_next_child_number "$parent_num")

        task_id="t${parent_num}_${child_num}"
        local child_dir="$TASK_DIR/t${parent_num}"
        mkdir -p "$child_dir"
        filepath="$child_dir/${task_id}_${task_name}.md"

        # Copy content, remove draft-specific fields
        sed '/^draft: true$/d; /^parent: .*$/d' "$draft_path" > "$filepath"

        # Update parent's children_to_implement
        update_parent_children_to_implement "$parent_num" "$task_id"

        rm -f "$draft_path"

        if [[ "$silent" != "true" ]]; then
            success "Finalized child task: $filepath (ID: $task_id)"
        fi

        # Git commit
        task_git add "$filepath"
        local parent_file
        parent_file=$(get_parent_task_file "$parent_num")
        [[ -n "$parent_file" ]] && task_git add "$parent_file" 2>/dev/null || true
        task_git add "$LABELS_FILE" 2>/dev/null || true
        local humanized_name
        humanized_name=$(echo "$task_name" | tr '_' ' ')
        task_git commit -m "ait: Add child task ${task_id}: ${humanized_name}"

        run_auto_merge_if_needed "${parent_num}_${child_num}" "$filepath"

        release_child_lock "$parent_num"
        trap - EXIT
    else
        # Parent task: claim from atomic counter
        local claimed_id
        local claim_stderr
        claim_stderr=$(mktemp)
        claimed_id=$("$SCRIPT_DIR/aitask_claim_id.sh" --claim 2>"$claim_stderr") || {
            local claim_err
            claim_err=$(cat "$claim_stderr")
            rm -f "$claim_stderr"

            if [[ -t 0 ]]; then
                # Interactive mode: warn and offer local scan fallback
                echo "" >&2
                warn "Atomic ID counter failed: ${claim_err:-unknown error}" >&2
                warn "Local scan may cause duplicate IDs if other users are active." >&2
                echo "" >&2
                printf "Use local scan anyway? (y/N): " >&2
                local answer
                read -r answer
                if [[ "$answer" =~ ^[Yy]$ ]]; then
                    claimed_id=$(get_next_task_number_local)
                else
                    die "Aborted. Fix the remote counter or run 'ait setup'."
                fi
            else
                # Batch/non-interactive mode: fail hard
                die "Atomic ID counter failed: ${claim_err:-unknown error}. Run 'ait setup' to initialize the counter."
            fi
        }
        rm -f "$claim_stderr" 2>/dev/null

        task_id="t${claimed_id}"
        filepath="$TASK_DIR/${task_id}_${task_name}.md"

        # Copy content, remove draft field
        sed '/^draft: true$/d' "$draft_path" > "$filepath"

        rm -f "$draft_path"

        # Store email if present in frontmatter
        local assigned_email
        assigned_email=$(grep '^assigned_to:' "$filepath" 2>/dev/null | sed 's/assigned_to: *//' || true)
        if [[ -n "$assigned_email" ]]; then
            add_email_to_file "$assigned_email"
        fi

        if [[ "$silent" != "true" ]]; then
            success "Finalized: $filepath (ID: $task_id)"
        fi

        # Git commit
        task_git add "$filepath"
        task_git add "$LABELS_FILE" 2>/dev/null || true
        local humanized_name
        humanized_name=$(echo "$task_name" | tr '_' ' ')
        if [[ "$silent" == "true" ]]; then
            task_git commit --quiet -m "ait: Add task ${task_id}: ${humanized_name}" >&2
        else
            task_git commit -m "ait: Add task ${task_id}: ${humanized_name}"
        fi

        run_auto_merge_if_needed "$claimed_id" "$filepath"
    fi

    if [[ "$silent" == "true" ]]; then
        echo "$filepath"
    fi
}

# Finalize all drafts in DRAFT_DIR
finalize_all_drafts() {
    local silent="${1:-false}"

    if [[ ! -d "$DRAFT_DIR" ]] || ! ls "$DRAFT_DIR"/draft_*.md &>/dev/null; then
        if [[ "$silent" != "true" ]]; then
            info "No draft files found in $DRAFT_DIR/"
        fi
        return 0
    fi

    local count=0
    for draft_file in "$DRAFT_DIR"/draft_*.md; do
        [[ -e "$draft_file" ]] || continue
        finalize_draft "$draft_file" "$silent"
        count=$((count + 1))
    done

    if [[ "$silent" != "true" ]]; then
        success "Finalized $count draft(s)"
    fi
}

# Local-only task number scan (fallback when atomic counter is unavailable)
get_next_task_number_local() {
    local max_num=0
    local num

    if ls "$TASK_DIR"/t*_*.md &>/dev/null; then
        for f in "$TASK_DIR"/t*_*.md; do
            num=$(basename "$f" | grep -oE '^t[0-9]+' | sed 's/t//')
            [[ "$num" -gt "$max_num" ]] && max_num="$num"
        done
    fi

    if ls "$ARCHIVED_DIR"/t*_*.md &>/dev/null; then
        for f in "$ARCHIVED_DIR"/t*_*.md; do
            num=$(basename "$f" | grep -oE '^t[0-9]+' | sed 's/t//')
            [[ "$num" -gt "$max_num" ]] && max_num="$num"
        done
    fi

    if [[ -n "$ARCHIVE_FILE" && -f "$ARCHIVE_FILE" ]]; then
        while IFS= read -r line; do
            num=$(echo "$line" | grep -oE 't[0-9]+' | head -1 | sed 's/t//')
            [[ -n "$num" && "$num" -gt "$max_num" ]] && max_num="$num"
        done < <(_archive_list "$ARCHIVE_FILE" | grep -E 't[0-9]+')
    fi

    echo $((max_num + 1))
}

# List draft files with summary info
list_drafts() {
    if [[ ! -d "$DRAFT_DIR" ]] || ! ls "$DRAFT_DIR"/draft_*.md &>/dev/null; then
        return 1
    fi

    local drafts=()
    for f in "$DRAFT_DIR"/draft_*.md; do
        [[ -e "$f" ]] || continue
        local name parent_info=""
        name=$(extract_name_from_draft "$f")
        local parent
        parent=$(extract_parent_from_draft "$f")
        [[ -n "$parent" ]] && parent_info=" (child of t$parent)"
        drafts+=("$(basename "$f") - ${name}${parent_info}")
    done

    if [[ ${#drafts[@]} -eq 0 ]]; then
        return 1
    fi

    printf '%s\n' "${drafts[@]}"
    return 0
}

# --- Step 2: Metadata Collection ---

select_priority() {
    echo -e "high\nmedium\nlow" | fzf --prompt="Priority: " --height=10 --no-info --header="Select task priority"
}

select_effort() {
    echo -e "low\nmedium\nhigh" | fzf --prompt="Effort: " --height=10 --no-info --header="Select estimated effort"
}

select_issue_type() {
    get_valid_task_types | fzf --prompt="Issue type: " --height=10 --no-info --header="Select issue type"
}

select_status() {
    echo -e "Ready\nEditing\nImplementing\nPostponed" | fzf --prompt="Status: " --height=12 --no-info --header="Select task status"
}

LABELS_FILE="aitasks/metadata/labels.txt"
EMAILS_FILE="aitasks/metadata/emails.txt"
TASK_TYPES_FILE="aitasks/metadata/task_types.txt"

ensure_emails_file() {
    local dir
    dir=$(dirname "$EMAILS_FILE")
    mkdir -p "$dir"
    touch "$EMAILS_FILE"
}

add_email_to_file() {
    local email="$1"
    ensure_emails_file
    if [[ -n "$email" ]] && ! grep -qFx "$email" "$EMAILS_FILE" 2>/dev/null; then
        echo "$email" >> "$EMAILS_FILE"
        sort -u "$EMAILS_FILE" -o "$EMAILS_FILE"
    fi
}

sanitize_label() {
    local label="$1"
    # Convert to lowercase, keep only valid chars (a-z, 0-9, hyphen, underscore)
    echo "$label" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9_-]//g'
}

ensure_labels_file() {
    local dir
    dir=$(dirname "$LABELS_FILE")
    mkdir -p "$dir"
    touch "$LABELS_FILE"
}

get_existing_labels() {
    ensure_labels_file
    if [[ -s "$LABELS_FILE" ]]; then
        sort -u "$LABELS_FILE"
    fi
}

add_label_to_file() {
    local label="$1"
    ensure_labels_file
    # Add label if not already present
    if ! grep -qFx "$label" "$LABELS_FILE" 2>/dev/null; then
        echo "$label" >> "$LABELS_FILE"
        # Keep file sorted
        sort -u "$LABELS_FILE" -o "$LABELS_FILE"
    fi
}

# --- Task Types Management ---

ensure_task_types_file() {
    local dir
    dir=$(dirname "$TASK_TYPES_FILE")
    mkdir -p "$dir"
    touch "$TASK_TYPES_FILE"
}

get_valid_task_types() {
    ensure_task_types_file
    if [[ -s "$TASK_TYPES_FILE" ]]; then
        sort -u "$TASK_TYPES_FILE"
    else
        # Fallback defaults if file is empty
        printf '%s\n' "bug" "feature" "refactor"
    fi
}

validate_task_type() {
    local type="$1"
    if ! grep -qFx "$type" <(get_valid_task_types); then
        local valid
        valid=$(get_valid_task_types | tr '\n' ', ' | sed 's/,$//')
        die "Invalid type: $type (must be one of: $valid)"
    fi
}

# Get labels interactively - sets SELECTED_LABELS variable
# This function works directly with the terminal, not via command substitution
get_labels_interactive() {
    # Disable exit-on-error for this function (fzf and file operations can return non-zero)
    set +e

    SELECTED_LABELS=""
    local selected_labels=()

    # Offer the previous-task labels as a one-time menu entry in the first
    # iteration. If the user selects it, we seed the selection with those
    # labels and suppress the entry on subsequent loops.
    local prev_labels_csv=""
    local prev_labels_display=""
    local offered_prev=false
    prev_labels_csv=$(get_last_used_labels 2>/dev/null || true)
    if [[ -n "$prev_labels_csv" ]]; then
        prev_labels_display=">> Use labels from previous task (${prev_labels_csv})"
    fi

    while true; do
        # Build options list, filtering out already selected labels
        local existing_labels
        existing_labels=$(get_existing_labels)

        local available_labels=""
        if [[ -n "$existing_labels" ]]; then
            # Filter out already selected labels
            while IFS= read -r lbl; do
                local is_selected=false
                for sel in "${selected_labels[@]}"; do
                    if [[ "$sel" == "$lbl" ]]; then
                        is_selected=true
                        break
                    fi
                done
                if [[ "$is_selected" == "false" ]]; then
                    if [[ -n "$available_labels" ]]; then
                        available_labels="${available_labels}"$'\n'"${lbl}"
                    else
                        available_labels="$lbl"
                    fi
                fi
            done <<< "$existing_labels"
        fi

        local options
        if [[ -n "$available_labels" ]]; then
            options=">> Done adding labels"$'\n'">> Add new label"$'\n'"$available_labels"
        else
            options=">> Done adding labels"$'\n'">> Add new label"
        fi
        if [[ -n "$prev_labels_display" && "$offered_prev" == "false" ]]; then
            options="${prev_labels_display}"$'\n'"${options}"
        fi

        # Select label using fzf
        local selected
        selected=$(printf "%s" "$options" | fzf --prompt="Select label: " --height=15 --no-info --header="Select existing label or add new")

        if [[ -n "$selected" ]]; then
            local label=""

            if [[ -n "$prev_labels_display" && "$selected" == "$prev_labels_display" ]]; then
                # Seed current selection with the previous labels and continue
                # the loop; the entry is suppressed on subsequent iterations.
                local _prev_split=()
                IFS=',' read -ra _prev_split <<< "$prev_labels_csv"
                for _pl in "${_prev_split[@]}"; do
                    if [[ -n "$_pl" ]]; then
                        selected_labels+=("$_pl")
                        success "Added label: $_pl"
                    fi
                done
                offered_prev=true
                continue
            elif [[ "$selected" == ">> Done adding labels" ]]; then
                break
            elif [[ "$selected" == ">> Add new label" ]]; then
                local new_label
                read -erp "Enter new label: " new_label
                if [[ -n "$new_label" ]]; then
                    # Sanitize the label using sed (more portable than tr -cd with hyphen)
                    label=$(echo "$new_label" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9_-]//g') || true
                    if [[ -n "$label" ]]; then
                        # Add to labels file
                        ensure_labels_file
                        if ! grep -qFx "$label" "$LABELS_FILE" 2>/dev/null; then
                            echo "$label" >> "$LABELS_FILE"
                            sort -u "$LABELS_FILE" -o "$LABELS_FILE"
                        fi
                    fi
                fi
            else
                label="$selected"
            fi

            if [[ -n "$label" ]]; then
                selected_labels+=("$label")
                success "Added label: $label"
            fi
        fi

        # Show current selection
        if [[ ${#selected_labels[@]} -gt 0 ]]; then
            info "Current labels: ${selected_labels[*]}"
        fi

        # Ask to continue or done
        local continue_choice
        continue_choice=$(printf "Add another label\nDone with labels" | fzf --prompt="Continue? " --height=8 --no-info)

        if [[ "$continue_choice" == "Done with labels" ]] || [[ -z "$continue_choice" ]]; then
            break
        fi
    done

    # Set result in global variable
    if [[ ${#selected_labels[@]} -gt 0 ]]; then
        local IFS=','
        SELECTED_LABELS="${selected_labels[*]}"
    else
        SELECTED_LABELS=""
    fi

    # Re-enable exit-on-error
    set -e
}

select_dependencies() {
    local parent_num="${1:-}"  # Optional: parent task number for child tasks

    local tasks
    # Use --status all to show all tasks for dependency selection
    tasks=$("$SCRIPT_DIR/aitask_ls.sh" -v -s all 99 2>/dev/null || echo "")

    # If creating a child task, also list siblings at the top
    local siblings=""
    if [[ -n "$parent_num" ]]; then
        local child_dir="$TASK_DIR/t${parent_num}"
        if [[ -d "$child_dir" ]]; then
            for f in "$child_dir"/t${parent_num}_*_*.md; do
                [[ -e "$f" ]] || continue
                local child_id
                child_id=$(basename "$f" | grep -oE "^t${parent_num}_[0-9]+")
                local child_name
                child_name=$(basename "$f" .md)
                if [[ -n "$siblings" ]]; then
                    siblings="${siblings}"$'\n'"${child_name} (sibling)"
                else
                    siblings="${child_name} (sibling)"
                fi
            done
        fi
    fi

    if [[ -z "$tasks" && -z "$siblings" ]]; then
        echo ""
        return
    fi

    # Build options list
    local options="None - no dependencies"
    if [[ -n "$siblings" ]]; then
        options="${options}"$'\n'"${siblings}"
    fi
    if [[ -n "$tasks" ]]; then
        options="${options}"$'\n'"${tasks}"
    fi

    local selected
    selected=$(echo "$options" | fzf --multi --prompt="Dependencies (Tab to select): " --height=15 --no-info --header="Select task dependencies (Tab=select, Enter=confirm)")

    # Check if "None" was selected or nothing selected
    if [[ -z "$selected" ]] || echo "$selected" | grep -q "^None"; then
        echo ""
        return
    fi

    # Extract task IDs from selected lines
    # For siblings: t1_2_name (sibling) -> t1_2
    # For regular: t10_name.md [...] -> 10
    local deps=""
    while IFS= read -r line; do
        if echo "$line" | grep -q "(sibling)"; then
            # Extract child task ID (e.g., t1_2)
            local child_id
            child_id=$(echo "$line" | grep -oE "^t[0-9]+_[0-9]+")
            if [[ -n "$child_id" ]]; then
                deps="${deps:+$deps,}$child_id"
            fi
        else
            # Extract regular task number
            local task_num
            task_num=$(echo "$line" | grep -oE '^t[0-9]+' | sed 's/t//')
            if [[ -n "$task_num" ]]; then
                deps="${deps:+$deps,}$task_num"
            fi
        fi
    done <<< "$selected"

    echo "$deps"
}

# --- Step 3: Task Name ---

sanitize_name() {
    local name="$1"
    # Convert to lowercase, replace spaces with underscores, remove special chars
    echo "$name" | tr '[:upper:]' '[:lower:]' | tr ' ' '_' | tr -cd 'a-z0-9_' | sed 's/__*/_/g' | sed 's/^_//;s/_$//' | cut -c1-60
}

get_task_name() {
    local name predesc=""
    read -erp "Task name (short, will be sanitized): " name

    # Detect if user accidentally entered a description as the task name
    if [[ ${#name} -gt 50 ]]; then
        warn "You entered a long text (${#name} chars). Is this part of the task description?"
        local choice
        choice=$(echo -e "Yes, it's a description\nNo, it's the task name" | fzf --prompt="Long input: " --height=5 --no-info)
        if [[ "$choice" == "Yes, it's a description" ]]; then
            echo "No problem, I'll keep it for the description. What should be the actual task name?" >&2
            predesc="$name"
            read -erp "Task name (short, will be sanitized): " name
        fi
    fi

    local sanitized
    sanitized=$(sanitize_name "$name")

    # Default to unnamed_task if empty
    [[ -z "$sanitized" ]] && sanitized="unnamed_task"

    # Output: line 1 = sanitized name, line 2 = predesc text (empty if none)
    echo "$sanitized"
    echo "$predesc"
}

# --- Step 4-5: Task Definition Loop ---

get_task_definition() {
    local task_desc="${1:-}"

    if [[ -n "$task_desc" ]]; then
        info "Pre-populated description with your earlier text. You can add more or finish." >&2
    fi

    # Track file refs across all outer rounds (for structured file_references output)
    local -a all_file_refs=()
    if [[ ${#BATCH_FILE_REFS[@]} -gt 0 ]]; then
        all_file_refs=("${BATCH_FILE_REFS[@]}")
        info "Pre-populated file references: ${all_file_refs[*]}" >&2
    fi

    while true; do
        # Step 4: Get description block
        echo "" >&2
        read -erp "Enter description (or press Enter to skip): " desc_block

        if [[ -n "$desc_block" ]]; then
            if [[ -n "$task_desc" ]]; then
                # Add blank line before new description block
                task_desc="$task_desc

$desc_block"
            else
                task_desc="$desc_block"
            fi
        fi

        # Step 5: Optional file references loop
        local -a current_round_refs=()
        while true; do
            local add_file
            local menu_opts="Add file reference\nDone with files"
            if [[ ${#current_round_refs[@]} -gt 0 ]]; then
                menu_opts="Add file reference\nRemove file reference\nDone with files"
            fi
            add_file=$(echo -e "$menu_opts" | fzf --prompt="Add file? " --height=8 --no-info)

            if [[ "$add_file" == "Done with files" ]] || [[ -z "$add_file" ]]; then
                break
            elif [[ "$add_file" == "Remove file reference" ]]; then
                # Let user pick which file ref to remove
                local remove_file
                remove_file=$(printf '%s\n' "${current_round_refs[@]}" | fzf --prompt="Remove which file? " --height=12 --no-info)

                if [[ -n "$remove_file" ]]; then
                    # Remove from task_desc (the file path is on its own line)
                    task_desc=$(echo "$task_desc" | grep -vxF "$remove_file")
                    # Remove from tracking array
                    local -a new_refs=()
                    local ref
                    for ref in "${current_round_refs[@]}"; do
                        [[ "$ref" != "$remove_file" ]] && new_refs+=("$ref")
                    done
                    current_round_refs=("${new_refs[@]}")
                    # Also remove from the persistent all_file_refs list
                    local -a new_all=()
                    for ref in "${all_file_refs[@]}"; do
                        [[ "$ref" != "$remove_file" ]] && new_all+=("$ref")
                    done
                    all_file_refs=("${new_all[@]}")
                    success "Removed: $remove_file" >&2
                fi
                continue
            fi

            # Use fzf's built-in file walker for interactive fuzzy finding
            # Redirect from /dev/tty so fzf can detect TTY inside subshell
            local selected_file
            selected_file=$(fzf --prompt="Select file: " --height=20 --preview 'head -50 {}' --walker=file,hidden --walker-skip=.git,node_modules,build < /dev/tty 2>/dev/null || echo "")

            if [[ -n "$selected_file" ]]; then
                if [[ -n "$task_desc" ]]; then
                    task_desc="$task_desc
$selected_file"
                else
                    task_desc="$selected_file"
                fi
                current_round_refs+=("$selected_file")
                all_file_refs+=("$selected_file")
                success "Added: $selected_file" >&2
            fi
        done

        # Ask to continue with more description
        local continue_choice
        continue_choice=$(echo -e "Add more description\nDone - create task" | fzf --prompt="Continue? " --height=8 --no-info)

        if [[ "$continue_choice" == "Done - create task" ]] || [[ -z "$continue_choice" ]]; then
            break
        fi
    done

    # Output task_desc followed by marker line and structured file refs.
    # The caller (run_draft_interactive) splits on __FILE_REFS_MARKER__.
    echo "$task_desc"
    echo "__FILE_REFS_MARKER__"
    local ref
    for ref in "${all_file_refs[@]}"; do
        echo "$ref"
    done
}

# --- Step 6: Create Task File ---

get_timestamp() {
    date '+%Y-%m-%d %H:%M'
}

# Deduplicate a bash array of file-reference strings by exact-string match,
# preserving order of first occurrence. Prints a comma-separated string.
dedup_file_refs() {
    local -n arr_ref=$1
    local -A seen=()
    local -a unique=()
    local item
    for item in "${arr_ref[@]}"; do
        if [[ -z "${seen[$item]:-}" ]]; then
            seen[$item]=1
            unique+=("$item")
        fi
    done
    local IFS=','
    echo "${unique[*]}"
}

# run_auto_merge_if_needed <new_id> <new_file>
#
# After a task has been created + committed, scan the task's file_references
# frontmatter for paths that match any existing pending task via
# aitask_find_by_file.sh. If matches are found, honor --auto-merge by
# delegating to the aitask_fold_* scripts; otherwise warn and skip.
#
# This helper is only invoked from the --batch --commit paths. It is a
# no-op for any of these conditions:
#   - the new task has no file_references
#   - no pending tasks reference any of those paths
#   - BATCH_AUTO_MERGE is false AND there are matches (warn + skip)
run_auto_merge_if_needed() {
    local new_id="$1"
    local new_file="$2"
    new_id="${new_id#t}"

    [[ -f "$new_file" ]] || return 0

    # Collect distinct path-only portions from the new task's file_references.
    local -a paths=()
    local -A seen_paths=()
    local entry entry_path
    while IFS= read -r entry; do
        [[ -z "$entry" ]] && continue
        entry_path="${entry%%:*}"
        [[ -z "$entry_path" ]] && continue
        if [[ -z "${seen_paths[$entry_path]:-}" ]]; then
            seen_paths[$entry_path]=1
            paths+=("$entry_path")
        fi
    done < <(get_file_references "$new_file")

    [[ ${#paths[@]} -eq 0 ]] && return 0

    # Union candidate task IDs across all paths, dedup by id, exclude new_id.
    local -A cand_seen=()
    local -a cand_ids=()
    local -a cand_files=()
    local -A cand_paths_by_id=()
    local p find_out line tid tfile
    for p in "${paths[@]}"; do
        find_out=$("$SCRIPT_DIR/aitask_find_by_file.sh" "$p" 2>/dev/null || true)
        [[ -z "$find_out" ]] && continue
        while IFS= read -r line; do
            [[ "$line" == TASK:* ]] || continue
            tid="${line#TASK:}"
            tfile="${tid#*:}"
            tid="${tid%%:*}"
            [[ -z "$tid" ]] && continue
            [[ "$tid" == "$new_id" ]] && continue
            if [[ -z "${cand_seen[$tid]:-}" ]]; then
                cand_seen[$tid]=1
                cand_ids+=("$tid")
                cand_files+=("$tfile")
                cand_paths_by_id[$tid]="$p"
            fi
        done <<< "$find_out"
    done

    [[ ${#cand_ids[@]} -eq 0 ]] && return 0

    if [[ "$BATCH_AUTO_MERGE" != true && "$BATCH_MODE" != true && -t 0 ]]; then
        info "Found ${#cand_ids[@]} pending task(s) that already reference this file:"
        local prompt_i
        for ((prompt_i = 0; prompt_i < ${#cand_ids[@]}; prompt_i++)); do
            info "  - t${cand_ids[$prompt_i]} (${cand_paths_by_id[${cand_ids[$prompt_i]}]}) → ${cand_files[$prompt_i]}"
        done
        local merge_choice
        merge_choice=$(printf 'Yes, fold them into this task\nNo, keep separate\n' \
            | fzf --prompt="Auto-merge? " --height=6 --no-info \
                  --header="Fold ${#cand_ids[@]} matching task(s) into t${new_id}") || true
        if [[ "$merge_choice" == Yes* ]]; then
            BATCH_AUTO_MERGE=true
        fi
    fi

    if [[ "$BATCH_AUTO_MERGE" != true ]]; then
        warn "Found ${#cand_ids[@]} pending task(s) that already reference this file:"
        local i
        for ((i = 0; i < ${#cand_ids[@]}; i++)); do
            warn "  - t${cand_ids[$i]} (${cand_paths_by_id[${cand_ids[$i]}]}) → ${cand_files[$i]}"
        done
        warn "Auto-merge skipped (pass --auto-merge to fold them into this task)."
        return 0
    fi

    # Validate the candidate set. Exclude-self is belt + braces.
    local validate_out
    validate_out=$("$SCRIPT_DIR/aitask_fold_validate.sh" --exclude-self "$new_id" "${cand_ids[@]}" 2>/dev/null || true)

    local -a valid_ids=()
    local -a valid_files=()
    while IFS= read -r line; do
        [[ -z "$line" ]] && continue
        case "$line" in
            VALID:*)
                local rest="${line#VALID:}"
                local vid="${rest%%:*}"
                local vfile="${rest#*:}"
                valid_ids+=("$vid")
                valid_files+=("$vfile")
                ;;
            INVALID:*)
                local rest="${line#INVALID:}"
                local iid="${rest%%:*}"
                local ireason="${rest#*:}"
                warn "Auto-merge: skipping t${iid} (${ireason})"
                ;;
        esac
    done <<< "$validate_out"

    [[ ${#valid_ids[@]} -eq 0 ]] && return 0

    info "Auto-merging ${#valid_ids[@]} task(s) into t${new_id}..."

    # Body merge: fold_content → update --desc-file -
    "$SCRIPT_DIR/aitask_fold_content.sh" "$new_file" "${valid_files[@]}" \
        | "$SCRIPT_DIR/aitask_update.sh" --batch "$new_id" --desc-file - --silent >/dev/null

    # Mark + commit: fold_mark
    "$SCRIPT_DIR/aitask_fold_mark.sh" --commit-mode fresh "$new_id" "${valid_ids[@]}" >/dev/null

    local joined=""
    local vid
    for vid in "${valid_ids[@]}"; do
        if [[ -n "$joined" ]]; then
            joined="${joined}, t${vid}"
        else
            joined="t${vid}"
        fi
    done
    success "Folded ${joined} into t${new_id}"
}

create_task_file() {
    local task_num="$1"
    local task_name="$2"
    local priority="$3"
    local effort="$4"
    local deps="$5"
    local description="$6"
    local issue_type="$7"
    local status="$8"
    local labels="$9"
    local assigned_to="${10:-}"
    local issue="${11:-}"
    local pull_request="${12:-}"
    local contributor="${13:-}"
    local contributor_email="${14:-}"
    local file_references="${15:-}"
    local verifies="${16:-}"

    local filename="t${task_num}_${task_name}.md"
    local filepath="$TASK_DIR/$filename"

    local timestamp
    timestamp=$(get_timestamp)

    local deps_yaml
    deps_yaml=$(format_yaml_list "$deps")

    local labels_yaml
    labels_yaml=$(format_yaml_list "$labels")

    # Create the file with YAML front matter
    {
        echo "---"
        echo "priority: $priority"
        echo "effort: $effort"
        echo "depends: $deps_yaml"
        echo "issue_type: $issue_type"
        echo "status: $status"
        echo "labels: $labels_yaml"
        # Only write verifies if present
        if [[ -n "$verifies" ]]; then
            local verifies_yaml
            verifies_yaml=$(format_yaml_list "$verifies")
            echo "verifies: $verifies_yaml"
        fi
        # Only write file_references if present
        if [[ -n "$file_references" ]]; then
            local file_refs_yaml
            file_refs_yaml=$(format_yaml_list "$file_references")
            echo "file_references: $file_refs_yaml"
        fi
        # Only write assigned_to if present
        if [[ -n "$assigned_to" ]]; then
            echo "assigned_to: $assigned_to"
        fi
        # Only write issue if present
        if [[ -n "$issue" ]]; then
            echo "issue: $issue"
        fi
        if [[ -n "$pull_request" ]]; then
            echo "pull_request: $pull_request"
        fi
        if [[ -n "$contributor" ]]; then
            echo "contributor: $contributor"
        fi
        if [[ -n "$contributor_email" ]]; then
            echo "contributor_email: $contributor_email"
        fi
        echo "created_at: $timestamp"
        echo "updated_at: $timestamp"
        echo "---"
        echo ""
        echo "$description"
    } > "$filepath"

    echo "$filepath"
}

# --- Step 7: Git Commit ---

commit_task() {
    local filepath="$1"
    local task_num="$2"
    local task_name="$3"

    read -rp "Commit to git? [Y/n] " commit_choice

    if [[ "$commit_choice" != "n" && "$commit_choice" != "N" ]]; then
        local humanized_name
        humanized_name=$(echo "$task_name" | tr '_' ' ')

        task_git add "$filepath"
        task_git add "$LABELS_FILE" 2>/dev/null || true
        task_git commit -m "ait: Add task t${task_num}: ${humanized_name}"

        local commit_hash
        commit_hash=$(task_git rev-parse --short HEAD)
        echo "$commit_hash"
    else
        echo ""
    fi
}

# --- Batch Mode ---

run_batch_mode() {
    # Handle finalize operations first (don't require --name/--desc)
    if [[ "$BATCH_FINALIZE_ALL" == true ]]; then
        finalize_all_drafts "$BATCH_SILENT"
        return
    fi

    if [[ -n "$BATCH_FINALIZE" ]]; then
        local draft_path
        # Accept either just filename or full path
        if [[ -f "$BATCH_FINALIZE" ]]; then
            draft_path="$BATCH_FINALIZE"
        elif [[ -f "$DRAFT_DIR/$BATCH_FINALIZE" ]]; then
            draft_path="$DRAFT_DIR/$BATCH_FINALIZE"
        else
            die "Draft file not found: $BATCH_FINALIZE"
        fi
        finalize_draft "$draft_path" "$BATCH_SILENT"
        return
    fi

    # Regular task creation - ensure task directory exists
    mkdir -p "$TASK_DIR"

    # Validate required fields
    [[ -z "$BATCH_NAME" ]] && die "Batch mode requires --name"

    # Handle description from file
    if [[ -n "$BATCH_DESC_FILE" ]]; then
        if [[ "$BATCH_DESC_FILE" == "-" ]]; then
            BATCH_DESC=$(cat)
        else
            [[ -f "$BATCH_DESC_FILE" ]] || die "Description file not found: $BATCH_DESC_FILE"
            BATCH_DESC=$(cat "$BATCH_DESC_FILE")
        fi
    fi

    [[ -z "$BATCH_DESC" ]] && die "Batch mode requires --desc or --desc-file"

    # Validate enum values
    case "$BATCH_PRIORITY" in
        high|medium|low) ;;
        *) die "Invalid priority: $BATCH_PRIORITY (must be high, medium, or low)" ;;
    esac

    case "$BATCH_EFFORT" in
        low|medium|high) ;;
        *) die "Invalid effort: $BATCH_EFFORT (must be low, medium, or high)" ;;
    esac

    validate_task_type "$BATCH_TYPE"

    case "$BATCH_STATUS" in
        Ready|Editing|Implementing|Postponed) ;;
        *) die "Invalid status: $BATCH_STATUS (must be Ready, Editing, Implementing, or Postponed)" ;;
    esac

    # Sanitize task name
    local task_name
    task_name=$(sanitize_name "$BATCH_NAME")
    [[ -z "$task_name" ]] && task_name="unnamed_task"

    local filepath
    local task_id

    if [[ "$BATCH_COMMIT" == true ]]; then
        # --commit: auto-finalize immediately (claims real ID, requires network)
        if [[ -n "$BATCH_PARENT" ]]; then
            # Child task: create directly (parent ID is already unique)
            # Lock to prevent parallel races on child number assignment
            acquire_child_lock "$BATCH_PARENT"
            trap 'release_child_lock "$BATCH_PARENT"' EXIT

            local parent_file
            parent_file=$(get_parent_task_file "$BATCH_PARENT")
            if [[ -z "$parent_file" || ! -f "$parent_file" ]]; then
                release_child_lock "$BATCH_PARENT"
                trap - EXIT
                die "Parent task t$BATCH_PARENT not found"
            fi

            local child_num
            child_num=$(get_next_child_number "$BATCH_PARENT")

            # Add default sibling dependency unless --no-sibling-dep
            if [[ "$BATCH_NO_SIBLING_DEP" != true && "$child_num" -gt 1 ]]; then
                local prev_sibling="t${BATCH_PARENT}_$((child_num - 1))"
                if [[ -n "$BATCH_DEPS" ]]; then
                    BATCH_DEPS="$prev_sibling,$BATCH_DEPS"
                else
                    BATCH_DEPS="$prev_sibling"
                fi
            fi

            local deduped_file_refs
            deduped_file_refs=$(dedup_file_refs BATCH_FILE_REFS)
            filepath=$(create_child_task_file "$BATCH_PARENT" "$child_num" "$task_name" \
                "$BATCH_PRIORITY" "$BATCH_EFFORT" "$BATCH_DEPS" "$BATCH_DESC" \
                "$BATCH_TYPE" "$BATCH_STATUS" "$BATCH_LABELS" "$BATCH_ISSUE" \
                "$BATCH_PULL_REQUEST" "$BATCH_CONTRIBUTOR" "$BATCH_CONTRIBUTOR_EMAIL" \
                "$deduped_file_refs" "$BATCH_VERIFIES")

            task_id="t${BATCH_PARENT}_${child_num}"
            update_parent_children_to_implement "$BATCH_PARENT" "$task_id"

            local humanized_name
            humanized_name=$(echo "$task_name" | tr '_' ' ')
            task_git add "$filepath"
            task_git add "$parent_file" 2>/dev/null || true
            task_git add "$LABELS_FILE" 2>/dev/null || true
            if [[ "$BATCH_SILENT" == true ]]; then
                task_git commit --quiet -m "ait: Add child task ${task_id}: ${humanized_name}" >&2
            else
                task_git commit -m "ait: Add child task ${task_id}: ${humanized_name}"
            fi

            run_auto_merge_if_needed "${BATCH_PARENT}_${child_num}" "$filepath"

            release_child_lock "$BATCH_PARENT"
            trap - EXIT
        else
            # Parent task: claim real ID from atomic counter
            local claimed_id
            local claim_stderr
            claim_stderr=$(mktemp)
            claimed_id=$("$SCRIPT_DIR/aitask_claim_id.sh" --claim 2>"$claim_stderr") || {
                local claim_err
                claim_err=$(cat "$claim_stderr")
                rm -f "$claim_stderr"
                die "Atomic ID counter failed: ${claim_err:-unknown error}. Run 'ait setup' to initialize the counter."
            }
            rm -f "$claim_stderr" 2>/dev/null

            local deduped_file_refs
            deduped_file_refs=$(dedup_file_refs BATCH_FILE_REFS)
            filepath=$(create_task_file "$claimed_id" "$task_name" "$BATCH_PRIORITY" "$BATCH_EFFORT" \
                "$BATCH_DEPS" "$BATCH_DESC" "$BATCH_TYPE" "$BATCH_STATUS" "$BATCH_LABELS" "$BATCH_ASSIGNED_TO" "$BATCH_ISSUE" \
                "$BATCH_PULL_REQUEST" "$BATCH_CONTRIBUTOR" "$BATCH_CONTRIBUTOR_EMAIL" \
                "$deduped_file_refs" "$BATCH_VERIFIES")

            if [[ -n "$BATCH_ASSIGNED_TO" ]]; then
                add_email_to_file "$BATCH_ASSIGNED_TO"
            fi

            task_id="t${claimed_id}"

            local humanized_name
            humanized_name=$(echo "$task_name" | tr '_' ' ')
            task_git add "$filepath"
            task_git add "$LABELS_FILE" 2>/dev/null || true
            if [[ "$BATCH_SILENT" == true ]]; then
                task_git commit --quiet -m "ait: Add task ${task_id}: ${humanized_name}" >&2
            else
                task_git commit -m "ait: Add task ${task_id}: ${humanized_name}"
            fi

            run_auto_merge_if_needed "$claimed_id" "$filepath"
        fi
    else
        # Default: create as draft in aitasks/new/ (no network needed)
        local deduped_file_refs
        deduped_file_refs=$(dedup_file_refs BATCH_FILE_REFS)
        filepath=$(create_draft_file "$task_name" "$BATCH_PRIORITY" "$BATCH_EFFORT" \
            "$BATCH_DEPS" "$BATCH_DESC" "$BATCH_TYPE" "$BATCH_STATUS" "$BATCH_LABELS" \
            "$BATCH_ASSIGNED_TO" "$BATCH_ISSUE" "$BATCH_PARENT" \
            "$BATCH_PULL_REQUEST" "$BATCH_CONTRIBUTOR" "$BATCH_CONTRIBUTOR_EMAIL" \
            "$deduped_file_refs" "$BATCH_VERIFIES")
    fi

    # Output
    if [[ "$BATCH_SILENT" == true ]]; then
        echo "$filepath"
    else
        echo "Created: $filepath"
    fi
}

# --- Main ---

main() {
    parse_args "$@"

    # Handle batch mode
    if [[ "$BATCH_MODE" == true ]]; then
        run_batch_mode
        return
    fi

    info "=== AI Task Creator ==="
    echo ""

    # Check terminal capabilities (warn on incapable terminals)
    ait_warn_if_incapable_terminal

    # Check dependencies
    command -v fzf &>/dev/null || die "fzf is required but not installed"

    # Ensure task directory and metadata directory exist
    mkdir -p "$TASK_DIR"
    mkdir -p "$DRAFT_DIR"
    mkdir -p "$(dirname "$LABELS_FILE")"

    # Step 0: Check for existing drafts
    local draft_list
    draft_list=$(list_drafts 2>/dev/null || true)

    if [[ -n "$draft_list" ]]; then
        info "Found draft task(s) in $DRAFT_DIR/:"
        echo "$draft_list" | while IFS= read -r line; do
            echo "  $line"
        done
        echo ""

        local draft_action
        local draft_options
        draft_options=$(echo -e "Create new task\n$(echo "$draft_list" | sed 's/ - .*//')" | \
            fzf --prompt="Select draft or create new: " --height=15 --no-info \
            --header="Manage drafts or create a new task")

        if [[ "$draft_action" == "Create new task" ]] || [[ -z "$draft_options" ]]; then
            : # Fall through to creation flow below
        elif [[ "$draft_options" == "Create new task" ]]; then
            : # Fall through to creation flow below
        else
            # User selected a draft
            local selected_draft="$draft_options"
            local draft_path="$DRAFT_DIR/$selected_draft"

            if [[ ! -f "$draft_path" ]]; then
                warn "Draft not found: $draft_path"
            else
                local manage_action
                manage_action=$(echo -e "Continue editing\nFinalize (assign real ID & commit)\nDelete draft\nBack to creation" | \
                    fzf --prompt="What to do with this draft? " --height=10 --no-info)

                case "$manage_action" in
                    "Continue editing")
                        ${EDITOR:-vim} "$draft_path"
                        success "Draft updated: $draft_path"
                        return
                        ;;
                    "Finalize"*)
                        finalize_draft "$draft_path"
                        return
                        ;;
                    "Delete draft")
                        rm -f "$draft_path"
                        success "Draft deleted: $selected_draft"
                        return
                        ;;
                    "Back to creation"|"")
                        : # Fall through to creation flow
                        ;;
                esac
            fi
        fi
    fi

    # Step 1a: Ask if this should be a child task
    info "Select parent task (or None for standalone task)..."
    local parent_num
    parent_num=$(select_parent_task)

    local is_child_task=false

    if [[ -n "$parent_num" ]]; then
        is_child_task=true
        info "Creating child task of parent t$parent_num (ID assigned on finalization)"
    else
        info "Creating standalone task (ID assigned on finalization)"
    fi
    echo ""

    # Step 2: Get metadata
    info "Select task metadata..."

    local priority
    priority=$(select_priority)
    [[ -z "$priority" ]] && die "Priority selection cancelled"

    local effort
    effort=$(select_effort)
    [[ -z "$effort" ]] && die "Effort selection cancelled"

    local issue_type
    issue_type=$(select_issue_type)
    [[ -z "$issue_type" ]] && issue_type="feature"

    local status
    status=$(select_status)
    [[ -z "$status" ]] && status="Ready"

    get_labels_interactive
    local labels="$SELECTED_LABELS"
    set_last_used_labels "$labels"

    local deps
    deps=$(select_dependencies "$parent_num")

    echo ""
    info "Priority: $priority, Effort: $effort, Issue: $issue_type, Status: $status"
    info "Dependencies: ${deps:-None}, Labels: ${labels:-None}"
    echo ""

    # Step 3: Get task name
    local name_result task_name predesc_text
    name_result=$(get_task_name)
    task_name=$(head -1 <<< "$name_result")
    predesc_text=$(sed '1d' <<< "$name_result")

    info "Draft filename: draft_*_${task_name}.md"
    echo ""

    # Step 4-5: Get task definition
    info "Enter task definition..."
    local raw_definition task_desc
    raw_definition=$(get_task_definition "$predesc_text")

    # Split the raw output at the __FILE_REFS_MARKER__ line: the portion
    # above is the description body; the portion below is one file ref per line.
    task_desc=$(sed '/^__FILE_REFS_MARKER__$/,$d' <<< "$raw_definition")
    local -a collected_refs=()
    while IFS= read -r _ref_line; do
        [[ -n "$_ref_line" ]] && collected_refs+=("$_ref_line")
    done < <(sed '1,/^__FILE_REFS_MARKER__$/d' <<< "$raw_definition")
    local deduped_file_refs
    deduped_file_refs=$(dedup_file_refs collected_refs)

    if [[ -z "$task_desc" ]]; then
        die "Task definition cannot be empty"
    fi

    # Step 6: Create draft file
    local filepath
    filepath=$(create_draft_file "$task_name" "$priority" "$effort" "$deps" \
        "$task_desc" "$issue_type" "$status" "$labels" "" "" \
        "$([[ "$is_child_task" == true ]] && echo "$parent_num" || echo "")" \
        "" "" "" "$deduped_file_refs")

    success "Draft created: $filepath"
    echo ""

    # Step 7: Summary
    echo ""
    echo "================================"
    success "Draft task created!"
    echo "================================"
    echo "  Filename:      $filepath"
    echo "  Priority:      $priority"
    echo "  Effort:        $effort"
    echo "  Issue Type:    $issue_type"
    echo "  Status:        $status"
    echo "  Dependencies:  ${deps:-None}"
    echo "  Labels:        ${labels:-None}"
    if [[ "$is_child_task" == true ]]; then
        echo "  Parent task:   t$parent_num"
    fi
    echo ""
    info "Note: This is a draft. Real task ID will be assigned on finalization."
    echo ""

    # Step 8: View/edit/finalize options
    while true; do
        local post_action
        post_action=$(echo -e "Finalize now (assign ID & commit)\nShow draft\nOpen in editor\nSave as draft (done)" | \
            fzf --prompt="What next? " --height=10 --no-info)

        case "$post_action" in
            "Finalize now"*)
                finalize_draft "$filepath"
                return
                ;;
            "Show draft")
                echo ""
                echo "--- Contents of $filepath ---"
                cat "$filepath"
                echo "--- End of file ---"
                echo ""
                ;;
            "Open in editor")
                ${EDITOR:-vim} "$filepath"
                ;;
            "Save as draft"*|"")
                info "Draft saved. Finalize later with: ait create (interactive) or --batch --finalize"
                return
                ;;
        esac
    done
}

main "$@"
