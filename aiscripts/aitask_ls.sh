#!/usr/bin/env bash

TASK_DIR="aitasks"

# --- Help Function ---
show_help() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS] [NUMBER]

Scans the '$TASK_DIR' subdirectory for markdown task files (t<number>_<name>.md),
parses their metadata, and lists them ordered by:
  1. Status (Unblocked tasks first)
  2. Priority (High -> Low)
  3. Effort   (Low -> High)

ARGUMENTS:
  NUMBER        Return only the top N tasks.

OPTIONS:
  -v            Verbose mode. Displays metadata (Status, Priority, Effort)
                alongside the filename.
  -s, --status  Filter by status. Values: Ready, Editing, Implementing, Postponed, Done, Folded, all
                Default: Ready (only show Ready tasks)
  -l, --labels LABELS  Filter by labels (comma-separated). Only show tasks
                with at least one matching label.
  -c, --children PARENT  List only children of specified parent task number.
  --all-levels  Show all tasks including children (flat list).
  --tree        Show hierarchical tree view with children indented.
  -h, --help    Show this help message.

METADATA FORMAT:
  The file uses YAML front matter (lines between --- markers).
  Missing properties default to 'Medium'.

    ---
    priority: high|medium|low
    effort: high|medium|low
    depends: [1, 3, 5]
    issue_type: bug|chore|documentation|feature|performance|refactor|style|test
    status: Editing|Implementing|Postponed|Ready|Done|Folded
    labels: [ui, backend]
    assigned_to: email@example.com
    created_at: 2026-02-01 14:30
    updated_at: 2026-02-01 15:45
    ---
EOF
}

# --- Argument Parsing ---
# If no arguments are provided, show help
if [ $# -eq 0 ]; then
    show_help
    exit 0
fi

VERBOSE=false
LIMIT=0
STATUS_FILTER="Ready"
LABELS_FILTER=""
CHILDREN_OF=""
ALL_LEVELS=false
TREE_VIEW=false

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        -v)
            VERBOSE=true
            shift
            ;;
        -s|--status)
            STATUS_FILTER="$2"
            shift 2
            ;;
        -l|--labels)
            LABELS_FILTER="$2"
            shift 2
            ;;
        -c|--children)
            CHILDREN_OF="$2"
            shift 2
            ;;
        --all-levels)
            ALL_LEVELS=true
            shift
            ;;
        --tree)
            TREE_VIEW=true
            ALL_LEVELS=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *[0-9]*)
            if [[ "$1" =~ ^[0-9]+$ ]]; then
                LIMIT=$1
                shift
            else
                echo "Unknown argument: $1"
                show_help
                exit 1
            fi
            ;;
        *)
            echo "Unknown argument: $1"
            show_help
            exit 1
            ;;
    esac
done

# Check if directory exists
if [ ! -d "$TASK_DIR" ]; then
    echo "Error: Directory '$TASK_DIR' not found."
    exit 1
fi

# --- Core Logic ---

# 1. Map existing task IDs (including child tasks)
existing_ids_file=$(mktemp)

# Add parent-level task IDs
ls "$TASK_DIR" 2>/dev/null | grep -E '^t[0-9]+_.*\.md$' | awk -F'_' '{print substr($1,2)}' > "$existing_ids_file"

# Add child task IDs (format: t1_2)
for child_dir in "$TASK_DIR"/t*/; do
    [ -d "$child_dir" ] || continue
    ls "$child_dir" 2>/dev/null | grep -E '^t[0-9]+_[0-9]+_.*\.md$' | grep -oE '^t[0-9]+_[0-9]+' >> "$existing_ids_file"
done

# Check for duplicate parent task IDs
duplicate_parent_ids=$(sort "$existing_ids_file" | uniq -d)
if [[ -n "$duplicate_parent_ids" ]]; then
    echo -e "\033[1;33mWarning: Duplicate task IDs detected: $duplicate_parent_ids\033[0m" >&2
    echo -e "\033[1;33mRun 'ait setup' to initialize the atomic task ID counter.\033[0m" >&2
fi

is_task_uncompleted() {
    local task_id="$1"

    # Handle child task references (e.g., t1_2 or just the ID format)
    if [[ "$task_id" =~ ^t?([0-9]+)_([0-9]+)$ ]]; then
        # Child task ID format
        grep -qFx "t${BASH_REMATCH[1]}_${BASH_REMATCH[2]}" "$existing_ids_file"
    else
        # Regular parent task ID
        grep -qFx "$task_id" "$existing_ids_file"
    fi
}

# 2. Parsing Functions

# Global variables set by parse functions
p_score=2
e_score=2
blocked=0
p_text="Medium"
e_text="Medium"
d_text="None"
issue_type_text="feature"
status_text="Ready"
labels_text=""
children_to_implement_text=""
has_children=0
assigned_to_text=""
issue_text=""

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

parse_yaml_frontmatter() {
    local file_path="$1"
    local in_frontmatter=false
    local line_num=0

    while IFS= read -r line; do
        ((line_num++))

        # First line should be ---
        if [[ $line_num -eq 1 ]]; then
            if [[ "$line" == "---" ]]; then
                in_frontmatter=true
                continue
            else
                return
            fi
        fi

        # End of front matter
        if [[ "$line" == "---" ]]; then
            break
        fi

        # Parse YAML key-value pairs
        if [[ "$line" =~ ^([a-z_]+):(.*)$ ]]; then
            local key="${BASH_REMATCH[1]}"
            local value="${BASH_REMATCH[2]}"
            # Trim leading/trailing whitespace
            value=$(echo "$value" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

            case "$key" in
                priority)
                    case "$value" in
                        high)   p_score=1; p_text="High" ;;
                        medium) p_score=2; p_text="Medium" ;;
                        low)    p_score=3; p_text="Low" ;;
                    esac
                    ;;
                effort)
                    case "$value" in
                        low)    e_score=1; e_text="Low" ;;
                        medium) e_score=2; e_text="Medium" ;;
                        high)   e_score=3; e_text="High" ;;
                    esac
                    ;;
                depends)
                    # Parse YAML list: [1, 3, 5] -> 1,3,5
                    d_text=$(echo "$value" | tr -d '[]' | tr -d ' ')
                    d_text=$(normalize_task_ids "$d_text")
                    ;;
                issue_type)
                    issue_type_text="$value"
                    ;;
                status)
                    status_text="$value"
                    ;;
                labels)
                    # Parse YAML list: [ui, backend] -> ui,backend
                    labels_text=$(echo "$value" | tr -d '[]' | tr -d ' ')
                    ;;
                children_to_implement)
                    # Parse YAML list: [t1_1, t1_2] -> t1_1,t1_2
                    children_to_implement_text=$(echo "$value" | tr -d '[]' | tr -d ' ')
                    children_to_implement_text=$(normalize_task_ids "$children_to_implement_text")
                    ;;
                assigned_to)
                    assigned_to_text="$value"
                    ;;
                issue)
                    issue_text="$value"
                    ;;
            esac
        fi
    done < "$file_path"
}

calculate_blocked_status() {
    blocked=0
    local blocking_info=""

    # Check explicit dependencies
    if [[ "$d_text" != "None" && -n "$d_text" ]]; then
        IFS=',' read -ra ADDR <<< "$d_text"
        for dep_id in "${ADDR[@]}"; do
            if is_task_uncompleted "$dep_id"; then
                blocked=1
                blocking_info="$d_text"
                break
            fi
        done
    fi

    # Track if task has children (for display purposes only, doesn't affect blocking/sorting)
    if [[ -n "$children_to_implement_text" ]]; then
        has_children=1
    fi

    # Update d_text for display
    if [[ "$blocked" -eq 1 && -n "$blocking_info" ]]; then
        d_text="$blocking_info"
    fi
}

parse_task_metadata() {
    local file_path="$1"

    # Reset to defaults
    p_score=2; p_text="Medium"
    e_score=2; e_text="Medium"
    blocked=0; d_text="None"
    issue_type_text="feature"
    status_text="Ready"
    labels_text=""
    children_to_implement_text=""
    has_children=0
    assigned_to_text=""
    issue_text=""

    # Parse YAML front matter
    parse_yaml_frontmatter "$file_path"

    # Calculate blocked status from dependencies
    calculate_blocked_status
}

# 3. Process Files
DELIM=$'\t'

# Helper function to process a single task file
process_task_file() {
    local file_path="$1"
    local indent_prefix="${2:-}"
    local task_type="${3:-parent}"  # parent or child

    [ -e "$file_path" ] || return

    local filename
    filename=$(basename "$file_path")

    # Parse metadata (sets global variables)
    parse_task_metadata "$file_path"

    # Apply status filter
    if [[ "$STATUS_FILTER" != "all" ]]; then
        if [[ "$status_text" != "$STATUS_FILTER" ]]; then
            return
        fi
    fi

    # Apply labels filter
    if [[ -n "$LABELS_FILTER" ]]; then
        local match_found=false
        IFS=',' read -ra FILTER_LABELS <<< "$LABELS_FILTER"
        IFS=',' read -ra TASK_LABELS <<< "$labels_text"
        for filter_label in "${FILTER_LABELS[@]}"; do
            for task_label in "${TASK_LABELS[@]}"; do
                if [[ "$filter_label" == "$task_label" ]]; then
                    match_found=true
                    break 2
                fi
            done
        done
        if [[ "$match_found" == false ]]; then
            return
        fi
    fi

    # Determine display status string
    local display_status
    if [ "$blocked" -eq 1 ]; then
        display_status="Blocked (by $d_text)"
    elif [ "$has_children" -eq 1 ]; then
        display_status="Has children"
    elif [[ "$status_text" != "Ready" ]]; then
        display_status="$status_text"
    else
        display_status="Ready"
    fi

    # Construct Output
    local display
    if [ "$VERBOSE" = true ]; then
        local assigned_info=""
        if [[ -n "$assigned_to_text" ]]; then
            assigned_info=", Assigned: $assigned_to_text"
        fi
        local issue_info=""
        if [[ -n "$issue_text" ]]; then
            issue_info=", Issue: $issue_text"
        fi
        display="${indent_prefix}$filename [Status: $display_status, Priority: $p_text, Effort: $e_text${assigned_info}${issue_info}]"
    else
        display="${indent_prefix}$filename"
    fi

    echo "$blocked $p_score $e_score $DELIM$display"
}

# Collect output in a temp file
output_file=$(mktemp)

# Mode 1: List children of a specific parent
if [[ -n "$CHILDREN_OF" ]]; then
    child_dir="$TASK_DIR/t${CHILDREN_OF}"
    if [[ -d "$child_dir" ]]; then
        for file_path in "$child_dir"/t${CHILDREN_OF}_*_*.md; do
            process_task_file "$file_path" "" "child"
        done >> "$output_file"
    fi

# Mode 2: Tree view (parents with indented children)
elif [[ "$TREE_VIEW" = true ]]; then
    for file_path in "$TASK_DIR"/t*_*.md; do
        [ -e "$file_path" ] || continue

        # Get parent task number
        task_num=$(basename "$file_path" | grep -oE '^t[0-9]+' | sed 's/t//')

        # Process parent
        process_task_file "$file_path" "" "parent" >> "$output_file"

        # Process children if they exist
        child_dir="$TASK_DIR/t${task_num}"
        if [[ -d "$child_dir" ]]; then
            for child_path in "$child_dir"/t${task_num}_*_*.md; do
                [ -e "$child_path" ] || continue
                process_task_file "$child_path" "  └─ " "child" >> "$output_file"
            done
        fi
    done

# Mode 3: All levels (flat list of parents and children)
elif [[ "$ALL_LEVELS" = true ]]; then
    # Parents first
    for file_path in "$TASK_DIR"/t*_*.md; do
        process_task_file "$file_path" "" "parent"
    done >> "$output_file"

    # Then children
    for child_dir in "$TASK_DIR"/t*/; do
        [ -d "$child_dir" ] || continue
        for file_path in "$child_dir"/t*_*_*.md; do
            process_task_file "$file_path" "" "child"
        done
    done >> "$output_file"

# Mode 4: Normal (parents only, default)
else
    for file_path in "$TASK_DIR"/t*_*.md; do
        process_task_file "$file_path" "" "parent"
    done >> "$output_file"
fi

# Sort and limit output (skip sorting for tree view to preserve hierarchy)
if [[ "$TREE_VIEW" = true ]]; then
    cat "$output_file" | awk -F"$DELIM" '{print $2}' | {
        if [ "$LIMIT" -gt 0 ]; then
            head -n "$LIMIT"
        else
            cat
        fi
    }
else
    cat "$output_file" | sort -k1,1n -k2,2n -k3,3n | awk -F"$DELIM" '{print $2}' | {
        if [ "$LIMIT" -gt 0 ]; then
            head -n "$LIMIT"
        else
            cat
        fi
    }
fi

rm "$existing_ids_file" "$output_file"
