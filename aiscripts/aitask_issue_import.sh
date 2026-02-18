#!/bin/bash

# aitask_issue_import.sh - Import GitHub/GitLab/Bitbucket issues as AI task files
# Uses gh/glab/bkt CLI to fetch issue data and aitask_create.sh to create tasks

set -e

TASK_DIR="aitasks"
ARCHIVED_DIR="aitasks/archived"
LABELS_FILE="aitasks/metadata/labels.txt"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"

# Batch mode variables
BATCH_MODE=false
SOURCE=""  # Auto-detected from git remote if not set via --source
BATCH_ISSUE_NUM=""
BATCH_ISSUE_RANGE=""
BATCH_ALL=false
BATCH_PRIORITY="medium"
BATCH_EFFORT="medium"
BATCH_TYPE=""
BATCH_STATUS="Ready"
BATCH_LABELS=""
BATCH_DEPS=""
BATCH_PARENT=""
BATCH_NO_SIBLING_DEP=false
BATCH_COMMIT=false
BATCH_SILENT=false
BATCH_SKIP_DUPLICATES=false
BATCH_NO_COMMENTS=false

# --- Helper Functions ---

sanitize_name() {
    local name="$1"
    # Convert to lowercase, replace spaces with underscores, remove special chars
    echo "$name" | tr '[:upper:]' '[:lower:]' | tr ' ' '_' | tr -cd 'a-z0-9_' | sed 's/__*/_/g' | sed 's/^_//;s/_$//' | cut -c1-60
}

# Convert UTC timestamp to local timezone
utc_to_local() {
    local utc_ts="$1"
    date -d "$utc_ts" '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo "$utc_ts"
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

# ============================================================
# PLATFORM BACKENDS
# To add a new platform (e.g., GitLab):
#   1. Implement all <platform>_* functions below
#   2. Add to --source validation in parse_args()
#   3. Add case to each source_* dispatcher function
# ============================================================

# --- GitHub Backend ---
# PLATFORM-EXTENSION-POINT: Add new platform backend functions here

github_check_cli() {
    command -v gh &>/dev/null || die "gh CLI is required for GitHub. Install: https://cli.github.com/"
    command -v jq &>/dev/null || die "jq is required. Install via your package manager."
    # Verify authentication
    gh auth status &>/dev/null || die "gh CLI is not authenticated. Run: gh auth login"
}

# Returns JSON with title, body, labels, url, comments, createdAt, updatedAt
github_fetch_issue() {
    local issue_num="$1"
    gh issue view "$issue_num" --json title,body,labels,url,comments,createdAt,updatedAt
}

# Format comments as text for inclusion in task description
# Input: JSON comments array. Output: formatted comment text
github_format_comments() {
    local comments_json="$1"
    local count
    count=$(echo "$comments_json" | jq length)
    [[ "$count" -eq 0 ]] && return 0

    echo ""
    echo "## Comments"
    echo ""
    local i last_idx
    last_idx=$((count - 1))
    for ((i=0; i<count; i++)); do
        local author created_at body local_time
        author=$(echo "$comments_json" | jq -r ".[$i].author.login")
        created_at=$(echo "$comments_json" | jq -r ".[$i].createdAt")
        body=$(echo "$comments_json" | jq -r ".[$i].body")
        local_time=$(utc_to_local "$created_at")
        echo "**${author}** (${local_time})"
        echo ""
        echo "$body"
        if [[ $i -lt $last_idx ]]; then
            echo ""
            echo "-------"
            echo ""
        fi
    done
}

# Returns JSON array: [{"number":N, "title":"...", "labels":[{"name":"..."}], "url":"..."}]
github_list_issues() {
    gh issue list --state open --limit 500 --json number,title,labels,url
}

# Input: JSON labels array [{"name":"..."}]. Output: comma-separated lowercase sanitized labels
github_map_labels() {
    local labels_json="$1"
    local result
    result=$(echo "$labels_json" | jq -r '.[].name' 2>/dev/null | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9_-]/_/g' | sed 's/__*/_/g' | sed 's/^_//;s/_$//' | paste -sd ',' 2>/dev/null)
    echo "$result"
}

# Input: JSON labels array. Output: detected issue type (defaults to "feature")
github_detect_type() {
    local labels_json="$1"
    local label_names
    label_names=$(echo "$labels_json" | jq -r '.[].name' 2>/dev/null)
    if echo "$label_names" | grep -qi "^bug$"; then
        echo "bug"
    elif echo "$label_names" | grep -qiE "^(refactor|refactoring|tech-debt|cleanup)$"; then
        echo "refactor"
    elif echo "$label_names" | grep -qiE "^(test|testing|tests)$"; then
        echo "test"
    elif echo "$label_names" | grep -qiE "^(style|styling|formatting|lint|linting)$"; then
        echo "style"
    elif echo "$label_names" | grep -qiE "^(chore|maintenance|housekeeping|deps|dependencies)$"; then
        echo "chore"
    elif echo "$label_names" | grep -qiE "^(documentation|docs)$"; then
        echo "documentation"
    elif echo "$label_names" | grep -qiE "^(performance|perf|optimization)$"; then
        echo "performance"
    else
        echo "feature"
    fi
}

# Prints issue preview to stdout for user confirmation
github_preview_issue() {
    local issue_num="$1"
    gh issue view "$issue_num" --comments=false
}

# --- GitLab Backend ---

gitlab_check_cli() {
    command -v glab &>/dev/null || die "glab CLI is required for GitLab. Install: https://gitlab.com/gitlab-org/cli"
    command -v jq &>/dev/null || die "jq is required. Install via your package manager."
    glab auth status &>/dev/null || die "glab CLI is not authenticated. Run: glab auth login"
}

# Returns JSON normalized to GitHub-compatible format
# Fields: title, body, labels[{name}], url, comments[{author{login},body,createdAt}], createdAt, updatedAt
gitlab_fetch_issue() {
    local issue_num="$1"
    local issue_json notes_json

    # Fetch issue data
    issue_json=$(glab issue view "$issue_num" -F json)

    # Fetch notes (comments), filtering out system notes
    notes_json=$(glab api "projects/:fullpath/issues/$issue_num/notes?sort=asc&per_page=100" 2>/dev/null || echo "[]")

    # Normalize to GitHub-compatible JSON structure
    echo "$issue_json" | jq --argjson notes "$notes_json" '{
        title: .title,
        body: (.description // ""),
        labels: [.labels[] | {name: .}],
        url: .web_url,
        comments: [$notes[] | select(.system != true) | {
            author: {login: .author.username},
            body: .body,
            createdAt: .created_at
        }],
        createdAt: .created_at,
        updatedAt: .updated_at
    }'
}

# Format comments — reuses github_format_comments since JSON is already normalized
gitlab_format_comments() {
    github_format_comments "$@"
}

# Returns JSON array normalized to GitHub-compatible format
# Fields: [{number, title, labels[{name}], url}]
gitlab_list_issues() {
    glab issue list --all --output json | jq '[.[] | {
        number: .iid,
        title: .title,
        labels: [.labels[] | {name: .}],
        url: .web_url
    }]'
}

# Input: JSON labels array [{name:"..."}] (already normalized). Output: comma-separated lowercase sanitized labels
gitlab_map_labels() {
    github_map_labels "$@"
}

# Input: JSON labels array (already normalized). Output: detected issue type
gitlab_detect_type() {
    github_detect_type "$@"
}

# Prints issue preview to stdout
gitlab_preview_issue() {
    local issue_num="$1"
    glab issue view "$issue_num"
}

# --- Bitbucket Backend ---

bitbucket_check_cli() {
    command -v bkt &>/dev/null || die "bkt CLI is required for Bitbucket. Install: https://github.com/avivsinai/bitbucket-cli"
    command -v jq &>/dev/null || die "jq is required. Install via your package manager."
    bkt auth status &>/dev/null || die "bkt CLI is not authenticated. Run: bkt auth login https://bitbucket.org --kind cloud --web"
}

# Returns JSON normalized to GitHub-compatible format
# bkt --json already provides flat .body and .url fields; we normalize
# .comments[].author from string to {login: string} and synthesize labels from .kind
bitbucket_fetch_issue() {
    local issue_num="$1"
    local issue_json

    # Fetch issue with comments
    issue_json=$(bkt issue view "$issue_num" --comments --json)

    # Normalize to GitHub-compatible JSON structure
    echo "$issue_json" | jq '{
        title: .title,
        body: (.body // ""),
        labels: ([
            (if .kind != null and .kind != "" then {name: .kind} else empty end)
        ]),
        url: .url,
        comments: [(.comments // [])[] | {
            author: {login: .author},
            body: .body,
            createdAt: .created_on
        }],
        createdAt: .created_on,
        updatedAt: .updated_on
    }'
}

# Format comments — reuses github_format_comments since JSON is already normalized
bitbucket_format_comments() {
    github_format_comments "$@"
}

# Returns JSON array normalized to GitHub-compatible format
# bkt wraps the list in {"issues": [...]} envelope; also need --state new
# since default --state open misses newly created issues
bitbucket_list_issues() {
    local all_issues new_issues open_issues
    # Fetch both new and open issues (Bitbucket treats these as separate states)
    new_issues=$(bkt issue list --state new --limit 500 --json | jq '.issues // []')
    open_issues=$(bkt issue list --state open --limit 500 --json | jq '.issues // []')
    # Merge and normalize
    jq -n --argjson new "$new_issues" --argjson open "$open_issues" '
        ($new + $open) | [.[] | {
            number: .id,
            title: .title,
            labels: ([
                (if .kind != null and .kind != "" then {name: .kind} else empty end)
            ]),
            url: .url
        }]'
}

# Input: JSON labels array [{name:"..."}] (already normalized). Output: comma-separated lowercase sanitized labels
bitbucket_map_labels() {
    github_map_labels "$@"
}

# Input: JSON labels array. Output: detected issue type
# Bitbucket uses "kind" values: bug, enhancement, proposal, task
bitbucket_detect_type() {
    local labels_json="$1"
    local label_names
    label_names=$(echo "$labels_json" | jq -r '.[].name' 2>/dev/null)
    if echo "$label_names" | grep -qi "^bug$"; then
        echo "bug"
    elif echo "$label_names" | grep -qi "^task$"; then
        echo "chore"
    elif echo "$label_names" | grep -qiE "^(enhancement|proposal)$"; then
        echo "feature"
    else
        # Fallback to GitHub detection for any other labels
        github_detect_type "$labels_json"
    fi
}

# Prints issue preview to stdout
bitbucket_preview_issue() {
    local issue_num="$1"
    bkt issue view "$issue_num"
}

# --- Dispatcher Functions ---
# PLATFORM-EXTENSION-POINT: Add new platform cases to each dispatcher

source_check_cli() {
    case "$SOURCE" in
        github) github_check_cli ;;
        gitlab) gitlab_check_cli ;;
        bitbucket) bitbucket_check_cli ;;
        *) die "Unknown source: $SOURCE" ;;
    esac
}

source_fetch_issue() {
    local issue_num="$1"
    case "$SOURCE" in
        github) github_fetch_issue "$issue_num" ;;
        gitlab) gitlab_fetch_issue "$issue_num" ;;
        bitbucket) bitbucket_fetch_issue "$issue_num" ;;
        *) die "Unknown source: $SOURCE" ;;
    esac
}

source_list_issues() {
    case "$SOURCE" in
        github) github_list_issues ;;
        gitlab) gitlab_list_issues ;;
        bitbucket) bitbucket_list_issues ;;
        *) die "Unknown source: $SOURCE" ;;
    esac
}

source_map_labels() {
    local labels_json="$1"
    case "$SOURCE" in
        github) github_map_labels "$labels_json" ;;
        gitlab) gitlab_map_labels "$labels_json" ;;
        bitbucket) bitbucket_map_labels "$labels_json" ;;
        *) die "Unknown source: $SOURCE" ;;
    esac
}

source_detect_type() {
    local labels_json="$1"
    case "$SOURCE" in
        github) github_detect_type "$labels_json" ;;
        gitlab) gitlab_detect_type "$labels_json" ;;
        bitbucket) bitbucket_detect_type "$labels_json" ;;
        *) die "Unknown source: $SOURCE" ;;
    esac
}

source_preview_issue() {
    local issue_num="$1"
    case "$SOURCE" in
        github) github_preview_issue "$issue_num" ;;
        gitlab) gitlab_preview_issue "$issue_num" ;;
        bitbucket) bitbucket_preview_issue "$issue_num" ;;
        *) die "Unknown source: $SOURCE" ;;
    esac
}

source_format_comments() {
    local comments_json="$1"
    case "$SOURCE" in
        github) github_format_comments "$comments_json" ;;
        gitlab) gitlab_format_comments "$comments_json" ;;
        bitbucket) bitbucket_format_comments "$comments_json" ;;
        *) die "Unknown source: $SOURCE" ;;
    esac
}

# --- Duplicate Detection ---

check_duplicate_import() {
    local issue_num="$1"
    local found=""
    # Search active tasks
    found=$(grep -rl "^issue:.*/$issue_num$" "$TASK_DIR"/ 2>/dev/null | head -1)
    if [[ -z "$found" ]]; then
        # Search archived tasks
        found=$(grep -rl "^issue:.*/$issue_num$" "$ARCHIVED_DIR"/ 2>/dev/null | head -1)
    fi
    echo "$found"
}

# --- Core Import Function ---

import_single_issue() {
    local issue_num="$1"

    # Check for duplicate
    local existing
    existing=$(check_duplicate_import "$issue_num")
    if [[ -n "$existing" ]]; then
        if [[ "$BATCH_SKIP_DUPLICATES" == true ]]; then
            [[ "$BATCH_SILENT" == true ]] || warn "Issue #$issue_num already imported as: $existing (skipping)"
            return 0
        else
            warn "Issue #$issue_num already imported as: $existing"
        fi
    fi

    # Fetch issue data
    local issue_json
    issue_json=$(source_fetch_issue "$issue_num") || die "Failed to fetch issue #$issue_num"

    local title body url labels_json comments_json issue_created issue_updated
    title=$(echo "$issue_json" | jq -r '.title')
    body=$(echo "$issue_json" | jq -r '.body // ""')
    url=$(echo "$issue_json" | jq -r '.url')
    labels_json=$(echo "$issue_json" | jq -c '.labels')
    comments_json=$(echo "$issue_json" | jq -c '.comments // []')
    issue_created=$(echo "$issue_json" | jq -r '.createdAt // ""')
    issue_updated=$(echo "$issue_json" | jq -r '.updatedAt // ""')

    local task_name aitask_labels issue_type
    task_name=$(sanitize_name "$title")
    [[ -z "$task_name" ]] && task_name="issue_${issue_num}"

    # Use overrides if provided, otherwise derive from issue
    if [[ -n "$BATCH_LABELS" ]]; then
        aitask_labels="$BATCH_LABELS"
    else
        aitask_labels=$(source_map_labels "$labels_json")
    fi

    if [[ -n "$BATCH_TYPE" ]]; then
        issue_type="$BATCH_TYPE"
    else
        issue_type=$(source_detect_type "$labels_json")
    fi

    # Build description with issue timestamps
    local ts_line=""
    if [[ -n "$issue_created" ]]; then
        ts_line="Issue created: $(utc_to_local "$issue_created")"
        if [[ -n "$issue_updated" && "$issue_updated" != "$issue_created" ]]; then
            ts_line="${ts_line}, last updated: $(utc_to_local "$issue_updated")"
        fi
    fi
    local description
    if [[ -n "$ts_line" ]]; then
        description=$(printf "%s\n\n## %s\n\n%s" "$ts_line" "$title" "$body")
    else
        description=$(printf "## %s\n\n%s" "$title" "$body")
    fi

    # Append comments if not disabled
    if [[ "$BATCH_NO_COMMENTS" != true ]]; then
        local comments_text
        comments_text=$(source_format_comments "$comments_json")
        if [[ -n "$comments_text" ]]; then
            description="${description}${comments_text}"
        fi
    fi

    # Build aitask_create.sh arguments
    local create_args=(--batch --name "$task_name"
        --desc-file -
        --priority "$BATCH_PRIORITY" --effort "$BATCH_EFFORT"
        --type "$issue_type" --status "$BATCH_STATUS"
        --issue "$url")

    [[ -n "$aitask_labels" ]] && create_args+=(--labels "$aitask_labels")
    [[ -n "$BATCH_DEPS" ]] && create_args+=(--deps "$BATCH_DEPS")
    [[ -n "$BATCH_PARENT" ]] && create_args+=(--parent "$BATCH_PARENT")
    [[ "$BATCH_NO_SIBLING_DEP" == true ]] && create_args+=(--no-sibling-dep)
    [[ "$BATCH_COMMIT" == true ]] && create_args+=(--commit)
    [[ "$BATCH_SILENT" == true ]] && create_args+=(--silent)

    echo "$description" | "$SCRIPT_DIR/aitask_create.sh" "${create_args[@]}"
}

# --- Batch Mode ---

run_batch_mode() {
    source_check_cli

    if [[ "$BATCH_ALL" == true ]]; then
        local issues
        issues=$(source_list_issues | jq -r '.[].number' | sort -n)
        if [[ -z "$issues" ]]; then
            info "No open issues found."
            return 0
        fi
        local count=0
        while IFS= read -r num; do
            [[ -z "$num" ]] && continue
            import_single_issue "$num"
            count=$((count + 1))
        done <<< "$issues"
        [[ "$BATCH_SILENT" == true ]] || success "Imported $count issue(s)."
    elif [[ -n "$BATCH_ISSUE_RANGE" ]]; then
        local start end
        IFS='-' read -r start end <<< "$BATCH_ISSUE_RANGE"
        [[ -z "$start" || -z "$end" ]] && die "Invalid range format. Use: START-END (e.g., 5-10)"
        [[ "$start" -gt "$end" ]] && die "Invalid range: start ($start) > end ($end)"
        local count=0
        for ((num=start; num<=end; num++)); do
            import_single_issue "$num"
            count=$((count + 1))
        done
        [[ "$BATCH_SILENT" == true ]] || success "Imported $count issue(s)."
    elif [[ -n "$BATCH_ISSUE_NUM" ]]; then
        import_single_issue "$BATCH_ISSUE_NUM"
    else
        die "Batch mode requires --issue, --range, or --all"
    fi
}

# --- Interactive Mode ---

interactive_import_issue() {
    local issue_num="$1"

    # Check for duplicate
    local existing
    existing=$(check_duplicate_import "$issue_num")
    if [[ -n "$existing" ]]; then
        warn "Issue #$issue_num already imported as: $(basename "$existing")"
        local skip
        skip=$(printf "Skip\nImport anyway" | fzf --prompt="Already imported: " --height=8 --no-info)
        [[ "$skip" == "Skip" || -z "$skip" ]] && return 0
    fi

    # Fetch full issue data
    info "Fetching issue #$issue_num..."
    local issue_json
    issue_json=$(source_fetch_issue "$issue_num") || die "Failed to fetch issue #$issue_num"

    local title body url labels_json comments_json issue_created issue_updated
    title=$(echo "$issue_json" | jq -r '.title')
    body=$(echo "$issue_json" | jq -r '.body // ""')
    url=$(echo "$issue_json" | jq -r '.url')
    labels_json=$(echo "$issue_json" | jq -c '.labels')
    comments_json=$(echo "$issue_json" | jq -c '.comments // []')
    issue_created=$(echo "$issue_json" | jq -r '.createdAt // ""')
    issue_updated=$(echo "$issue_json" | jq -r '.updatedAt // ""')

    # Show preview
    echo ""
    echo -e "${BLUE}━━━ Issue #$issue_num: $title ━━━${NC}"
    echo ""
    echo "$body" | head -30
    local body_lines
    body_lines=$(echo "$body" | wc -l)
    if [[ "$body_lines" -gt 30 ]]; then
        warn "(truncated -- full text will be in task file)"
    fi
    echo ""

    # Confirm import
    local confirm
    confirm=$(printf "Import\nSkip" | fzf --prompt="Import this issue? " --height=8 --no-info)
    [[ "$confirm" == "Import" ]] || return 0

    # Task name: auto-generate, let user edit
    local auto_name
    auto_name=$(sanitize_name "$title")
    read -erp "Task name [$auto_name]: " user_name < /dev/tty
    local task_name="${user_name:-$auto_name}"
    task_name=$(sanitize_name "$task_name")

    # Labels: interactive selection
    # Disable exit-on-error for fzf operations
    set +e

    local selected_labels=()

    # Step 1: Review issue labels - ask user about each one
    local auto_labels
    auto_labels=$(source_map_labels "$labels_json")
    if [[ -n "$auto_labels" ]]; then
        info "Issue labels from GitHub:"
        IFS=',' read -ra issue_label_arr <<< "$auto_labels"
        for lbl in "${issue_label_arr[@]}"; do
            lbl=$(echo "$lbl" | xargs)  # trim whitespace
            [[ -z "$lbl" ]] && continue
            local keep
            keep=$(printf "Yes\nNo" | fzf --prompt="Keep label '$lbl'? " --height=8 --no-info)
            if [[ "$keep" == "Yes" ]]; then
                selected_labels+=("$lbl")
                success "  Kept: $lbl"
            fi
        done
        if [[ ${#selected_labels[@]} -eq 0 ]]; then
            warn "No labels kept!"
        fi
    fi

    # Step 2: Add more labels (loop like aitask_create.sh)
    while true; do
        local existing_labels
        existing_labels=$(get_existing_labels)

        local available_labels=""
        if [[ -n "$existing_labels" ]]; then
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

        local selected
        selected=$(printf "%s" "$options" | fzf --prompt="Select label: " --height=15 --no-info --header="Add more labels or finish")

        if [[ -z "$selected" || "$selected" == ">> Done adding labels" ]]; then
            break
        elif [[ "$selected" == ">> Add new label" ]]; then
            local new_label
            read -erp "Enter new label: " new_label < /dev/tty
            if [[ -n "$new_label" ]]; then
                local label
                label=$(echo "$new_label" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9_-]//g') || true
                if [[ -n "$label" ]]; then
                    ensure_labels_file
                    if ! grep -qFx "$label" "$LABELS_FILE" 2>/dev/null; then
                        echo "$label" >> "$LABELS_FILE"
                        sort -u "$LABELS_FILE" -o "$LABELS_FILE"
                    fi
                    selected_labels+=("$label")
                    success "  Added: $label"
                fi
            fi
        else
            selected_labels+=("$selected")
            success "  Added: $selected"
        fi

        if [[ ${#selected_labels[@]} -gt 0 ]]; then
            info "Current labels: ${selected_labels[*]}"
        fi

        local continue_choice
        continue_choice=$(printf "Add another label\nDone with labels" | fzf --prompt="Continue? " --height=8 --no-info)
        if [[ "$continue_choice" == "Done with labels" || -z "$continue_choice" ]]; then
            break
        fi
    done

    local labels=""
    if [[ ${#selected_labels[@]} -gt 0 ]]; then
        local IFS=','
        labels="${selected_labels[*]}"
    fi

    set -e

    # Priority selection
    local priority
    priority=$(printf "medium\nhigh\nlow" | fzf --prompt="Priority: " --height=10 --no-info --header="Select priority")
    priority="${priority:-medium}"

    # Effort selection
    local effort
    effort=$(printf "medium\nlow\nhigh" | fzf --prompt="Effort: " --height=10 --no-info --header="Select effort")
    effort="${effort:-medium}"

    # Auto-detect issue type from labels
    local issue_type
    issue_type=$(source_detect_type "$labels_json")

    # Build description with issue timestamps
    local ts_line=""
    if [[ -n "$issue_created" ]]; then
        ts_line="Issue created: $(utc_to_local "$issue_created")"
        if [[ -n "$issue_updated" && "$issue_updated" != "$issue_created" ]]; then
            ts_line="${ts_line}, last updated: $(utc_to_local "$issue_updated")"
        fi
    fi
    local description
    if [[ -n "$ts_line" ]]; then
        description=$(printf "%s\n\n## %s\n\n%s" "$ts_line" "$title" "$body")
    else
        description=$(printf "## %s\n\n%s" "$title" "$body")
    fi

    # Append comments
    local comments_text
    comments_text=$(source_format_comments "$comments_json")
    if [[ -n "$comments_text" ]]; then
        description="${description}${comments_text}"
    fi

    local create_args=(--batch --name "$task_name"
        --desc-file -
        --priority "$priority" --effort "$effort"
        --type "$issue_type" --status "Ready"
        --issue "$url")

    [[ -n "$labels" ]] && create_args+=(--labels "$labels")

    local result
    result=$(echo "$description" | "$SCRIPT_DIR/aitask_create.sh" "${create_args[@]}")
    success "Created: $result"

    # Git commit (like aitask_create.sh interactive mode)
    local created_file
    created_file=$(echo "$result" | sed 's/^Created: //')
    read -rp "Commit to git? [Y/n] " commit_choice < /dev/tty
    if [[ "$commit_choice" != "n" && "$commit_choice" != "N" ]]; then
        local task_id
        task_id=$(basename "$created_file" .md | grep -oE '^t[0-9]+')
        local humanized_name
        humanized_name=$(echo "$task_name" | tr '_' ' ')
        git add "$created_file"
        git commit -m "ait: Add task ${task_id}: ${humanized_name}"
        local commit_hash
        commit_hash=$(git rev-parse --short HEAD)
        success "Committed: $commit_hash"
    fi
}

interactive_specific_issue() {
    local issue_num
    read -rp "Enter issue number: " issue_num < /dev/tty
    [[ -z "$issue_num" ]] && die "No issue number entered"
    [[ "$issue_num" =~ ^[0-9]+$ ]] || die "Invalid issue number: $issue_num"
    interactive_import_issue "$issue_num"
}

interactive_fetch_and_choose() {
    info "Fetching open issues..."
    local issues_json
    issues_json=$(source_list_issues)

    local issue_count
    issue_count=$(echo "$issues_json" | jq length)
    [[ "$issue_count" -eq 0 ]] && die "No open issues found"

    # Format for fzf: "#NUM - TITLE [labels]"
    local issue_list
    issue_list=$(echo "$issues_json" | jq -r '.[] | "#\(.number) - \(.title) [\(.labels | map(.name) | join(", "))]"')

    # fzf with multi-select and preview
    local selected
    selected=$(echo "$issue_list" | fzf --multi --prompt="Select issues: " --height=20 --no-info \
        --header="Tab to select multiple, Enter to confirm" \
        --preview="echo {} | grep -oE '^#[0-9]+' | tr -d '#' | xargs -I{} gh issue view {} --comments=false" \
        --preview-window=right:50%:wrap)

    [[ -z "$selected" ]] && die "No issues selected"

    while IFS= read -r line; do
        local num
        num=$(echo "$line" | grep -oE '^#[0-9]+' | tr -d '#')
        [[ -n "$num" ]] && interactive_import_issue "$num"
    done <<< "$selected"
}

interactive_range() {
    local start end
    read -rp "Start issue number: " start < /dev/tty
    read -rp "End issue number: " end < /dev/tty
    [[ -z "$start" || -z "$end" ]] && die "Both start and end are required"
    [[ "$start" =~ ^[0-9]+$ && "$end" =~ ^[0-9]+$ ]] || die "Invalid numbers"
    [[ "$start" -gt "$end" ]] && die "Invalid range: start ($start) > end ($end)"

    info "Importing issues #$start to #$end..."
    for ((num=start; num<=end; num++)); do
        interactive_import_issue "$num"
    done
}

interactive_all_open() {
    info "Fetching all open issues..."
    local issues_json
    issues_json=$(source_list_issues)
    local count
    count=$(echo "$issues_json" | jq length)

    [[ "$count" -eq 0 ]] && die "No open issues found"

    local confirm
    confirm=$(printf "Yes - import $count issues\nNo - cancel" | fzf --prompt="Confirm? " --height=8 --no-info)
    [[ "$confirm" == "Yes"* ]] || die "Cancelled"

    echo "$issues_json" | jq -r '.[].number' | sort -n | while IFS= read -r num; do
        [[ -z "$num" ]] && continue
        interactive_import_issue "$num"
    done
}

run_interactive_mode() {
    # Check terminal capabilities (warn on incapable terminals)
    ait_warn_if_incapable_terminal

    command -v fzf &>/dev/null || die "fzf is required for interactive mode. Install via your package manager."
    source_check_cli

    local mode
    mode=$(printf "Specific issue number\nFetch open issues and choose\nIssue number range\nAll open issues" | \
        fzf --prompt="Import mode: " --height=10 --no-info --header="Select import mode")

    case "$mode" in
        "Specific issue number") interactive_specific_issue ;;
        "Fetch open issues and choose") interactive_fetch_and_choose ;;
        "Issue number range") interactive_range ;;
        "All open issues") interactive_all_open ;;
        *) die "No mode selected" ;;
    esac
}

# --- Argument Parsing ---

show_help() {
    cat << 'EOF'
Usage: aitask_issue_import.sh [--batch OPTIONS]

Import GitHub issues as AI task files.

Modes:
  Without --batch:  Interactive mode (uses fzf for selection and editing)
  With --batch:     Batch mode (non-interactive, all options via flags)

Interactive mode (no arguments):
  ./aitask_issue_import.sh
  Presents a menu to choose: specific issue, fetch & choose, range, or all.
  Each issue can be previewed, and metadata (name, labels, priority, effort)
  can be edited before import.

Batch mode required flags (one of):
  --issue, -i NUM          Import a specific issue number
  --range START-END        Import issues in a number range (e.g., 5-10)
  --all                    Import all open issues

Batch mode options:
  --batch                  Enable batch mode (required for non-interactive)
  --source, -S PLATFORM    Source platform: github, gitlab, bitbucket (auto-detected from git remote)
  --priority, -p LEVEL     Override priority: high, medium (default), low
  --effort, -e LEVEL       Override effort: low, medium (default), high
  --type, -t TYPE          Override issue type (see aitasks/metadata/task_types.txt, default: auto-detect)
  --status, -s STATUS      Override status (default: Ready)
  --labels, -l LABELS      Override labels (default: from issue labels)
  --deps DEPS              Set dependencies (comma-separated task numbers)
  --parent, -P NUM         Create as child of parent task
  --no-sibling-dep         Don't add dependency on previous sibling
  --commit                 Auto git commit after creation
  --silent                 Output only created filename(s)
  --skip-duplicates        Skip already-imported issues silently
  --no-comments            Don't include issue comments in task description
  --help, -h               Show this help

Examples:
  # Interactive mode
  ./aitask_issue_import.sh

  # Import a single issue (batch)
  ./aitask_issue_import.sh --batch --issue 42

  # Import a range of issues with high priority
  ./aitask_issue_import.sh --batch --range 1-10 --priority high

  # Import all open issues, skip duplicates
  ./aitask_issue_import.sh --batch --all --skip-duplicates

  # Import as child tasks of parent t53
  ./aitask_issue_import.sh --batch --all --parent 53 --skip-duplicates
EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --batch) BATCH_MODE=true; shift ;;
            --source|-S) SOURCE="$2"; shift 2 ;;
            --issue|-i) BATCH_ISSUE_NUM="$2"; shift 2 ;;
            --range) BATCH_ISSUE_RANGE="$2"; shift 2 ;;
            --all) BATCH_ALL=true; shift ;;
            --priority|-p) BATCH_PRIORITY="$2"; shift 2 ;;
            --effort|-e) BATCH_EFFORT="$2"; shift 2 ;;
            --type|-t) BATCH_TYPE="$2"; shift 2 ;;
            --status|-s) BATCH_STATUS="$2"; shift 2 ;;
            --labels|-l) BATCH_LABELS="$2"; shift 2 ;;
            --deps) BATCH_DEPS="$2"; shift 2 ;;
            --parent|-P) BATCH_PARENT="$2"; shift 2 ;;
            --no-sibling-dep) BATCH_NO_SIBLING_DEP=true; shift ;;
            --commit) BATCH_COMMIT=true; shift ;;
            --silent) BATCH_SILENT=true; shift ;;
            --skip-duplicates) BATCH_SKIP_DUPLICATES=true; shift ;;
            --no-comments) BATCH_NO_COMMENTS=true; shift ;;
            --help|-h) show_help; exit 0 ;;
            *) die "Unknown option: $1. Use --help for usage." ;;
        esac
    done

    # Auto-detect source platform if not explicitly set
    if [[ -z "$SOURCE" ]]; then
        SOURCE=$(detect_platform)
        if [[ -z "$SOURCE" ]]; then
            die "Could not auto-detect source platform from git remote. Use --source github|gitlab|bitbucket"
        fi
    fi

    # Validate source platform
    case "$SOURCE" in
        github) ;;
        gitlab) ;;
        bitbucket) ;;
        *) die "Unknown source platform: $SOURCE (supported: github, gitlab, bitbucket)" ;;
    esac
}

# --- Main ---

main() {
    parse_args "$@"

    if [[ "$BATCH_MODE" == true ]]; then
        run_batch_mode
    else
        run_interactive_mode
    fi
}

main "$@"
