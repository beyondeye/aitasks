#!/bin/bash

# aitask_stats.sh - Calculate and display AI task completion statistics

TASK_DIR="aitasks"
ARCHIVE_DIR="$TASK_DIR/archived"
ARCHIVE_TAR="$ARCHIVE_DIR/old.tar.gz"
TASK_TYPES_FILE="$TASK_DIR/metadata/task_types.txt"

# --- Help Function ---
show_help() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Calculate and display statistics for AI task completions.

OPTIONS:
  -d, --days N          Show daily breakdown for last N days (default: 7)
  -w, --week-start DAY  First day of week (e.g., mon, sun, tue). Default: Monday
  -v, --verbose         Show individual task IDs in daily breakdown
  --csv [FILE]          Export raw data to CSV (default: aitask_stats.csv)
  -h, --help            Show this help message

STATISTICS PROVIDED:
  - Summary: Total completions, 7-day and 30-day counts
  - Daily breakdown: Completions per day
  - Day of week: Current week counts + 30d/all-time averages
  - Label weekly trends: Last 4 weeks per label
  - Task type trends: Parent/child and issue type weekly trends
  - Label+type trends: Issue types by label weekly

EXAMPLES:
  $(basename "$0")              # Basic stats (last 7 days)
  $(basename "$0") -d 14        # Extended daily view (14 days)
  $(basename "$0") -w sun       # Week starts on Sunday
  $(basename "$0") -v           # Verbose with task IDs
  $(basename "$0") --csv        # Export to CSV
EOF
}

# --- Task Types ---

get_valid_task_types() {
    if [[ -s "$TASK_TYPES_FILE" ]]; then
        sort -u "$TASK_TYPES_FILE"
    else
        printf '%s\n' "bug" "feature" "refactor"
    fi
}

get_type_display_name() {
    case "$1" in
        feature) echo "Features" ;;
        bug) echo "Bug Fixes" ;;
        refactor) echo "Refactors" ;;
        *) echo "$1" | sed 's/^./\U&/' ;;
    esac
}

# --- Default Values ---
DAYS=7
VERBOSE=false
CSV_EXPORT=false
CSV_FILE="aitask_stats.csv"
WEEK_START_DOW=1  # 1=Monday (default), uses %u format: 1=Mon..7=Sun
WEEK_START_RAW=""

# --- Argument Parsing ---
while [[ $# -gt 0 ]]; do
    case $1 in
        -d|--days)
            DAYS="$2"
            shift 2
            ;;
        -w|--week-start)
            WEEK_START_RAW="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        --csv)
            CSV_EXPORT=true
            if [[ -n "$2" && ! "$2" =~ ^- ]]; then
                CSV_FILE="$2"
                shift
            fi
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown argument: $1"
            show_help
            exit 1
            ;;
    esac
done

# --- Resolve week start day ---
resolve_week_start() {
    local input="${1,,}"  # lowercase
    [[ -z "$input" ]] && return

    local day_names=("monday" "tuesday" "wednesday" "thursday" "friday" "saturday" "sunday")
    local day_nums=(1 2 3 4 5 6 7)  # %u format
    local matches=()
    local match_nums=()

    for i in "${!day_names[@]}"; do
        if [[ "${day_names[$i]}" == "$input"* ]]; then
            matches+=("${day_names[$i]}")
            match_nums+=("${day_nums[$i]}")
        fi
    done

    if [[ ${#matches[@]} -eq 1 ]]; then
        WEEK_START_DOW="${match_nums[0]}"
    elif [[ ${#matches[@]} -eq 0 ]]; then
        echo "Warning: '$1' does not match any day of the week. Using default (Monday)." >&2
    else
        local match_list=$(IFS=', '; echo "${matches[*]}")
        echo "Warning: '$1' is ambiguous (matches: $match_list). Using default (Monday)." >&2
    fi
}

if [[ -n "$WEEK_START_RAW" ]]; then
    resolve_week_start "$WEEK_START_RAW"
fi

# --- Utility Functions ---

# Calculate average with one decimal place using pure bash
# Usage: calc_avg numerator denominator
calc_avg() {
    local num="$1"
    local denom="$2"
    [[ $denom -eq 0 ]] && { echo "0.0"; return; }

    # Multiply by 10 to get one decimal place
    local result=$(( (num * 10 + denom / 2) / denom ))
    local int_part=$((result / 10))
    local dec_part=$((result % 10))
    echo "${int_part}.${dec_part}"
}

# --- Date Functions ---
TODAY=$(date +%Y-%m-%d)
TODAY_EPOCH=$(date -d "$TODAY" +%s)

# Get week start date (Monday) for a given date
get_week_start() {
    local date="$1"
    local dow=$(date -d "$date" +%u 2>/dev/null)  # 1=Mon, 7=Sun
    if [[ -z "$dow" ]]; then
        echo ""
        return
    fi
    local offset=$(( (dow - WEEK_START_DOW + 7) % 7 ))
    date -d "$date - $offset days" +%Y-%m-%d
}

# Get week offset from current week (0 = this week, 1 = last week, etc.)
get_week_offset() {
    local completed_date="$1"
    local completed_week_start=$(get_week_start "$completed_date")
    local current_week_start=$(get_week_start "$TODAY")

    if [[ -z "$completed_week_start" ]]; then
        echo "-1"
        return
    fi

    local completed_epoch=$(date -d "$completed_week_start" +%s 2>/dev/null)
    local current_epoch=$(date -d "$current_week_start" +%s 2>/dev/null)

    if [[ -z "$completed_epoch" || -z "$current_epoch" ]]; then
        echo "-1"
        return
    fi

    local diff_days=$(( (current_epoch - completed_epoch) / 86400 ))
    echo $((diff_days / 7))
}

# Check if date is within last N days
is_within_days() {
    local date="$1"
    local n_days="$2"
    local date_epoch=$(date -d "$date" +%s 2>/dev/null)

    if [[ -z "$date_epoch" ]]; then
        return 1
    fi

    local diff_days=$(( (TODAY_EPOCH - date_epoch) / 86400 ))
    [[ $diff_days -ge 0 && $diff_days -lt $n_days ]]
}

# --- Parsing Functions ---

# Parse completed_at from content
parse_completed_at() {
    local content="$1"
    echo "$content" | grep -E "^completed_at:" | head -1 | sed 's/completed_at:[[:space:]]*//'
}

# Parse labels from content
parse_labels() {
    local content="$1"
    echo "$content" | grep -E "^labels:" | head -1 | sed 's/labels:[[:space:]]*//' | tr -d '[]' | tr -d ' '
}

# Parse issue_type from content
parse_issue_type() {
    local content="$1"
    local issue_type=$(echo "$content" | grep -E "^issue_type:" | head -1 | sed 's/issue_type:[[:space:]]*//')
    # Default to feature if not specified
    echo "${issue_type:-feature}"
}

# Parse status from content
parse_status() {
    local content="$1"
    echo "$content" | grep -E "^status:" | head -1 | sed 's/status:[[:space:]]*//'
}

# Determine task type from filename
get_task_type() {
    local filename="$1"
    # Child tasks have pattern t<N>_<M>_*.md (two underscores before the name)
    if [[ "$filename" =~ ^t[0-9]+_[0-9]+_ ]]; then
        echo "child"
    else
        echo "parent"
    fi
}

# Extract task ID from filename
get_task_id() {
    local filename="$1"
    # Remove .md extension and path
    local basename=$(basename "$filename" .md)
    echo "$basename"
}

# --- Data Collection ---

# Associative arrays for statistics
declare -A daily_counts
declare -A daily_tasks
declare -A dow_counts_thisweek
declare -A dow_counts_30d
declare -A dow_counts_total
declare -A label_counts_total
declare -A label_week_counts
declare -A label_dow_counts_30d
declare -A type_week_counts
declare -A label_type_week_counts
declare -A all_labels

# Counters
TOTAL_TASKS=0
TASKS_7D=0
TASKS_30D=0

# CSV data collection
declare -a CSV_ROWS

# Day names
DAY_NAMES=("" "Mon" "Tue" "Wed" "Thu" "Fri" "Sat" "Sun")
DAY_FULL_NAMES=("" "Monday" "Tuesday" "Wednesday" "Thursday" "Friday" "Saturday" "Sunday")

# Current week start
CURRENT_WEEK_START=$(get_week_start "$TODAY")

# Process a single task
process_task() {
    local content="$1"
    local filename="$2"

    local completed_at=$(parse_completed_at "$content")
    local status=$(parse_status "$content")

    # Skip if no completed_at and status is not Done/Completed
    if [[ -z "$completed_at" ]]; then
        if [[ "$status" != "Done" && "$status" != "Completed" ]]; then
            return
        fi
        # Try to use updated_at as fallback
        completed_at=$(echo "$content" | grep -E "^updated_at:" | head -1 | sed 's/updated_at:[[:space:]]*//')
        if [[ -z "$completed_at" ]]; then
            return
        fi
    fi

    # Extract date portion (YYYY-MM-DD)
    local completed_date="${completed_at:0:10}"

    # Validate date format
    if ! date -d "$completed_date" +%s &>/dev/null; then
        return
    fi

    local labels=$(parse_labels "$content")
    local issue_type=$(parse_issue_type "$content")
    local task_type=$(get_task_type "$filename")
    local task_id=$(get_task_id "$filename")

    # Day of week (1=Mon, 7=Sun)
    local dow=$(date -d "$completed_date" +%u 2>/dev/null)
    local day_name="${DAY_NAMES[$dow]}"

    # Week offset
    local week_offset=$(get_week_offset "$completed_date")

    # Update counters
    ((TOTAL_TASKS++))

    # Daily counts
    ((daily_counts["$completed_date"]++))
    if [[ -n "${daily_tasks[$completed_date]}" ]]; then
        daily_tasks["$completed_date"]="${daily_tasks[$completed_date]},$task_id"
    else
        daily_tasks["$completed_date"]="$task_id"
    fi

    # Day of week counts
    ((dow_counts_total[$dow]++))

    # Current week day of week
    local task_week_start=$(get_week_start "$completed_date")
    if [[ "$task_week_start" == "$CURRENT_WEEK_START" ]]; then
        ((dow_counts_thisweek[$dow]++))
    fi

    # 7-day and 30-day counts
    if is_within_days "$completed_date" 7; then
        ((TASKS_7D++))
    fi

    if is_within_days "$completed_date" 30; then
        ((TASKS_30D++))
        ((dow_counts_30d[$dow]++))
    fi

    # Label processing
    if [[ -z "$labels" ]]; then
        labels="(unlabeled)"
    fi

    # Process each label
    IFS=',' read -ra LABEL_ARRAY <<< "$labels"
    for label in "${LABEL_ARRAY[@]}"; do
        [[ -z "$label" ]] && continue
        all_labels["$label"]=1
        ((label_counts_total["$label"]++))

        # Weekly trend for label (last 4 weeks)
        if [[ $week_offset -ge 0 && $week_offset -le 3 ]]; then
            ((label_week_counts["$label:$week_offset"]++))
        fi

        # Per-label day of week (last 30 days)
        if is_within_days "$completed_date" 30; then
            ((label_dow_counts_30d["$label:$dow"]++))
        fi

        # Label + issue type weekly trend
        if [[ $week_offset -ge 0 && $week_offset -le 3 ]]; then
            ((label_type_week_counts["$label:$issue_type:$week_offset"]++))
        fi
    done

    # Task type weekly trends
    if [[ $week_offset -ge 0 && $week_offset -le 3 ]]; then
        ((type_week_counts["$task_type:$week_offset"]++))
        ((type_week_counts["$issue_type:$week_offset"]++))
    fi

    # CSV row
    if $CSV_EXPORT; then
        local csv_labels="${labels//,/;}"  # Replace comma with semicolon for CSV
        CSV_ROWS+=("$completed_date,$day_name,$week_offset,$task_id,\"$csv_labels\",$issue_type,$task_type")
    fi
}

# Collect from archived parent tasks
collect_archived_parents() {
    for file in "$ARCHIVE_DIR"/t*_*.md; do
        [[ -f "$file" ]] || continue
        # Skip if it's actually a child task pattern
        local basename=$(basename "$file")
        if [[ "$basename" =~ ^t[0-9]+_[0-9]+_ ]]; then
            continue
        fi
        local content=$(cat "$file")
        process_task "$content" "$basename"
    done
}

# Collect from archived child tasks
collect_archived_children() {
    for dir in "$ARCHIVE_DIR"/t*/; do
        [[ -d "$dir" ]] || continue
        for file in "$dir"t*_*_*.md; do
            [[ -f "$file" ]] || continue
            local content=$(cat "$file")
            local basename=$(basename "$file")
            process_task "$content" "$basename"
        done
    done
}

# Collect from old.tar.gz archive
collect_from_tarball() {
    [[ -f "$ARCHIVE_TAR" ]] || return

    local files=$(tar -tzf "$ARCHIVE_TAR" 2>/dev/null | grep '\.md$')
    [[ -z "$files" ]] && return

    while IFS= read -r filename; do
        local content=$(tar -xzf "$ARCHIVE_TAR" -O "$filename" 2>/dev/null)
        [[ -z "$content" ]] && continue
        local basename=$(basename "$filename")
        process_task "$content" "$basename"
    done <<< "$files"
}

# --- Output Functions ---

# Print summary section
print_summary() {
    echo "## Task Completion Statistics"
    echo ""
    echo "Generated: $(date '+%Y-%m-%d %H:%M')"
    echo ""
    echo "### Summary"
    echo "| Metric                    | Count |"
    echo "|---------------------------|-------|"
    printf "| Total Tasks Completed     | %-5d |\n" "$TOTAL_TASKS"
    printf "| Completed (Last 7 days)   | %-5d |\n" "$TASKS_7D"
    printf "| Completed (Last 30 days)  | %-5d |\n" "$TASKS_30D"
    echo ""
}

# Print daily completions
print_daily() {
    echo "### Daily Completions (Last $DAYS Days)"
    if $VERBOSE; then
        echo "| Date       | Day | Count | Tasks |"
        echo "|------------|-----|-------|-------|"
    else
        echo "| Date       | Day | Count |"
        echo "|------------|-----|-------|"
    fi

    for ((i=0; i<DAYS; i++)); do
        local date=$(date -d "$TODAY - $i days" +%Y-%m-%d)
        local dow=$(date -d "$date" +%u)
        local day_name="${DAY_NAMES[$dow]}"
        local count=${daily_counts["$date"]:-0}
        local tasks=${daily_tasks["$date"]:-""}

        if $VERBOSE; then
            printf "| %s | %-3s | %-5d | %s |\n" "$date" "$day_name" "$count" "$tasks"
        else
            printf "| %s | %-3s | %-5d |\n" "$date" "$day_name" "$count"
        fi
    done
    echo ""
}

# Print day of week averages
print_dow_averages() {
    echo "### Average Completions by Day of Week"
    echo "| Day       | This Week | Last 30d Avg | All-time Avg |"
    echo "|-----------|-----------|--------------|--------------|"

    # Calculate occurrences of each weekday in the last 30 days
    declare -A dow_occurrences_30d
    for ((i=0; i<30; i++)); do
        local check_date=$(date -d "$TODAY - $i days" +%Y-%m-%d)
        local dow=$(date -d "$check_date" +%u)
        ((dow_occurrences_30d[$dow]++))
    done

    # Calculate total weeks for all-time average
    local first_date=""
    for date in "${!daily_counts[@]}"; do
        if [[ -z "$first_date" || "$date" < "$first_date" ]]; then
            first_date="$date"
        fi
    done

    local total_days=1
    if [[ -n "$first_date" ]]; then
        local first_epoch=$(date -d "$first_date" +%s)
        total_days=$(( (TODAY_EPOCH - first_epoch) / 86400 + 1 ))
    fi
    local total_weeks=$(( (total_days + 6) / 7 ))
    [[ $total_weeks -lt 1 ]] && total_weeks=1

    local current_dow=$(date +%u)
    for ((j=0; j<7; j++)); do
        local dow=$(( (WEEK_START_DOW - 1 + j) % 7 + 1 ))
        local day_name="${DAY_FULL_NAMES[$dow]}"
        local thisweek=${dow_counts_thisweek[$dow]:-0}
        local count_30d=${dow_counts_30d[$dow]:-0}
        local count_total=${dow_counts_total[$dow]:-0}
        local occurrences=${dow_occurrences_30d[$dow]:-1}

        local avg_30d=$(calc_avg "$count_30d" "$occurrences")
        local avg_total=$(calc_avg "$count_total" "$total_weeks")

        local thisweek_display="$thisweek"
        # Check if this day has passed in current week
        # A day hasn't passed if it's after today in the week cycle
        local today_offset=$(( (current_dow - WEEK_START_DOW + 7) % 7 ))
        local day_offset=$(( (dow - WEEK_START_DOW + 7) % 7 ))
        if [[ $day_offset -gt $today_offset ]]; then
            thisweek_display="-"
        fi

        printf "| %-9s | %-9s | %-12s | %-12s |\n" "$day_name" "$thisweek_display" "$avg_30d" "$avg_total"
    done
    echo ""
}

# Print label weekly trends
print_label_trends() {
    echo "### Completions by Label - Weekly Trend (Last 4 Weeks)"
    echo "| Label          | Total | W-3 | W-2 | W-1 | This Week |"
    echo "|----------------|-------|-----|-----|-----|-----------|"

    # Sort labels by total count
    local sorted_labels=$(for label in "${!all_labels[@]}"; do
        echo "${label_counts_total[$label]:-0} $label"
    done | sort -rn | cut -d' ' -f2-)

    while IFS= read -r label; do
        [[ -z "$label" ]] && continue
        local total=${label_counts_total[$label]:-0}
        local w3=${label_week_counts["$label:3"]:-0}
        local w2=${label_week_counts["$label:2"]:-0}
        local w1=${label_week_counts["$label:1"]:-0}
        local w0=${label_week_counts["$label:0"]:-0}

        printf "| %-14s | %-5d | %-3d | %-3d | %-3d | %-9d |\n" "$label" "$total" "$w3" "$w2" "$w1" "$w0"
    done <<< "$sorted_labels"
    echo ""
}

# Print label day of week averages
print_label_dow() {
    echo "### Label Avg by Day of Week (Last 30 Days)"
    # Build header dynamically based on week start day
    local header="| Label        |"
    local separator="|--------------|"
    for ((j=0; j<7; j++)); do
        local hdow=$(( (WEEK_START_DOW - 1 + j) % 7 + 1 ))
        header+=" ${DAY_NAMES[$hdow]} |"
        separator+="-----|"
    done
    echo "$header"
    echo "$separator"

    # Calculate occurrences of each weekday in the last 30 days
    declare -A dow_occurrences_30d
    for ((i=0; i<30; i++)); do
        local check_date=$(date -d "$TODAY - $i days" +%Y-%m-%d)
        local dow=$(date -d "$check_date" +%u)
        ((dow_occurrences_30d[$dow]++))
    done

    # Sort labels by total count
    local sorted_labels=$(for label in "${!all_labels[@]}"; do
        echo "${label_counts_total[$label]:-0} $label"
    done | sort -rn | cut -d' ' -f2-)

    while IFS= read -r label; do
        [[ -z "$label" ]] && continue
        printf "| %-12s |" "$label"
        for ((j=0; j<7; j++)); do
            local dow=$(( (WEEK_START_DOW - 1 + j) % 7 + 1 ))
            local count=${label_dow_counts_30d["$label:$dow"]:-0}
            local occurrences=${dow_occurrences_30d[$dow]:-1}
            local avg=$(calc_avg "$count" "$occurrences")
            printf " %-3s |" "$avg"
        done
        echo ""
    done <<< "$sorted_labels"
    echo ""
}

# Print task type weekly trends
print_type_trends() {
    echo "### By Task Type - Weekly Trend (Last 4 Weeks)"
    echo "| Type           | Total | W-3 | W-2 | W-1 | This Week |"
    echo "|----------------|-------|-----|-----|-----|-----------|"

    for type in "parent" "child"; do
        local total=0
        for week in {0..3}; do
            ((total += ${type_week_counts["$type:$week"]:-0}))
        done

        local w3=${type_week_counts["$type:3"]:-0}
        local w2=${type_week_counts["$type:2"]:-0}
        local w1=${type_week_counts["$type:1"]:-0}
        local w0=${type_week_counts["$type:0"]:-0}

        local display_type
        case $type in
            parent) display_type="Parent Tasks" ;;
            child) display_type="Child Tasks" ;;
        esac

        printf "| %-14s | %-5d | %-3d | %-3d | %-3d | %-9d |\n" "$display_type" "$total" "$w3" "$w2" "$w1" "$w0"
    done

    while IFS= read -r type; do
        [[ -z "$type" ]] && continue
        local total=0
        for week in {0..3}; do
            ((total += ${type_week_counts["$type:$week"]:-0}))
        done

        local w3=${type_week_counts["$type:3"]:-0}
        local w2=${type_week_counts["$type:2"]:-0}
        local w1=${type_week_counts["$type:1"]:-0}
        local w0=${type_week_counts["$type:0"]:-0}

        local display_type
        display_type=$(get_type_display_name "$type")

        printf "| %-14s | %-5d | %-3d | %-3d | %-3d | %-9d |\n" "$display_type" "$total" "$w3" "$w2" "$w1" "$w0"
    done < <(get_valid_task_types)
    echo ""
}

# Print issue types by label trends
print_label_type_trends() {
    echo "### By Issue Type per Label - Weekly Trend (Last 4 Weeks)"
    echo "| Label        | Type    | Total | W-3 | W-2 | W-1 | This Week |"
    echo "|--------------|---------|-------|-----|-----|-----|-----------|"

    # Sort labels by total count
    local sorted_labels=$(for label in "${!all_labels[@]}"; do
        echo "${label_counts_total[$label]:-0} $label"
    done | sort -rn | cut -d' ' -f2-)

    while IFS= read -r label; do
        [[ -z "$label" ]] && continue
        [[ "$label" == "(unlabeled)" ]] && continue

        while IFS= read -r issue_type; do
            [[ -z "$issue_type" ]] && continue
            local total=0
            for week in {0..3}; do
                ((total += ${label_type_week_counts["$label:$issue_type:$week"]:-0}))
            done

            # Skip if no tasks of this type for this label
            [[ $total -eq 0 ]] && continue

            local w3=${label_type_week_counts["$label:$issue_type:3"]:-0}
            local w2=${label_type_week_counts["$label:$issue_type:2"]:-0}
            local w1=${label_type_week_counts["$label:$issue_type:1"]:-0}
            local w0=${label_type_week_counts["$label:$issue_type:0"]:-0}

            local type_display=$(echo "$issue_type" | sed 's/^./\U&/')

            printf "| %-12s | %-7s | %-5d | %-3d | %-3d | %-3d | %-9d |\n" "$label" "$type_display" "$total" "$w3" "$w2" "$w1" "$w0"
        done < <(get_valid_task_types)
    done <<< "$sorted_labels"
    echo ""
}

# Export to CSV
export_to_csv() {
    echo "date,day_of_week,week_offset,task_id,labels,issue_type,task_type" > "$CSV_FILE"

    # Sort CSV rows by date (descending)
    for row in "${CSV_ROWS[@]}"; do
        echo "$row"
    done | sort -t',' -k1 -r >> "$CSV_FILE"

    echo "CSV exported to: $CSV_FILE"
    echo ""
    echo "To create charts in LibreOffice Calc:"
    echo "1. Open LibreOffice Calc"
    echo "2. File -> Open -> Select $CSV_FILE"
    echo "3. In import dialog: UTF-8, Comma separator, 'Quoted field as text'"
    echo "4. Use Insert -> Chart or Insert -> Pivot Table for analysis"
}

# --- Main ---

# Check if archive directory exists
if [[ ! -d "$ARCHIVE_DIR" ]]; then
    echo "No archived tasks found in $ARCHIVE_DIR"
    exit 0
fi

# Collect all data
collect_archived_parents
collect_archived_children
collect_from_tarball

# Check if any tasks were found
if [[ $TOTAL_TASKS -eq 0 ]]; then
    echo "No completed tasks found."
    exit 0
fi

# Output
if $CSV_EXPORT; then
    export_to_csv
else
    print_summary
    print_daily
    print_dow_averages
    print_label_trends
    print_label_dow
    print_type_trends
    print_label_type_trends
fi
