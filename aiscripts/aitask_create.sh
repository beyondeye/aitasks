#!/bin/bash

# aitask_create.sh - Interactive AI task creation with fzf
# Creates task files in aitasks/ directory with YAML front matter

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TASK_DIR="aitasks"
ARCHIVED_DIR="aitasks/archived"
ARCHIVE_FILE="aitasks/archived/old.tar.gz"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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
BATCH_COMMIT=false
BATCH_SILENT=false
BATCH_PARENT=""
BATCH_NO_SIBLING_DEP=false
BATCH_ASSIGNED_TO=""
BATCH_ISSUE=""

# --- Helper Functions ---

die() {
    echo -e "${RED}Error: $1${NC}" >&2
    exit 1
}

info() {
    echo -e "${BLUE}$1${NC}"
}

success() {
    echo -e "${GREEN}$1${NC}"
}

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
  --type, -t TYPE        Issue type: feature, bug (default: feature)
  --status, -s STATUS    Status: Ready, Editing, Implementing, Postponed (default: Ready)
  --assigned-to, -a EMAIL  Email of person assigned to task (optional)
  --issue URL            Issue tracker URL (e.g., GitHub issue URL)
  --labels, -l LABELS    Comma-separated labels
  --deps DEPS            Comma-separated dependency task numbers
  --parent, -P NUM       Create as child of specified parent task number
  --no-sibling-dep       Don't auto-add dependency on previous sibling (for child tasks)
  --commit               Automatically commit to git
  --silent               Output only the created filename (for scripting)
  --help, -h             Show this help

Examples:
  # Interactive mode
  ./aitask_create.sh

  # Batch mode with minimal options
  ./aitask_create.sh --batch --name "fix_login_bug" --desc "Fix the login issue"

  # Batch mode with all options
  ./aitask_create.sh --batch --name "add_feature" --desc "Add new feature" \
      --priority high --effort medium --type feature --labels "ui,urgent" --commit

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
            --parent|-P) BATCH_PARENT="$2"; shift 2 ;;
            --no-sibling-dep) BATCH_NO_SIBLING_DEP=true; shift ;;
            --assigned-to|-a) BATCH_ASSIGNED_TO="$2"; shift 2 ;;
            --issue) BATCH_ISSUE="$2"; shift 2 ;;
            --commit) BATCH_COMMIT=true; shift ;;
            --silent) BATCH_SILENT=true; shift ;;
            --help|-h) show_help; exit 0 ;;
            *) die "Unknown option: $1" ;;
        esac
    done
}

# --- Step 1: Determine Next Task Number ---

get_next_task_number() {
    local max_num=0
    local num

    # Get task numbers from active tasks
    if ls "$TASK_DIR"/t*_*.md &>/dev/null; then
        for f in "$TASK_DIR"/t*_*.md; do
            num=$(basename "$f" | grep -oE '^t[0-9]+' | sed 's/t//')
            [[ "$num" -gt "$max_num" ]] && max_num="$num"
        done
    fi

    # Get task numbers from archived tasks
    if ls "$ARCHIVED_DIR"/t*_*.md &>/dev/null; then
        for f in "$ARCHIVED_DIR"/t*_*.md; do
            num=$(basename "$f" | grep -oE '^t[0-9]+' | sed 's/t//')
            [[ "$num" -gt "$max_num" ]] && max_num="$num"
        done
    fi

    # Get task numbers from compressed archive
    if [[ -f "$ARCHIVE_FILE" ]]; then
        while IFS= read -r line; do
            num=$(echo "$line" | grep -oE 't[0-9]+' | head -1 | sed 's/t//')
            [[ -n "$num" && "$num" -gt "$max_num" ]] && max_num="$num"
        done < <(tar -tzf "$ARCHIVE_FILE" 2>/dev/null | grep -E 't[0-9]+')
    fi

    echo $((max_num + 1))
}

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
    if [[ -f "$ARCHIVE_FILE" ]]; then
        while IFS= read -r line; do
            num=$(echo "$line" | grep -oE "t${parent_num}_[0-9]+" | head -1 | sed "s/t${parent_num}_//")
            [[ -n "$num" && "$num" -gt "$max_child" ]] && max_child="$num"
        done < <(tar -tzf "$ARCHIVE_FILE" 2>/dev/null | grep -E "t${parent_num}/t${parent_num}_[0-9]+")
    fi

    echo $((max_child + 1))
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
            current_children=$(echo "$line" | sed 's/children_to_implement://' | tr -d '[]' | tr -d ' ')
            break
        fi
    done < "$parent_file"

    # Add new child to list
    if [[ -z "$current_children" ]]; then
        current_children="$child_id"
    else
        current_children="$current_children,$child_id"
    fi

    # Update the parent file using aitask_update.sh if available, otherwise inline update
    if [[ -x "$SCRIPT_DIR/aitask_update.sh" ]]; then
        "$SCRIPT_DIR/aitask_update.sh" --batch "$parent_num" --add-child "$child_id" 2>/dev/null || {
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
        content=$(echo "$content" | sed "/^labels:/a children_to_implement: $children_yaml")
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
    labels_yaml=$(format_labels_yaml "$labels")

    # Create the file with YAML front matter (same format as regular tasks)
    {
        echo "---"
        echo "priority: $priority"
        echo "effort: $effort"
        echo "depends: $deps_yaml"
        echo "issue_type: $issue_type"
        echo "status: $status"
        echo "labels: $labels_yaml"
        # Only write issue if present
        if [[ -n "$issue" ]]; then
            echo "issue: $issue"
        fi
        echo "created_at: $timestamp"
        echo "updated_at: $timestamp"
        echo "---"
        echo ""
        echo "$description"
    } > "$filepath"

    echo "$filepath"
}

# --- Step 2: Metadata Collection ---

select_priority() {
    echo -e "high\nmedium\nlow" | fzf --prompt="Priority: " --height=10 --no-info --header="Select task priority"
}

select_effort() {
    echo -e "low\nmedium\nhigh" | fzf --prompt="Effort: " --height=10 --no-info --header="Select estimated effort"
}

select_issue_type() {
    echo -e "feature\nbug" | fzf --prompt="Issue type: " --height=8 --no-info --header="Select issue type"
}

select_status() {
    echo -e "Ready\nEditing\nImplementing\nPostponed" | fzf --prompt="Status: " --height=12 --no-info --header="Select task status"
}

LABELS_FILE="aitasks/metadata/labels.txt"
EMAILS_FILE="aitasks/metadata/emails.txt"

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

# Get labels interactively - sets SELECTED_LABELS variable
# This function works directly with the terminal, not via command substitution
get_labels_interactive() {
    # Disable exit-on-error for this function (fzf and file operations can return non-zero)
    set +e

    SELECTED_LABELS=""
    local selected_labels=()

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

        # Select label using fzf
        local selected
        selected=$(printf "%s" "$options" | fzf --prompt="Select label: " --height=15 --no-info --header="Select existing label or add new")

        if [[ -n "$selected" ]]; then
            local label=""

            if [[ "$selected" == ">> Done adding labels" ]]; then
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
    local name
    read -erp "Task name (short, will be sanitized): " name

    local sanitized
    sanitized=$(sanitize_name "$name")

    # Default to unnamed_task if empty
    [[ -z "$sanitized" ]] && sanitized="unnamed_task"

    echo "$sanitized"
}

# --- Step 4-5: Task Definition Loop ---

get_task_definition() {
    local task_desc=""

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
                    for ref in "${current_round_refs[@]}"; do
                        [[ "$ref" != "$remove_file" ]] && new_refs+=("$ref")
                    done
                    current_round_refs=("${new_refs[@]}")
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

    echo "$task_desc"
}

# --- Step 6: Create Task File ---

get_timestamp() {
    date '+%Y-%m-%d %H:%M'
}

format_yaml_list() {
    # Converts "1,3,5" to "[1, 3, 5]" for YAML
    local input="$1"
    if [[ -z "$input" ]]; then
        echo "[]"
    else
        echo "[$(echo "$input" | sed 's/,/, /g')]"
    fi
}

format_labels_yaml() {
    # Converts "ui,backend" to "[ui, backend]" for YAML
    local input="$1"
    if [[ -z "$input" ]]; then
        echo "[]"
    else
        echo "[$(echo "$input" | sed 's/,/, /g')]"
    fi
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

    local filename="t${task_num}_${task_name}.md"
    local filepath="$TASK_DIR/$filename"

    local timestamp
    timestamp=$(get_timestamp)

    local deps_yaml
    deps_yaml=$(format_yaml_list "$deps")

    local labels_yaml
    labels_yaml=$(format_labels_yaml "$labels")

    # Create the file with YAML front matter
    {
        echo "---"
        echo "priority: $priority"
        echo "effort: $effort"
        echo "depends: $deps_yaml"
        echo "issue_type: $issue_type"
        echo "status: $status"
        echo "labels: $labels_yaml"
        # Only write assigned_to if present
        if [[ -n "$assigned_to" ]]; then
            echo "assigned_to: $assigned_to"
        fi
        # Only write issue if present
        if [[ -n "$issue" ]]; then
            echo "issue: $issue"
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

        git add "$filepath"
        git commit -m "Add task t${task_num}: ${humanized_name}"

        local commit_hash
        commit_hash=$(git rev-parse --short HEAD)
        echo "$commit_hash"
    else
        echo ""
    fi
}

# --- Batch Mode ---

run_batch_mode() {
    # Ensure task directory exists
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

    case "$BATCH_TYPE" in
        feature|bug) ;;
        *) die "Invalid type: $BATCH_TYPE (must be feature or bug)" ;;
    esac

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

    # Check if creating a child task
    if [[ -n "$BATCH_PARENT" ]]; then
        # Validate parent exists
        local parent_file
        parent_file=$(get_parent_task_file "$BATCH_PARENT")
        [[ -z "$parent_file" || ! -f "$parent_file" ]] && die "Parent task t$BATCH_PARENT not found"

        # Get next child number
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

        # Create child task file
        filepath=$(create_child_task_file "$BATCH_PARENT" "$child_num" "$task_name" \
            "$BATCH_PRIORITY" "$BATCH_EFFORT" "$BATCH_DEPS" "$BATCH_DESC" \
            "$BATCH_TYPE" "$BATCH_STATUS" "$BATCH_LABELS" "$BATCH_ISSUE")

        task_id="t${BATCH_PARENT}_${child_num}"

        # Update parent's children_to_implement
        update_parent_children_to_implement "$BATCH_PARENT" "$task_id"

        # Git commit if requested
        if [[ "$BATCH_COMMIT" == true ]]; then
            local humanized_name
            humanized_name=$(echo "$task_name" | tr '_' ' ')
            git add "$filepath"
            # Also add parent if it was modified
            git add "$parent_file" 2>/dev/null || true
            git commit -m "Add child task ${task_id}: ${humanized_name}"
        fi
    else
        # Create regular (parent-level) task
        local next_num
        next_num=$(get_next_task_number)

        filepath=$(create_task_file "$next_num" "$task_name" "$BATCH_PRIORITY" "$BATCH_EFFORT" \
            "$BATCH_DEPS" "$BATCH_DESC" "$BATCH_TYPE" "$BATCH_STATUS" "$BATCH_LABELS" "$BATCH_ASSIGNED_TO" "$BATCH_ISSUE")

        # Store email if provided
        if [[ -n "$BATCH_ASSIGNED_TO" ]]; then
            add_email_to_file "$BATCH_ASSIGNED_TO"
        fi

        task_id="t${next_num}"

        # Git commit if requested
        if [[ "$BATCH_COMMIT" == true ]]; then
            local humanized_name
            humanized_name=$(echo "$task_name" | tr '_' ' ')
            git add "$filepath"
            git commit -m "Add task ${task_id}: ${humanized_name}"
        fi
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

    # Check dependencies
    command -v fzf &>/dev/null || die "fzf is required but not installed"

    # Ensure task directory and metadata directory exist
    mkdir -p "$TASK_DIR"
    mkdir -p "$(dirname "$LABELS_FILE")"

    # Step 1a: Ask if this should be a child task
    info "Select parent task (or None for standalone task)..."
    local parent_num
    parent_num=$(select_parent_task)

    local is_child_task=false
    local next_num=""
    local child_num=""

    if [[ -n "$parent_num" ]]; then
        is_child_task=true
        child_num=$(get_next_child_number "$parent_num")
        info "Creating child task t${parent_num}_${child_num} of parent t$parent_num"
    else
        # Step 1b: Get next task number for standalone task
        next_num=$(get_next_task_number)
        info "Next task number: t$next_num"
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

    local deps
    deps=$(select_dependencies "$parent_num")

    # For child tasks, ask about sibling dependency
    if [[ "$is_child_task" == true && "$child_num" -gt 1 ]]; then
        local prev_sibling="t${parent_num}_$((child_num - 1))"
        local add_sibling_dep
        add_sibling_dep=$(echo -e "Yes - depend on $prev_sibling\nNo - no sibling dependency" | \
            fzf --prompt="Add sibling dependency? " --height=8 --no-info \
            --header="Should this task depend on the previous sibling?")

        if [[ "$add_sibling_dep" == "Yes"* ]]; then
            if [[ -n "$deps" ]]; then
                deps="$prev_sibling,$deps"
            else
                deps="$prev_sibling"
            fi
            info "Added dependency on sibling: $prev_sibling"
        fi
    fi

    echo ""
    info "Priority: $priority, Effort: $effort, Issue: $issue_type, Status: $status"
    info "Dependencies: ${deps:-None}, Labels: ${labels:-None}"
    echo ""

    # Step 3: Get task name
    local task_name
    task_name=$(get_task_name)

    if [[ "$is_child_task" == true ]]; then
        info "Task filename: t${parent_num}_${child_num}_${task_name}.md"
    else
        info "Task filename: t${next_num}_${task_name}.md"
    fi
    echo ""

    # Step 4-5: Get task definition
    info "Enter task definition..."
    local task_desc
    task_desc=$(get_task_definition)

    if [[ -z "$task_desc" ]]; then
        die "Task definition cannot be empty"
    fi

    # Step 6: Create task file
    local filepath
    local task_id

    if [[ "$is_child_task" == true ]]; then
        filepath=$(create_child_task_file "$parent_num" "$child_num" "$task_name" \
            "$priority" "$effort" "$deps" "$task_desc" "$issue_type" "$status" "$labels")
        task_id="t${parent_num}_${child_num}"

        # Update parent's children_to_implement
        update_parent_children_to_implement "$parent_num" "$task_id"
    else
        filepath=$(create_task_file "$next_num" "$task_name" "$priority" "$effort" \
            "$deps" "$task_desc" "$issue_type" "$status" "$labels")
        task_id="t${next_num}"
    fi

    success "Created: $filepath"
    echo ""

    # Step 7: Summary
    echo ""
    echo "================================"
    success "Task created successfully!"
    echo "================================"
    echo "  Task ID:       $task_id"
    if [[ "$is_child_task" == true ]]; then
        echo "  Parent task:   t$parent_num"
    fi
    echo "  Filename:      $filepath"
    echo "  Priority:      $priority"
    echo "  Effort:        $effort"
    echo "  Issue Type:    $issue_type"
    echo "  Status:        $status"
    echo "  Dependencies:  ${deps:-None}"
    echo "  Labels:        ${labels:-None}"
    echo ""

    # Step 8: View/edit options
    while true; do
        local post_action
        post_action=$(echo -e "Show created task\nOpen in editor\nDone" | fzf --prompt="What next? " --height=10 --no-info)

        case "$post_action" in
            "Show created task")
                echo ""
                echo "--- Contents of $filepath ---"
                cat "$filepath"
                echo "--- End of file ---"
                echo ""
                ;;
            "Open in editor")
                ${EDITOR:-vim} "$filepath"
                break
                ;;
            "Done"|"")
                break
                ;;
        esac
    done

    # Step 9: Git commit
    read -rp "Commit to git? [Y/n] " commit_choice

    if [[ "$commit_choice" != "n" && "$commit_choice" != "N" ]]; then
        local humanized_name
        humanized_name=$(echo "$task_name" | tr '_' ' ')

        git add "$filepath"

        if [[ "$is_child_task" == true ]]; then
            # Also add parent file if it was modified
            local parent_file
            parent_file=$(get_parent_task_file "$parent_num")
            [[ -n "$parent_file" ]] && git add "$parent_file" 2>/dev/null || true
            git commit -m "Add child task ${task_id}: ${humanized_name}"
        else
            git commit -m "Add task ${task_id}: ${humanized_name}"
        fi

        local commit_hash
        commit_hash=$(git rev-parse --short HEAD)
        success "Committed: $commit_hash"
    fi
}

main "$@"
