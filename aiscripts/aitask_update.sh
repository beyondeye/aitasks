#!/usr/bin/env bash

# aitask_update.sh - Update existing AI tasks
# Supports interactive mode (fzf) and batch mode (CLI parameters)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
source "$SCRIPT_DIR/lib/task_utils.sh"

TASK_DIR="aitasks"
LABELS_FILE="aitasks/metadata/labels.txt"
TASK_TYPES_FILE="aitasks/metadata/task_types.txt"

# Batch mode variables
BATCH_MODE=false
BATCH_TASK_NUM=""
BATCH_PRIORITY=""
BATCH_EFFORT=""
BATCH_STATUS=""
BATCH_TYPE=""
BATCH_DEPS=""
BATCH_DEPS_SET=false
BATCH_LABELS=""
BATCH_LABELS_SET=false
BATCH_ADD_LABELS=()
BATCH_REMOVE_LABELS=()
BATCH_DESC=""
BATCH_DESC_FILE=""
BATCH_NAME=""
BATCH_SILENT=false
BATCH_ADD_CHILD=""
BATCH_REMOVE_CHILD=""
BATCH_CHILDREN=""
BATCH_CHILDREN_SET=false
BATCH_ASSIGNED_TO=""
BATCH_ASSIGNED_TO_SET=false
BATCH_BOARDCOL=""
BATCH_BOARDCOL_SET=false
BATCH_BOARDIDX=""
BATCH_BOARDIDX_SET=false
BATCH_ISSUE=""
BATCH_ISSUE_SET=false
BATCH_FOLDED_TASKS=""
BATCH_FOLDED_TASKS_SET=false
BATCH_FOLDED_INTO=""
BATCH_FOLDED_INTO_SET=false
BATCH_COMMIT=false

# Current values (parsed from file)
CURRENT_PRIORITY=""
CURRENT_EFFORT=""
CURRENT_DEPS=""
CURRENT_TYPE=""
CURRENT_STATUS=""
CURRENT_LABELS=""
CURRENT_CREATED_AT=""
CURRENT_DESCRIPTION=""
CURRENT_CHILDREN_TO_IMPLEMENT=""
CURRENT_ASSIGNED_TO=""
CURRENT_BOARDCOL=""
CURRENT_BOARDIDX=""
CURRENT_ISSUE=""
CURRENT_FOLDED_TASKS=""
CURRENT_FOLDED_INTO=""

# --- Helper Functions ---

show_help() {
    cat << 'EOF'
Usage: aitask_update.sh [OPTIONS] [TASK_NUMBER]

Update an existing AI task file.

Interactive mode (default):
  Run without --batch for interactive task selection and editing with fzf.
  If TASK_NUMBER is provided, skip task selection and edit that task directly.

Batch mode (for automation):
  --batch                Enable batch mode (non-interactive)
  TASK_NUMBER            Task number to update (required in batch mode)

Metadata options (batch mode):
  --priority, -p LEVEL   Priority: high, medium, low
  --effort, -e LEVEL     Effort: low, medium, high
  --status, -s STATUS    Status: Ready, Editing, Implementing, Postponed, Done, Folded
  --type TYPE            Issue type (see aitasks/metadata/task_types.txt)
  --deps DEPS            Dependencies (comma-separated task numbers, replaces all)

Label options (batch mode):
  --labels, -l LABELS    Labels (comma-separated, replaces all existing labels)
  --add-label LABEL      Add a label (can be repeated)
  --remove-label LABEL   Remove a label (can be repeated)

Description options (batch mode):
  --description, -d DESC New description text (replaces existing)
  --desc-file FILE       Read description from file (use - for stdin)

Board options (batch mode):
  --boardcol COL           Board column ID (e.g., now, next, backlog)
  --boardidx IDX           Board sort index (integer)

Issue tracking options (batch mode):
  --issue URL              Issue tracker URL (e.g., GitHub issue URL; use "" to clear)

Assignment options (batch mode):
  --assigned-to, -a EMAIL  Email of assigned person (use "" to clear)

Folded task options (batch mode):
  --folded-tasks TASKS   Folded task IDs (comma-separated, e.g., "106,129_5"; use "" to clear)
  --folded-into NUM      Task number this task was folded into (use "" to clear)

Child task options (batch mode):
  --add-child CHILD_ID   Add child to children_to_implement list
  --remove-child CHILD_ID Remove child from children_to_implement list
  --children CHILDREN    Set children_to_implement (comma-separated, replaces all)

Other options:
  --name, -n NAME        Rename task (changes filename, sanitizes input)
  --commit               Automatically commit changes to git
  --silent               Output only filename on success (batch mode)
  --help, -h             Show this help

Examples:
  # Interactive mode - select task with fzf
  ./aitask_update.sh

  # Interactive mode - edit specific task
  ./aitask_update.sh 25

  # Batch mode - update priority
  ./aitask_update.sh --batch 25 --priority high

  # Batch mode - update multiple fields
  ./aitask_update.sh --batch 25 -p low -e high -s Editing

  # Batch mode - replace all labels
  ./aitask_update.sh --batch 25 --labels "ui,backend"

  # Batch mode - add/remove individual labels
  ./aitask_update.sh --batch 25 --add-label "urgent" --remove-label "low-priority"

  # Batch mode - update description
  ./aitask_update.sh --batch 25 -d "New description text"

  # Batch mode - rename task
  ./aitask_update.sh --batch 25 --name "new_task_name"

  # Batch mode - add child to parent's children_to_implement
  ./aitask_update.sh --batch 10 --add-child t10_1

  # Batch mode - remove child (when child is completed)
  ./aitask_update.sh --batch 10 --remove-child t10_1

  # Batch mode - update child task (use parent_child format)
  ./aitask_update.sh --batch 10_1 --status Done
EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --batch) BATCH_MODE=true; shift ;;
            --priority|-p) BATCH_PRIORITY="$2"; shift 2 ;;
            --effort|-e) BATCH_EFFORT="$2"; shift 2 ;;
            --status|-s) BATCH_STATUS="$2"; shift 2 ;;
            --type) BATCH_TYPE="$2"; shift 2 ;;
            --deps) BATCH_DEPS="$2"; BATCH_DEPS_SET=true; shift 2 ;;
            --labels|-l) BATCH_LABELS="$2"; BATCH_LABELS_SET=true; shift 2 ;;
            --add-label) BATCH_ADD_LABELS+=("$2"); shift 2 ;;
            --remove-label) BATCH_REMOVE_LABELS+=("$2"); shift 2 ;;
            --description|-d) BATCH_DESC="$2"; shift 2 ;;
            --desc-file) BATCH_DESC_FILE="$2"; shift 2 ;;
            --name|-n) BATCH_NAME="$2"; shift 2 ;;
            --add-child) BATCH_ADD_CHILD="$2"; shift 2 ;;
            --remove-child) BATCH_REMOVE_CHILD="$2"; shift 2 ;;
            --children) BATCH_CHILDREN="$2"; BATCH_CHILDREN_SET=true; shift 2 ;;
            --assigned-to|-a) BATCH_ASSIGNED_TO="$2"; BATCH_ASSIGNED_TO_SET=true; shift 2 ;;
            --boardcol) BATCH_BOARDCOL="$2"; BATCH_BOARDCOL_SET=true; shift 2 ;;
            --boardidx) BATCH_BOARDIDX="$2"; BATCH_BOARDIDX_SET=true; shift 2 ;;
            --issue) BATCH_ISSUE="$2"; BATCH_ISSUE_SET=true; shift 2 ;;
            --folded-tasks) BATCH_FOLDED_TASKS="$2"; BATCH_FOLDED_TASKS_SET=true; shift 2 ;;
            --folded-into) BATCH_FOLDED_INTO="$2"; BATCH_FOLDED_INTO_SET=true; shift 2 ;;
            --commit) BATCH_COMMIT=true; shift ;;
            --silent) BATCH_SILENT=true; shift ;;
            --help|-h) show_help; exit 0 ;;
            -*)
                die "Unknown option: $1"
                ;;
            *)
                # Positional argument - task number or child task ID
                # Support formats: 25 (parent), 25_1 (child), t25_1 (child with prefix)
                if [[ "$1" =~ ^t?[0-9]+(_[0-9]+)?$ ]]; then
                    BATCH_TASK_NUM="${1#t}"  # Remove leading 't' if present
                    shift
                else
                    die "Invalid task number: $1 (use format: 25, 25_1, or t25_1)"
                fi
                ;;
        esac
    done
}

# --- Task Resolution ---

resolve_task_file() {
    local task_id="$1"
    local files

    # Check if it's a child task ID (e.g., "10_1" or "t10_1")
    if [[ "$task_id" =~ ^([0-9]+)_([0-9]+)$ ]]; then
        local parent_num="${BASH_REMATCH[1]}"
        local child_num="${BASH_REMATCH[2]}"
        local child_dir="$TASK_DIR/t${parent_num}"

        files=$(ls "$child_dir"/t${parent_num}_${child_num}_*.md 2>/dev/null || true)

        if [[ -z "$files" ]]; then
            die "No child task file found for t${parent_num}_${child_num}"
        fi
    else
        # Regular task
        files=$(ls "$TASK_DIR"/t${task_id}_*.md 2>/dev/null || true)

        if [[ -z "$files" ]]; then
            die "No task file found for task number $task_id"
        fi
    fi

    local count
    count=$(echo "$files" | wc -l)

    if [[ "$count" -gt 1 ]]; then
        die "Multiple task files found for task $task_id. Run 'ait setup' to initialize the atomic task ID counter and prevent future duplicates."
    fi

    echo "$files"
}

# --- YAML Parsing ---

parse_yaml_frontmatter() {
    local file_path="$1"

    # Reset current values
    CURRENT_PRIORITY="medium"
    CURRENT_EFFORT="medium"
    CURRENT_DEPS=""
    CURRENT_TYPE="feature"
    CURRENT_STATUS="Ready"
    CURRENT_LABELS=""
    CURRENT_CREATED_AT=""
    CURRENT_DESCRIPTION=""
    CURRENT_CHILDREN_TO_IMPLEMENT=""
    CURRENT_ASSIGNED_TO=""
    CURRENT_BOARDCOL=""
    CURRENT_BOARDIDX=""
    CURRENT_ISSUE=""
    CURRENT_FOLDED_TASKS=""
    CURRENT_FOLDED_INTO=""

    # Read entire file content
    local file_content
    file_content=$(cat "$file_path")

    local first_line
    first_line=$(echo "$file_content" | head -n 1)

    # Check if it's YAML front matter
    if [[ "$first_line" != "---" ]]; then
        # No YAML front matter, entire file is description
        CURRENT_DESCRIPTION="$file_content"
        return
    fi

    # Find the end of YAML front matter (second ---)
    local yaml_end_line
    yaml_end_line=$(echo "$file_content" | tail -n +2 | grep -n "^---$" | head -1 | cut -d: -f1)

    if [[ -z "$yaml_end_line" ]]; then
        # No closing ---, treat as description
        CURRENT_DESCRIPTION="$file_content"
        return
    fi

    # Extract YAML content (between first and second ---)
    local yaml_content
    yaml_content=$(echo "$file_content" | head -n $((yaml_end_line + 1)) | tail -n +2 | head -n $((yaml_end_line - 1)))

    # Parse YAML key-value pairs
    while IFS= read -r line; do
        if [[ "$line" =~ ^([a-z_]+):(.*)$ ]]; then
            local key="${BASH_REMATCH[1]}"
            local value="${BASH_REMATCH[2]}"
            # Trim leading/trailing whitespace
            value=$(echo "$value" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

            case "$key" in
                priority) CURRENT_PRIORITY="$value" ;;
                effort) CURRENT_EFFORT="$value" ;;
                depends)
                    # Parse YAML list: [1, 3, 5] -> 1,3,5
                    CURRENT_DEPS=$(echo "$value" | tr -d '[]' | tr -d ' ')
                    CURRENT_DEPS=$(normalize_task_ids "$CURRENT_DEPS")
                    ;;
                issue_type) CURRENT_TYPE="$value" ;;
                status) CURRENT_STATUS="$value" ;;
                labels)
                    # Parse YAML list: [ui, backend] -> ui,backend
                    CURRENT_LABELS=$(echo "$value" | tr -d '[]' | tr -d ' ')
                    ;;
                children_to_implement)
                    # Parse YAML list: [t1_1, t1_2] -> t1_1,t1_2
                    CURRENT_CHILDREN_TO_IMPLEMENT=$(echo "$value" | tr -d '[]' | tr -d ' ')
                    CURRENT_CHILDREN_TO_IMPLEMENT=$(normalize_task_ids "$CURRENT_CHILDREN_TO_IMPLEMENT")
                    ;;
                created_at) CURRENT_CREATED_AT="$value" ;;
                assigned_to) CURRENT_ASSIGNED_TO="$value" ;;
                boardcol) CURRENT_BOARDCOL="$value" ;;
                boardidx) CURRENT_BOARDIDX="$value" ;;
                issue) CURRENT_ISSUE="$value" ;;
                folded_tasks)
                    CURRENT_FOLDED_TASKS=$(echo "$value" | tr -d '[]' | tr -d ' ')
                    ;;
                folded_into) CURRENT_FOLDED_INTO="$value" ;;
            esac
        fi
    done <<< "$yaml_content"

    # Extract description (everything after YAML block)
    local total_lines
    total_lines=$(echo "$file_content" | wc -l)
    local desc_start=$((yaml_end_line + 2))

    if [[ $desc_start -le $total_lines ]]; then
        # Get content after YAML and remove leading blank lines
        CURRENT_DESCRIPTION=$(echo "$file_content" | tail -n +$desc_start | sed -n '/./,$p')
    fi
}

# --- Name Sanitization ---

sanitize_name() {
    local name="$1"
    # Convert to lowercase, replace spaces with underscores, remove special chars
    echo "$name" | tr '[:upper:]' '[:lower:]' | tr ' ' '_' | tr -cd 'a-z0-9_' | sed 's/__*/_/g' | sed 's/^_//;s/_$//' | cut -c1-60
}

# --- YAML Formatting ---

normalize_task_ids() {
    # Normalize child task IDs: ensure entries with underscore have 't' prefix
    # e.g. "85_2,t85_3,16" -> "t85_2,t85_3,16"
    local input="$1"
    [[ -z "$input" ]] && return
    local result=""
    IFS=',' read -ra ids <<< "$input"
    for id in "${ids[@]}"; do
        if [[ "$id" =~ ^[0-9]+_[0-9]+$ ]]; then
            id="t${id}"
        fi
        [[ -n "$result" ]] && result="${result},"
        result="${result}${id}"
    done
    echo "$result"
}

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

# --- File Writing ---

write_task_file() {
    local file_path="$1"
    local priority="$2"
    local effort="$3"
    local deps="$4"
    local issue_type="$5"
    local status="$6"
    local labels="$7"
    local created_at="$8"
    local description="$9"
    local children_to_implement="${10:-}"
    local assigned_to="${11:-}"
    local boardcol="${12:-}"
    local boardidx="${13:-}"
    local issue="${14:-}"
    local folded_tasks="${15:-}"
    local folded_into="${16:-}"

    local updated_at
    updated_at=$(get_timestamp)

    local deps_yaml
    deps_yaml=$(format_yaml_list "$deps")

    local labels_yaml
    labels_yaml=$(format_yaml_list "$labels")

    # Write the file with YAML front matter
    {
        echo "---"
        echo "priority: $priority"
        echo "effort: $effort"
        echo "depends: $deps_yaml"
        echo "issue_type: $issue_type"
        echo "status: $status"
        echo "labels: $labels_yaml"
        # Only write children_to_implement if present
        if [[ -n "$children_to_implement" ]]; then
            local children_yaml
            children_yaml=$(format_yaml_list "$children_to_implement")
            echo "children_to_implement: $children_yaml"
        fi
        # Only write folded_tasks if present
        if [[ -n "$folded_tasks" ]]; then
            local folded_yaml
            folded_yaml=$(format_yaml_list "$folded_tasks")
            echo "folded_tasks: $folded_yaml"
        fi
        # Only write folded_into if present
        if [[ -n "$folded_into" ]]; then
            echo "folded_into: $folded_into"
        fi
        # Only write assigned_to if present
        if [[ -n "$assigned_to" ]]; then
            echo "assigned_to: $assigned_to"
        fi
        # Only write issue if present
        if [[ -n "$issue" ]]; then
            echo "issue: $issue"
        fi
        echo "created_at: $created_at"
        echo "updated_at: $updated_at"
        # Board fields always written last
        if [[ -n "$boardcol" ]]; then
            echo "boardcol: $boardcol"
        fi
        if [[ -n "$boardidx" ]]; then
            echo "boardidx: $boardidx"
        fi
        echo "---"
        echo ""
        echo "$description"
    } > "$file_path"
}

# --- Label Management ---

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
    if ! grep -qFx "$label" "$LABELS_FILE" 2>/dev/null; then
        echo "$label" >> "$LABELS_FILE"
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

process_label_operations() {
    local current_labels="$1"
    local new_labels="$2"
    local -n add_labels_ref=$3
    local -n remove_labels_ref=$4
    local labels_flag_set="${5:-false}"

    # If --labels was specified, use it as base (replaces all)
    # This works even when new_labels is empty (to clear all labels)
    if [[ "$labels_flag_set" == true ]]; then
        current_labels="$new_labels"
    fi

    # Convert to array for manipulation
    local -a labels_array=()
    if [[ -n "$current_labels" ]]; then
        IFS=',' read -ra labels_array <<< "$current_labels"
    fi

    # Add labels
    for label in "${add_labels_ref[@]}"; do
        local found=false
        for existing in "${labels_array[@]}"; do
            if [[ "$existing" == "$label" ]]; then
                found=true
                break
            fi
        done
        if [[ "$found" == false ]]; then
            labels_array+=("$label")
            # Also add to labels file for future use
            add_label_to_file "$label"
        fi
    done

    # Remove labels
    local -a new_array=()
    for existing in "${labels_array[@]}"; do
        local should_remove=false
        for label in "${remove_labels_ref[@]}"; do
            if [[ "$existing" == "$label" ]]; then
                should_remove=true
                break
            fi
        done
        if [[ "$should_remove" == false ]]; then
            new_array+=("$existing")
        fi
    done

    # Convert back to comma-separated string
    local IFS=','
    echo "${new_array[*]}"
}

# --- Children Management ---

process_children_operations() {
    local current_children="$1"
    local new_children="$2"
    local add_child="$3"
    local remove_child="$4"
    local children_flag_set="${5:-false}"

    # If --children was specified, use it as base (replaces all)
    if [[ "$children_flag_set" == true ]]; then
        current_children="$new_children"
    fi

    # Convert to array
    local -a children_array=()
    if [[ -n "$current_children" ]]; then
        IFS=',' read -ra children_array <<< "$current_children"
    fi

    # Add child if specified
    if [[ -n "$add_child" ]]; then
        local found=false
        for existing in "${children_array[@]}"; do
            if [[ "$existing" == "$add_child" ]]; then
                found=true
                break
            fi
        done
        if [[ "$found" == false ]]; then
            children_array+=("$add_child")
        fi
    fi

    # Remove child if specified
    if [[ -n "$remove_child" ]]; then
        local -a new_array=()
        for existing in "${children_array[@]}"; do
            if [[ "$existing" != "$remove_child" ]]; then
                new_array+=("$existing")
            fi
        done
        children_array=("${new_array[@]}")
    fi

    local IFS=','
    echo "${children_array[*]}"
}

# Handle child task completion - update parent's children_to_implement
handle_child_task_completion() {
    local task_id="$1"
    local new_status="$2"

    # Check if this is a child task
    if [[ ! "$task_id" =~ ^([0-9]+)_([0-9]+)$ ]]; then
        return  # Not a child task
    fi

    if [[ "$new_status" != "Done" ]]; then
        return  # Not completing
    fi

    local parent_num="${BASH_REMATCH[1]}"
    local child_id="t${task_id}"

    # Find parent file
    local parent_file
    parent_file=$(ls "$TASK_DIR"/t${parent_num}_*.md 2>/dev/null | head -1 || true)

    if [[ -z "$parent_file" || ! -f "$parent_file" ]]; then
        warn "Parent task t$parent_num not found - cannot update children_to_implement"
        return
    fi

    # Parse parent file
    local saved_priority="$CURRENT_PRIORITY"
    local saved_effort="$CURRENT_EFFORT"
    local saved_deps="$CURRENT_DEPS"
    local saved_type="$CURRENT_TYPE"
    local saved_status="$CURRENT_STATUS"
    local saved_labels="$CURRENT_LABELS"
    local saved_created="$CURRENT_CREATED_AT"
    local saved_desc="$CURRENT_DESCRIPTION"
    local saved_children="$CURRENT_CHILDREN_TO_IMPLEMENT"
    local saved_assigned_to="$CURRENT_ASSIGNED_TO"
    local saved_boardcol="$CURRENT_BOARDCOL"
    local saved_boardidx="$CURRENT_BOARDIDX"
    local saved_issue="$CURRENT_ISSUE"
    local saved_folded_tasks="$CURRENT_FOLDED_TASKS"
    local saved_folded_into="$CURRENT_FOLDED_INTO"

    parse_yaml_frontmatter "$parent_file"

    # Remove this child from parent's children_to_implement
    local new_children
    new_children=$(process_children_operations "$CURRENT_CHILDREN_TO_IMPLEMENT" "" "" "$child_id" false)

    # Write updated parent file
    write_task_file "$parent_file" "$CURRENT_PRIORITY" "$CURRENT_EFFORT" "$CURRENT_DEPS" \
        "$CURRENT_TYPE" "$CURRENT_STATUS" "$CURRENT_LABELS" "$CURRENT_CREATED_AT" \
        "$CURRENT_DESCRIPTION" "$new_children" "$CURRENT_ASSIGNED_TO" \
        "$CURRENT_BOARDCOL" "$CURRENT_BOARDIDX" "$CURRENT_ISSUE" "$CURRENT_FOLDED_TASKS" \
        "$CURRENT_FOLDED_INTO"

    if [[ -z "$new_children" ]]; then
        success "All children of t$parent_num are complete! Parent can now be completed."
    else
        info "Updated parent t$parent_num - remaining children: $new_children"
    fi

    # Restore original values
    CURRENT_PRIORITY="$saved_priority"
    CURRENT_EFFORT="$saved_effort"
    CURRENT_DEPS="$saved_deps"
    CURRENT_ASSIGNED_TO="$saved_assigned_to"
    CURRENT_TYPE="$saved_type"
    CURRENT_STATUS="$saved_status"
    CURRENT_LABELS="$saved_labels"
    CURRENT_CREATED_AT="$saved_created"
    CURRENT_DESCRIPTION="$saved_desc"
    CURRENT_CHILDREN_TO_IMPLEMENT="$saved_children"
    CURRENT_BOARDCOL="$saved_boardcol"
    CURRENT_BOARDIDX="$saved_boardidx"
    CURRENT_ISSUE="$saved_issue"
    CURRENT_FOLDED_TASKS="$saved_folded_tasks"
    CURRENT_FOLDED_INTO="$saved_folded_into"
}

# Validate that parent cannot be completed with pending children
validate_parent_completion() {
    local task_id="$1"
    local new_status="$2"
    local children="$3"

    # Only check for parent tasks being set to Done
    if [[ "$new_status" != "Done" ]]; then
        return 0
    fi

    # Check if this is a parent task (has children)
    if [[ -n "$children" ]]; then
        die "Cannot complete parent task: children_to_implement still contains: $children"
    fi

    return 0
}

# --- Interactive Mode ---

interactive_select_task() {
    local tasks
    tasks=$("$SCRIPT_DIR/aitask_ls.sh" -v -s all 99 2>/dev/null || echo "")

    if [[ -z "$tasks" ]]; then
        die "No tasks found in $TASK_DIR"
    fi

    local selected
    selected=$(echo "$tasks" | fzf --prompt="Select task to update: " --height=20 --no-info --header="Select a task to update")

    if [[ -z "$selected" ]]; then
        die "No task selected"
    fi

    # Extract task number from selection (format: t10_name.md [...])
    echo "$selected" | grep -oE '^t[0-9]+' | sed 's/t//'
}

interactive_select_field() {
    local priority="$1"
    local effort="$2"
    local status="$3"
    local issue_type="$4"
    local deps="$5"
    local labels="$6"

    local options="priority      [current: $priority]
effort        [current: $effort]
status        [current: $status]
issue_type    [current: $issue_type]
dependencies  [current: ${deps:-None}]
labels        [current: ${labels:-None}]
description   [edit in editor]
rename        [change filename]
---
Done - save changes
Exit - discard changes"

    local selected
    selected=$(echo "$options" | fzf --prompt="Select field to update: " --height=17 --no-info --header="Select a field to update, Done to save, or Exit to discard")

    # Extract just the field name (before the bracket or spaces)
    echo "$selected" | sed 's/[[:space:]]*\[.*//' | sed 's/[[:space:]]*$//'
}

interactive_update_priority() {
    local current="$1"
    echo -e "high\nmedium\nlow" | fzf --prompt="Priority (current: $current): " --height=10 --no-info --header="Select new priority"
}

interactive_update_effort() {
    local current="$1"
    echo -e "low\nmedium\nhigh" | fzf --prompt="Effort (current: $current): " --height=10 --no-info --header="Select new effort level"
}

interactive_update_status() {
    local current="$1"
    echo -e "Ready\nEditing\nImplementing\nPostponed\nDone\nFolded" | fzf --prompt="Status (current: $current): " --height=12 --no-info --header="Select new status"
}

interactive_update_type() {
    local current="$1"
    get_valid_task_types | fzf --prompt="Type (current: $current): " --height=10 --no-info --header="Select issue type"
}

interactive_update_deps() {
    local current="$1"
    local exclude_task="$2"  # Task number to exclude (the task being updated)

    local tasks
    tasks=$("$SCRIPT_DIR/aitask_ls.sh" -v -s all 99 2>/dev/null || echo "")

    if [[ -z "$tasks" ]]; then
        echo ""
        return
    fi

    # Filter out the current task from the list
    if [[ -n "$exclude_task" ]]; then
        tasks=$(echo "$tasks" | grep -v "^t${exclude_task}_")
    fi

    if [[ -z "$tasks" ]]; then
        echo ""
        return
    fi

    info "Current dependencies: ${current:-None}" >&2

    local options
    options=$(echo -e "Clear all dependencies\n$tasks")

    local selected
    selected=$(echo "$options" | fzf --multi --prompt="Dependencies (Tab to select): " --height=15 --no-info --header="Select task dependencies (Tab=select, Enter=confirm)")

    if [[ -z "$selected" ]] || echo "$selected" | grep -q "^Clear all"; then
        echo ""
        return
    fi

    # Extract task numbers
    echo "$selected" | grep -oE '^t[0-9]+' | sed 's/t//' | tr '\n' ',' | sed 's/,$//'
}

interactive_update_labels() {
    local current="$1"

    set +e  # Disable exit-on-error for fzf operations

    local -a labels_array=()
    if [[ -n "$current" ]]; then
        IFS=',' read -ra labels_array <<< "$current"
    fi

    info "Current labels: ${current:-None}" >&2

    while true; do
        local existing_labels
        existing_labels=$(get_existing_labels)

        local available_labels=""
        if [[ -n "$existing_labels" ]]; then
            while IFS= read -r lbl; do
                local is_selected=false
                for sel in "${labels_array[@]}"; do
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

        local options=">> Done with labels"$'\n'">> Clear all labels"$'\n'">> Add new label"
        if [[ -n "$available_labels" ]]; then
            options="$options"$'\n'"$available_labels"
        fi

        # Show currently selected
        if [[ ${#labels_array[@]} -gt 0 ]]; then
            local IFS=','
            info "Selected: ${labels_array[*]}" >&2
        fi

        local selected
        selected=$(printf "%s" "$options" | fzf --prompt="Select label: " --height=15 --no-info --header="Manage labels")

        if [[ -z "$selected" || "$selected" == ">> Done with labels" ]]; then
            break
        elif [[ "$selected" == ">> Clear all labels" ]]; then
            labels_array=()
            info "Cleared all labels" >&2
        elif [[ "$selected" == ">> Add new label" ]]; then
            local new_label
            read -rp "Enter new label: " new_label
            if [[ -n "$new_label" ]]; then
                local sanitized
                sanitized=$(echo "$new_label" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9_-]//g')
                if [[ -n "$sanitized" ]]; then
                    labels_array+=("$sanitized")
                    add_label_to_file "$sanitized"
                    success "Added: $sanitized" >&2
                fi
            fi
        else
            labels_array+=("$selected")
            success "Added: $selected" >&2
        fi
    done

    set -e  # Re-enable exit-on-error

    local IFS=','
    echo "${labels_array[*]}"
}

# Global variable for description result (set by interactive_update_description_direct)
UPDATED_DESCRIPTION=""

# Direct call version - does NOT use stdout for result
interactive_update_description_direct() {
    local current="$1"

    echo ""
    info "Current description:"
    echo "---"
    echo "$current"
    echo "---"
    echo ""

    # fzf needs explicit terminal access when called from within case statement
    local choice
    exec 3<&0  # save stdin
    exec 0</dev/tty  # redirect stdin from tty
    choice=$(printf "Open in editor\nSkip (keep current)" | fzf --prompt="Edit description? " --height=8 --no-info 2>/dev/tty)
    exec 0<&3  # restore stdin
    exec 3<&-  # close fd 3

    if [[ "$choice" == "Open in editor" ]]; then
        # Create temp file with current description
        local tmpfile
        tmpfile=$(mktemp "${TMPDIR:-/tmp}/aitask_XXXXXX.md")

        # Write content
        printf '%s' "$current" > "$tmpfile"

        # Determine editor and run with proper wait flag for GUI editors
        local editor="${EDITOR:-vim}"

        # Handle common GUI editors that need --wait flag
        case "$editor" in
            code|code-insiders)
                "$editor" --wait "$tmpfile"
                ;;
            subl|sublime_text)
                "$editor" --wait "$tmpfile"
                ;;
            atom)
                "$editor" --wait "$tmpfile"
                ;;
            gedit)
                "$editor" --wait "$tmpfile"
                ;;
            *)
                # For terminal editors and unknown editors, run normally
                "$editor" "$tmpfile"
                ;;
        esac

        # Read back the edited content into global variable
        UPDATED_DESCRIPTION=$(cat "$tmpfile")
        rm "$tmpfile"
    else
        UPDATED_DESCRIPTION="$current"
    fi
}

interactive_rename() {
    local current_file="$1"
    local current_name
    current_name=$(basename "$current_file" .md | sed 's/^t[0-9]*_//')

    echo "" >&2
    info "Current name: $current_name" >&2

    local new_name
    read -rp "Enter new name (or press Enter to keep current): " new_name

    if [[ -n "$new_name" ]]; then
        sanitize_name "$new_name"
    else
        echo ""
    fi
}

run_interactive_mode() {
    local task_num="$BATCH_TASK_NUM"

    # Check terminal capabilities (warn on incapable terminals)
    ait_warn_if_incapable_terminal

    # Check dependencies
    command -v fzf &>/dev/null || die "fzf is required but not installed"

    # Select task if not provided
    if [[ -z "$task_num" ]]; then
        task_num=$(interactive_select_task)
    fi

    # Resolve task file
    local file_path
    file_path=$(resolve_task_file "$task_num")

    info "Updating: $file_path"
    echo ""

    # Parse current values
    parse_yaml_frontmatter "$file_path"

    # New values (start with current)
    local new_priority="$CURRENT_PRIORITY"
    local new_effort="$CURRENT_EFFORT"
    local new_status="$CURRENT_STATUS"
    local new_type="$CURRENT_TYPE"
    local new_deps="$CURRENT_DEPS"
    local new_labels="$CURRENT_LABELS"
    local new_description="$CURRENT_DESCRIPTION"
    local new_name=""
    local changes_made=false

    # Main editing loop
    while true; do
        echo ""
        local field
        field=$(interactive_select_field "$new_priority" "$new_effort" "$new_status" "$new_type" "$new_deps" "$new_labels")

        case "$field" in
            "Exit - discard changes"|"Exit")
                info "Exiting without saving."
                return
                ;;
            "Done - save changes"|"Done"|"---"|"")
                break
                ;;
            priority)
                local result
                result=$(interactive_update_priority "$new_priority")
                if [[ -n "$result" ]]; then
                    new_priority="$result"
                    changes_made=true
                    success "Priority updated to: $new_priority"
                fi
                ;;
            effort)
                local result
                result=$(interactive_update_effort "$new_effort")
                if [[ -n "$result" ]]; then
                    new_effort="$result"
                    changes_made=true
                    success "Effort updated to: $new_effort"
                fi
                ;;
            status)
                local result
                result=$(interactive_update_status "$new_status")
                if [[ -n "$result" ]]; then
                    new_status="$result"
                    changes_made=true
                    success "Status updated to: $new_status"
                fi
                ;;
            issue_type)
                local result
                result=$(interactive_update_type "$new_type")
                if [[ -n "$result" ]]; then
                    new_type="$result"
                    changes_made=true
                    success "Type updated to: $new_type"
                fi
                ;;
            dependencies)
                new_deps=$(interactive_update_deps "$new_deps" "$task_num")
                changes_made=true
                success "Dependencies updated to: ${new_deps:-None}"
                ;;
            labels)
                new_labels=$(interactive_update_labels "$new_labels")
                changes_made=true
                success "Labels updated to: ${new_labels:-None}"
                ;;
            description)
                # Call directly (not in subshell) so editor can access terminal
                interactive_update_description_direct "$new_description"
                new_description="$UPDATED_DESCRIPTION"
                changes_made=true
                success "Description updated"
                ;;
            rename)
                local result
                result=$(interactive_rename "$file_path")
                if [[ -n "$result" ]]; then
                    new_name="$result"
                    changes_made=true
                    success "Will rename to: t${task_num}_${new_name}.md"
                fi
                ;;
        esac
    done

    # Check if any changes were made
    if [[ "$changes_made" == false ]]; then
        info "No changes made."
        return
    fi

    # Handle rename
    local final_path="$file_path"
    if [[ -n "$new_name" ]]; then
        local new_filename="t${task_num}_${new_name}.md"
        final_path="$TASK_DIR/$new_filename"

        if [[ "$file_path" != "$final_path" ]]; then
            mv "$file_path" "$final_path"
            success "Renamed to: $new_filename"
        fi
    fi

    # Validate parent completion
    validate_parent_completion "$task_num" "$new_status" "$CURRENT_CHILDREN_TO_IMPLEMENT"

    # Write updated file (preserve children_to_implement, assigned_to, board fields, issue, folded_tasks)
    write_task_file "$final_path" "$new_priority" "$new_effort" "$new_deps" \
        "$new_type" "$new_status" "$new_labels" "$CURRENT_CREATED_AT" "$new_description" \
        "$CURRENT_CHILDREN_TO_IMPLEMENT" "$CURRENT_ASSIGNED_TO" \
        "$CURRENT_BOARDCOL" "$CURRENT_BOARDIDX" "$CURRENT_ISSUE" "$CURRENT_FOLDED_TASKS" \
        "$CURRENT_FOLDED_INTO"

    # Handle child task completion
    if [[ "$new_status" == "Done" ]]; then
        handle_child_task_completion "$task_num" "$new_status"
    fi

    echo ""
    success "Task updated successfully!"
    echo ""
    echo "Updated values:"
    echo "  Priority:     $new_priority"
    echo "  Effort:       $new_effort"
    echo "  Status:       $new_status"
    echo "  Type:         $new_type"
    echo "  Dependencies: ${new_deps:-None}"
    echo "  Labels:       ${new_labels:-None}"
    if [[ -n "$CURRENT_CHILDREN_TO_IMPLEMENT" ]]; then
        echo "  Children:     $CURRENT_CHILDREN_TO_IMPLEMENT"
    fi
    if [[ -n "$CURRENT_ISSUE" ]]; then
        echo "  Issue:        $CURRENT_ISSUE"
    fi
    echo "  File:         $final_path"

    # Git commit
    read -rp "Commit to git? [Y/n] " commit_choice
    if [[ "$commit_choice" != "n" && "$commit_choice" != "N" ]]; then
        local humanized_name
        humanized_name=$(basename "$final_path" .md | sed 's/^t[0-9]*_\([0-9]*_\)\?//' | tr '_' ' ')
        task_git add "$final_path"
        task_git commit -m "ait: Update task t${task_num}: ${humanized_name}"
        local commit_hash
        commit_hash=$(task_git rev-parse --short HEAD)
        success "Committed: $commit_hash"
    fi
}

# --- Batch Mode ---

run_batch_mode() {
    # Validate task number
    [[ -z "$BATCH_TASK_NUM" ]] && die "Batch mode requires a task number"

    # Resolve task file
    local file_path
    file_path=$(resolve_task_file "$BATCH_TASK_NUM")

    # Parse current values
    parse_yaml_frontmatter "$file_path"

    # Check that at least one update is specified
    local has_update=false
    [[ -n "$BATCH_PRIORITY" ]] && has_update=true
    [[ -n "$BATCH_EFFORT" ]] && has_update=true
    [[ -n "$BATCH_STATUS" ]] && has_update=true
    [[ -n "$BATCH_TYPE" ]] && has_update=true
    [[ "$BATCH_DEPS_SET" == true ]] && has_update=true
    [[ "$BATCH_LABELS_SET" == true ]] && has_update=true
    [[ ${#BATCH_ADD_LABELS[@]} -gt 0 ]] && has_update=true
    [[ ${#BATCH_REMOVE_LABELS[@]} -gt 0 ]] && has_update=true
    [[ -n "$BATCH_DESC" || -n "$BATCH_DESC_FILE" ]] && has_update=true
    [[ -n "$BATCH_NAME" ]] && has_update=true
    [[ -n "$BATCH_ADD_CHILD" ]] && has_update=true
    [[ -n "$BATCH_REMOVE_CHILD" ]] && has_update=true
    [[ "$BATCH_CHILDREN_SET" == true ]] && has_update=true
    [[ "$BATCH_ASSIGNED_TO_SET" == true ]] && has_update=true
    [[ "$BATCH_BOARDCOL_SET" == true ]] && has_update=true
    [[ "$BATCH_BOARDIDX_SET" == true ]] && has_update=true
    [[ "$BATCH_ISSUE_SET" == true ]] && has_update=true
    [[ "$BATCH_FOLDED_TASKS_SET" == true ]] && has_update=true
    [[ "$BATCH_FOLDED_INTO_SET" == true ]] && has_update=true

    if [[ "$has_update" == false ]]; then
        die "No update parameters specified. Use --help for usage."
    fi

    # Validate enum values
    if [[ -n "$BATCH_PRIORITY" ]]; then
        case "$BATCH_PRIORITY" in
            high|medium|low) ;;
            *) die "Invalid priority: $BATCH_PRIORITY (must be high, medium, or low)" ;;
        esac
    fi

    if [[ -n "$BATCH_EFFORT" ]]; then
        case "$BATCH_EFFORT" in
            low|medium|high) ;;
            *) die "Invalid effort: $BATCH_EFFORT (must be low, medium, or high)" ;;
        esac
    fi

    if [[ -n "$BATCH_STATUS" ]]; then
        case "$BATCH_STATUS" in
            Ready|Editing|Implementing|Postponed|Done|Folded) ;;
            *) die "Invalid status: $BATCH_STATUS (must be Ready, Editing, Implementing, Postponed, Done, or Folded)" ;;
        esac
    fi

    if [[ -n "$BATCH_TYPE" ]]; then
        validate_task_type "$BATCH_TYPE"
    fi

    # Handle description from file
    if [[ -n "$BATCH_DESC_FILE" ]]; then
        if [[ "$BATCH_DESC_FILE" == "-" ]]; then
            BATCH_DESC=$(cat)
        else
            [[ -f "$BATCH_DESC_FILE" ]] || die "Description file not found: $BATCH_DESC_FILE"
            BATCH_DESC=$(cat "$BATCH_DESC_FILE")
        fi
    fi

    # Apply updates (use current value if not specified)
    local new_priority="${BATCH_PRIORITY:-$CURRENT_PRIORITY}"
    local new_effort="${BATCH_EFFORT:-$CURRENT_EFFORT}"
    local new_status="${BATCH_STATUS:-$CURRENT_STATUS}"
    local new_type="${BATCH_TYPE:-$CURRENT_TYPE}"
    local new_deps="${BATCH_DEPS:-$CURRENT_DEPS}"
    local new_description="${BATCH_DESC:-$CURRENT_DESCRIPTION}"

    # Special handling: if --deps was passed, use BATCH_DEPS even if empty
    if [[ "$BATCH_DEPS_SET" == true ]]; then
        new_deps="$BATCH_DEPS"
    fi
    new_deps=$(normalize_task_ids "$new_deps")

    # Process labels
    local new_labels
    new_labels=$(process_label_operations "$CURRENT_LABELS" "$BATCH_LABELS" BATCH_ADD_LABELS BATCH_REMOVE_LABELS "$BATCH_LABELS_SET")

    # Process children_to_implement
    local new_children
    new_children=$(process_children_operations "$CURRENT_CHILDREN_TO_IMPLEMENT" "$BATCH_CHILDREN" "$BATCH_ADD_CHILD" "$BATCH_REMOVE_CHILD" "$BATCH_CHILDREN_SET")
    new_children=$(normalize_task_ids "$new_children")

    # Process assigned_to
    local new_assigned_to="$CURRENT_ASSIGNED_TO"
    if [[ "$BATCH_ASSIGNED_TO_SET" == true ]]; then
        new_assigned_to="$BATCH_ASSIGNED_TO"
    fi

    # Process board fields
    local new_boardcol="$CURRENT_BOARDCOL"
    if [[ "$BATCH_BOARDCOL_SET" == true ]]; then
        new_boardcol="$BATCH_BOARDCOL"
    fi
    local new_boardidx="$CURRENT_BOARDIDX"
    if [[ "$BATCH_BOARDIDX_SET" == true ]]; then
        new_boardidx="$BATCH_BOARDIDX"
    fi

    # Process issue
    local new_issue="$CURRENT_ISSUE"
    if [[ "$BATCH_ISSUE_SET" == true ]]; then
        new_issue="$BATCH_ISSUE"
    fi

    # Process folded_tasks
    local new_folded_tasks="$CURRENT_FOLDED_TASKS"
    if [[ "$BATCH_FOLDED_TASKS_SET" == true ]]; then
        new_folded_tasks="$BATCH_FOLDED_TASKS"
    fi

    # Process folded_into
    local new_folded_into="$CURRENT_FOLDED_INTO"
    if [[ "$BATCH_FOLDED_INTO_SET" == true ]]; then
        new_folded_into="$BATCH_FOLDED_INTO"
    fi

    # Validate parent completion (cannot complete parent with pending children)
    validate_parent_completion "$BATCH_TASK_NUM" "$new_status" "$new_children"

    # Handle rename
    local final_path="$file_path"
    if [[ -n "$BATCH_NAME" ]]; then
        local sanitized_name
        sanitized_name=$(sanitize_name "$BATCH_NAME")
        [[ -z "$sanitized_name" ]] && die "Invalid task name after sanitization"

        local new_filename="t${BATCH_TASK_NUM}_${sanitized_name}.md"
        final_path="$TASK_DIR/$new_filename"

        if [[ "$file_path" != "$final_path" ]]; then
            mv "$file_path" "$final_path"
        fi
    fi

    # Write updated file
    write_task_file "$final_path" "$new_priority" "$new_effort" "$new_deps" \
        "$new_type" "$new_status" "$new_labels" "$CURRENT_CREATED_AT" "$new_description" \
        "$new_children" "$new_assigned_to" "$new_boardcol" "$new_boardidx" "$new_issue" \
        "$new_folded_tasks" "$new_folded_into"

    # Handle child task completion (update parent if needed)
    if [[ "$new_status" == "Done" ]]; then
        handle_child_task_completion "$BATCH_TASK_NUM" "$new_status"
    fi

    # Git commit if requested
    if [[ "$BATCH_COMMIT" == true ]]; then
        local humanized_name
        humanized_name=$(basename "$final_path" .md | sed 's/^t[0-9]*_\([0-9]*_\)\?//' | tr '_' ' ')
        task_git add "$final_path"
        task_git commit -m "ait: Update task t${BATCH_TASK_NUM}: ${humanized_name}"
    fi

    # Output
    if [[ "$BATCH_SILENT" == true ]]; then
        echo "$final_path"
    else
        echo "Updated: $final_path"
    fi
}

# --- Main ---

main() {
    # Store original args for detecting --deps flag
    ORIGINAL_ARGS=("$@")

    parse_args "$@"

    if [[ "$BATCH_MODE" == true ]]; then
        run_batch_mode
    else
        run_interactive_mode
    fi
}

main "$@"
