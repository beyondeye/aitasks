---
priority: medium
effort: high
depends: [t53_3]
issue_type: feature
status: Done
labels: [scripting, aitasks]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-10 16:18
updated_at: 2026-02-10 19:13
completed_at: 2026-02-10 19:13
---

## Context

This is child task 4 of t53 (import GitHub issues as tasks). This task adds the interactive mode to the `aitask_import.sh` script created in t53_3. The interactive mode uses fzf for user interaction and has 4 sub-modes for selecting which issues to import.

Depends on t53_3 which creates the script with batch mode infrastructure (platform abstraction, core import function, duplicate detection).

## Key Files to Modify

1. **`aitask_import.sh`** - Add `run_interactive_mode()` and sub-mode functions

## Reference Files for Patterns

- `aitask_import.sh` (created by t53_3) - The batch mode infrastructure to build upon
- `aitask_create.sh` - Interactive mode patterns: fzf usage, menu prompts, user input handling
- `aitask_update.sh` - Additional fzf interaction patterns

## Implementation Plan

### Step 1: Interactive mode entry point

Add `run_interactive_mode()` function that checks for `fzf` dependency and presents the 4 sub-mode menu:

```bash
run_interactive_mode() {
    command -v fzf &>/dev/null || die "fzf is required for interactive mode"
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
```

### Step 2: Specific issue number sub-mode

```bash
interactive_specific_issue() {
    local issue_num
    read -rp "Enter issue number: " issue_num
    [[ -z "$issue_num" ]] && die "No issue number entered"
    [[ "$issue_num" =~ ^[0-9]+$ ]] || die "Invalid issue number: $issue_num"
    interactive_import_issue "$issue_num"
}
```

### Step 3: Fetch and choose sub-mode (most complex)

```bash
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
```

### Step 4: Range and all-issues sub-modes

```bash
interactive_range() {
    local start end
    read -rp "Start issue number: " start
    read -rp "End issue number: " end
    [[ -z "$start" || -z "$end" ]] && die "Both start and end are required"
    [[ "$start" =~ ^[0-9]+$ && "$end" =~ ^[0-9]+$ ]] || die "Invalid numbers"
    
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
    
    local confirm
    confirm=$(printf "Yes - import $count issues\nNo - cancel" | fzf --prompt="Confirm? " --height=8)
    [[ "$confirm" == "Yes"* ]] || die "Cancelled"
    
    echo "$issues_json" | jq -r '.[].number' | sort -n | while IFS= read -r num; do
        [[ -z "$num" ]] && continue
        interactive_import_issue "$num"
    done
}
```

### Step 5: Core interactive import function

This is the shared function used by all sub-modes. It adds user interaction on top of the batch mode `import_single_issue()`:

```bash
interactive_import_issue() {
    local issue_num="$1"
    
    # Check for duplicate
    local existing
    existing=$(check_duplicate_import "$issue_num")
    if [[ -n "$existing" ]]; then
        warn "Issue #$issue_num already imported as: $(basename "$existing")"
        local skip
        skip=$(printf "Skip\nImport anyway" | fzf --prompt="Already imported: " --height=8)
        [[ "$skip" == "Skip" ]] && return 0
    fi
    
    # Fetch full issue data
    info "Fetching issue #$issue_num..."
    local issue_json
    issue_json=$(source_fetch_issue "$issue_num") || die "Failed to fetch issue #$issue_num"
    
    local title body url labels_json
    title=$(echo "$issue_json" | jq -r '.title')
    body=$(echo "$issue_json" | jq -r '.body // ""')
    url=$(echo "$issue_json" | jq -r '.url')
    labels_json=$(echo "$issue_json" | jq '.labels')
    
    # Show preview
    echo ""
    echo "━━━ Issue #$issue_num: $title ━━━"
    echo ""
    echo "$body" | head -30
    if [[ $(echo "$body" | wc -l) -gt 30 ]]; then
        warn "(truncated -- full text will be in task file)"
    fi
    echo ""
    
    # Confirm import
    local confirm
    confirm=$(printf "Import\nSkip" | fzf --prompt="Import this issue? " --height=8)
    [[ "$confirm" == "Import" ]] || return 0
    
    # Task name: auto-generate, let user edit
    local auto_name
    auto_name=$(sanitize_name "$title")
    read -erp "Task name [$auto_name]: " user_name
    local task_name="${user_name:-$auto_name}"
    task_name=$(sanitize_name "$task_name")
    
    # Labels: auto-sync from issue, let user edit
    local auto_labels
    auto_labels=$(source_map_labels "$labels_json")
    local labels="$auto_labels"
    
    if [[ -n "$auto_labels" ]]; then
        local edit_labels
        edit_labels=$(printf "Use labels: $auto_labels\nEdit labels\nClear labels" | \
            fzf --prompt="Labels: " --height=8)
        case "$edit_labels" in
            "Edit labels")
                read -erp "Labels (comma-separated) [$auto_labels]: " user_labels
                labels="${user_labels:-$auto_labels}"
                ;;
            "Clear labels") labels="" ;;
        esac
    fi
    
    # Priority and effort selection
    local priority
    priority=$(printf "medium\nhigh\nlow" | fzf --prompt="Priority: " --height=10 --no-info)
    priority="${priority:-medium}"
    
    local effort
    effort=$(printf "medium\nlow\nhigh" | fzf --prompt="Effort: " --height=10 --no-info)
    effort="${effort:-medium}"
    
    # Auto-detect issue type from labels
    local issue_type
    issue_type=$(source_detect_type "$labels_json")
    
    # Build description and create task
    local description
    description=$(printf "## %s\n\n%s" "$title" "$body")
    
    local create_args=(--batch --name "$task_name"
        --desc-file -
        --priority "$priority" --effort "$effort"
        --type "$issue_type" --status "Ready"
        --issue "$url")
    
    [[ -n "$labels" ]] && create_args+=(--labels "$labels")
    
    local result
    result=$(echo "$description" | ./aitask_create.sh "${create_args[@]}")
    success "Created: $result"
}
```

### Step 6: Update mode dispatch

Update the main script to dispatch to interactive or batch mode:

```bash
if [[ "$BATCH_MODE" == true ]]; then
    run_batch_mode
else
    run_interactive_mode
fi
```

## Verification Steps

1. Run interactive mode: `./aitask_import.sh`
2. Test "Specific issue number" - enter a known issue number
3. Test "Fetch open issues and choose" - verify fzf list and preview work
4. Test task name editing (accept default, then try custom name)
5. Test label editing (accept, edit, and clear)
6. Test duplicate detection (try importing same issue twice)
7. Test "Issue number range" with a small range
8. Test "All open issues" and verify confirmation prompt
9. Clean up test tasks
