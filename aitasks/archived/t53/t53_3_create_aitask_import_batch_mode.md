---
priority: high
effort: high
depends: [t53_1]
issue_type: feature
status: Done
labels: [scripting, aitasks]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-10 16:17
updated_at: 2026-02-10 17:56
completed_at: 2026-02-10 17:56
---

## Context

This is child task 3 of t53 (import GitHub issues as tasks). This task creates the new `aitask_import.sh` script with batch mode functionality. The script uses the `gh` CLI to fetch GitHub issue data and calls `aitask_create.sh` to create task files. It depends on t53_1 which adds the `--issue` flag to `aitask_create.sh`.

The script is designed with platform abstraction from the start so that GitLab/Bitbucket support can be added later. All platform-specific code is isolated in clearly marked functions with `# PLATFORM-EXTENSION-POINT` comments.

## Key Files to Modify

1. **`aitask_import.sh`** (NEW) - Main import script

## Reference Files for Patterns

- `aitask_create.sh` - Follow its structure for: argument parsing, batch mode flow, color/helper functions (`die`, `info`, `success`, `warn`), name sanitization
- `aitask_update.sh` - For additional pattern reference on batch mode argument handling

## Implementation Plan

### Step 1: Script skeleton

Create `aitask_import.sh` with:
- Shebang, `set -e`
- Color definitions and helper functions (copy from `aitask_create.sh`): `die()`, `info()`, `success()`, `warn()`
- Name sanitization function `sanitize_name()` (copy from `aitask_create.sh`)
- Global variables
- Argument parsing function
- Mode dispatch (batch vs interactive placeholder)

### Step 2: Platform abstraction layer

Implement the dispatcher pattern with clearly marked extension points:

```bash
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
}

# Returns JSON: {"title":"...", "body":"...", "labels":[{"name":"..."}], "url":"..."}
github_fetch_issue() {
    local issue_num="$1"
    gh issue view "$issue_num" --json title,body,labels,url
}

# Returns JSON array: [{"number":N, "title":"...", "labels":[{"name":"..."}], "url":"..."}]
github_list_issues() {
    gh issue list --state open --limit 100 --json number,title,labels,url
}

# Input: JSON labels array [{"name":"..."}]. Output: comma-separated lowercase sanitized labels
github_map_labels() {
    local labels_json="$1"
    echo "$labels_json" | jq -r '.[].name' | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9_-]//g' | paste -sd ','
}

# Input: JSON labels array. Output: "bug" or "feature"
github_detect_type() {
    local labels_json="$1"
    if echo "$labels_json" | jq -r '.[].name' | grep -qi "^bug$"; then
        echo "bug"
    else
        echo "feature"
    fi
}

# Prints issue preview to stdout for user confirmation
github_preview_issue() {
    local issue_num="$1"
    gh issue view "$issue_num" --comments=false
}

# --- Dispatcher Functions ---
# PLATFORM-EXTENSION-POINT: Add new platform cases to each dispatcher

source_check_cli() {
    # Validates that the required CLI tool is installed for the selected platform
    case "$SOURCE" in
        github) github_check_cli ;;
        # gitlab) gitlab_check_cli ;;  # PLATFORM-EXTENSION-POINT
        *) die "Unknown source: $SOURCE" ;;
    esac
}

source_fetch_issue() {
    # Must return JSON: {"title":"...", "body":"...", "labels":[{"name":"..."}], "url":"..."}
    local issue_num="$1"
    case "$SOURCE" in
        github) github_fetch_issue "$issue_num" ;;
        *) die "Unknown source: $SOURCE" ;;
    esac
}
# (similar for source_list_issues, source_map_labels, source_detect_type, source_preview_issue)
```

### Step 3: Core import function

```bash
import_single_issue() {
    local issue_num="$1"
    
    # Check for duplicate
    local existing
    existing=$(check_duplicate_import "$issue_num")
    if [[ -n "$existing" ]]; then
        warn "Issue #$issue_num already imported as: $existing"
        [[ "$BATCH_SKIP_DUPLICATES" == true ]] && return 0
    fi
    
    # Fetch issue data
    local issue_json
    issue_json=$(source_fetch_issue "$issue_num") || die "Failed to fetch issue #$issue_num"
    
    local title body url labels_json
    title=$(echo "$issue_json" | jq -r '.title')
    body=$(echo "$issue_json" | jq -r '.body // ""')
    url=$(echo "$issue_json" | jq -r '.url')
    labels_json=$(echo "$issue_json" | jq '.labels')
    
    local task_name aitask_labels issue_type
    task_name=$(sanitize_name "$title")
    aitask_labels="${BATCH_LABELS:-$(source_map_labels "$labels_json")}"
    issue_type="${BATCH_TYPE:-$(source_detect_type "$labels_json")}"
    
    # Build description
    local description
    description=$(printf "## %s\n\n%s" "$title" "$body")
    
    # Create task via aitask_create.sh using --desc-file for large bodies
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
    
    echo "$description" | ./aitask_create.sh "${create_args[@]}"
}
```

### Step 4: Batch mode dispatch

```bash
run_batch_mode() {
    source_check_cli
    
    if [[ "$BATCH_ALL" == true ]]; then
        local issues
        issues=$(source_list_issues | jq -r '.[].number' | sort -n)
        while IFS= read -r num; do
            [[ -z "$num" ]] && continue
            import_single_issue "$num"
        done <<< "$issues"
    elif [[ -n "$BATCH_ISSUE_RANGE" ]]; then
        local start end
        IFS='-' read -r start end <<< "$BATCH_ISSUE_RANGE"
        for ((num=start; num<=end; num++)); do
            import_single_issue "$num"
        done
    elif [[ -n "$BATCH_ISSUE_NUM" ]]; then
        import_single_issue "$BATCH_ISSUE_NUM"
    else
        die "Batch mode requires --issue, --range, or --all"
    fi
}
```

### Step 5: CLI arguments

```
--batch                  Enable batch mode (required for non-interactive)
--source, -S PLATFORM    Source platform: github (default). PLATFORM-EXTENSION-POINT
--issue, -i NUM          Specific issue number to import
--range START-END        Import issues in number range (e.g., 5-10)
--all                    Import all open issues
--priority, -p LEVEL     Override priority (default: medium)
--effort, -e LEVEL       Override effort (default: medium)
--type, -t TYPE          Override issue type (default: auto-detect from labels)
--status, -s STATUS      Override status (default: Ready)
--labels, -l LABELS      Override labels (default: auto-sync from issue)
--deps DEPS              Set dependencies (comma-separated task numbers)
--parent, -P NUM         Create as child of parent task
--no-sibling-dep         Don't add dependency on previous sibling
--commit                 Auto git commit after creation
--silent                 Output only created filename(s)
--skip-duplicates        Skip already-imported issues silently
--help, -h               Show help
```

### Step 6: Duplicate detection

```bash
check_duplicate_import() {
    local issue_num="$1"
    # Search for any task with issue URL containing this issue number
    # Works across platforms since we store full URLs
    grep -rl "^issue:.*/$issue_num\$" aitasks/ 2>/dev/null | head -1
}
```

Note: For more robust detection, also search `aitasks/archived/` to detect re-imports of closed issues.

### Step 7: Make executable

```bash
chmod +x aitask_import.sh
```

## Verification Steps

1. Verify `gh` CLI is available and authenticated: `gh auth status`
2. Test single issue import:
   ```bash
   ./aitask_import.sh --batch --issue 1
   ```
3. Verify created task has correct title, description, labels, and `issue` URL
4. Test range import:
   ```bash
   ./aitask_import.sh --batch --range 1-3 --silent
   ```
5. Test duplicate detection (run same import again)
6. Test with overrides:
   ```bash
   ./aitask_import.sh --batch --issue 1 --priority high --labels "custom" --skip-duplicates
   ```
7. Test all-issues mode (use with caution):
   ```bash
   ./aitask_import.sh --batch --all --silent --skip-duplicates
   ```
8. Clean up test tasks
