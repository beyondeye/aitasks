---
priority: high
effort: high
depends: [t260_2]
issue_type: feature
status: Ready
labels: [bash_scripts, git-integration]
created_at: 2026-03-01 15:30
updated_at: 2026-03-01 15:30
---

## Context

This is child task 3 of the "Create aitasks from Pull Requests" feature (t260). This is the core data extraction component — a bash script that fetches pull request data from GitHub/GitLab/Bitbucket and either creates a task directly or writes structured intermediate data for the Claude Code skill to process.

**Why this task is needed:** The framework currently has `aitask_issue_import.sh` for importing issues but nothing for pull requests. PRs contain much richer data than issues (code diffs, review comments, file changes) that need to be extracted and structured for AI analysis.

**Depends on:** t260_1 (needs `--pull-request`, `--contributor`, `--contributor-email` flags on `aitask_create.sh`)

## Key Files to Create/Modify

1. **Create `aiscripts/aitask_pr_import.sh`** — New script (~800-1200 lines expected)
   - Follow the exact dispatcher architecture from `aitask_issue_import.sh`
   - Platform backends: `github_*()`, `gitlab_*()`, `bitbucket_*()` function sets
   - Source dispatchers: `source_fetch_pr()`, `source_list_prs()`, etc.

2. **Modify `ait`** (dispatcher script, ~200 lines)
   - Add `pr-import)` case in the command dispatcher (around line 123, near other command cases)
   - Add to `show_usage()` help text

3. **Modify `.gitignore`** (or `seed/.gitignore` template)
   - Add `.aitask-pr-data/` entry

## Reference Files for Patterns

- **`aiscripts/aitask_issue_import.sh`** (~950 lines) — PRIMARY REFERENCE. This script demonstrates:
  - Platform dispatcher pattern (`github_fetch_issue()`, `gitlab_fetch_issue()`, `bitbucket_fetch_issue()`)
  - Source dispatchers (`source_fetch_issue()`, `source_list_issues()`, etc.)
  - Interactive mode with fzf menu (specific item, fetch & choose, range, all)
  - Batch mode with CLI flags
  - Duplicate detection (`check_duplicate_import()`)
  - Comment formatting (`github_format_comments()`)
  - Task creation via piping to `aitask_create.sh --batch`
  - Label sanitization pipeline
  - Issue type auto-detection from labels

- **`aiscripts/aitask_issue_update.sh`** (~350 lines) — Shows platform detection from URL, CLI validation, API interaction patterns

- **`aiscripts/lib/task_utils.sh`** — `detect_platform()` function for auto-detecting GitHub/GitLab/Bitbucket from git remote URL

- **`aiscripts/lib/terminal_compat.sh`** — Shared utilities: `die()`, `warn()`, `info()`, `portable_date()`, `sed_inplace()`

## Implementation Plan

### Phase 1: Script skeleton and platform detection

1. Create `aiscripts/aitask_pr_import.sh` with shebang, `set -euo pipefail`, source libraries
2. Add `parse_args()` with all CLI flags
3. Add platform auto-detection (reuse `detect_platform()` from task_utils.sh)
4. Add CLI tool validation (`github_check_cli()`, etc. — same as issue import)

### Phase 2: Platform backends for PR data fetching

**GitHub backend:**
```bash
github_fetch_pr() {
    local pr_num="$1"
    gh pr view "$pr_num" --json title,body,author,labels,url,comments,createdAt,updatedAt,headRefName,baseRefName,state,additions,deletions,changedFiles
}
github_fetch_pr_diff() {
    local pr_num="$1"
    gh pr diff "$pr_num"
}
github_fetch_pr_reviews() {
    local pr_num="$1"
    gh api "repos/{owner}/{repo}/pulls/${pr_num}/reviews" 2>/dev/null || echo "[]"
}
github_fetch_pr_review_comments() {
    local pr_num="$1"
    gh api "repos/{owner}/{repo}/pulls/${pr_num}/comments" 2>/dev/null || echo "[]"
}
github_list_prs() {
    gh pr list --state open --limit 500 --json number,title,labels,url,author
}
github_extract_pr_author() {
    local pr_json="$1"
    echo "$pr_json" | jq -r '.author.login'
}
github_resolve_contributor_email() {
    local username="$1"
    local user_id
    user_id=$(gh api "users/${username}" --jq '.id' 2>/dev/null || echo "")
    if [[ -n "$user_id" ]]; then
        echo "${user_id}+${username}@users.noreply.github.com"
    else
        echo "${username}@users.noreply.github.com"
    fi
}
```

**GitLab backend:**
```bash
gitlab_fetch_pr() {
    local mr_num="$1"
    glab mr view "$mr_num" -F json
    # Normalize to GitHub-compatible structure with jq (same pattern as gitlab_fetch_issue)
}
gitlab_fetch_pr_diff() {
    local mr_num="$1"
    glab mr diff "$mr_num"
}
gitlab_fetch_pr_reviews() {
    local mr_num="$1"
    glab api "projects/:fullpath/merge_requests/${mr_num}/notes?sort=asc&per_page=100" 2>/dev/null || echo "[]"
}
gitlab_list_prs() {
    glab mr list --all --output json
}
gitlab_resolve_contributor_email() {
    local username="$1"
    local user_id
    user_id=$(glab api "users?username=${username}" --jq '.[0].id' 2>/dev/null || echo "")
    if [[ -n "$user_id" ]]; then
        echo "${user_id}+${username}@noreply.gitlab.com"
    else
        echo "${username}@noreply.gitlab.com"
    fi
}
```

**Bitbucket backend:**
```bash
bitbucket_fetch_pr() {
    local pr_num="$1"
    bkt pr view "$pr_num" --json
}
bitbucket_fetch_pr_diff() {
    local pr_num="$1"
    bkt pr diff "$pr_num"
}
bitbucket_list_prs() {
    bkt pr list --json
}
```

### Phase 3: Intermediate data file generation

Write extracted data to `.aitask-pr-data/<pr_num>.md`:

```markdown
---
pr_number: 42
pr_url: https://github.com/owner/repo/pull/42
contributor: octocat
contributor_email: 12345+octocat@users.noreply.github.com
platform: github
title: "Add dark mode support"
state: open
base_branch: main
head_branch: feature/dark-mode
additions: 150
deletions: 30
changed_files: 8
fetched_at: 2026-03-01 12:00
---

## Description

<PR body/description>

## Comments

<formatted comments — same format as issue import: **author** (timestamp) + body>

## Reviews

<review comments with review state: APPROVED, CHANGES_REQUESTED, COMMENTED>

## Inline Review Comments

<inline review comments with file path, line number, and comment body>

## Changed Files

<list of files with additions/deletions per file>

## Diff

<full diff content, truncated at 5000 lines with "[Diff truncated...]" warning>
```

### Phase 4: Task creation mode

When NOT using `--data-only`:
```bash
echo "$description" | "$SCRIPT_DIR/aitask_create.sh" --batch \
    --name "$task_name" --desc-file - \
    --priority "$priority" --effort "$effort" \
    --type "$issue_type" --status "Ready" \
    --pull-request "$pr_url" \
    --contributor "$pr_author" \
    --contributor-email "$contributor_email" \
    "${extra_args[@]}"
```

### Phase 5: Interactive and batch modes

**Interactive mode menu (fzf):**
1. Import specific PR (enter number)
2. Fetch open PRs and choose (multi-select with fzf preview)
3. Import PR range (e.g., 10-20)
4. Import all open PRs

**Batch mode flags:**
```
--batch              Enable batch mode
--pr NUM             PR/MR number to import
--range START-END    Range of PR numbers
--all                All open PRs
--data-only          Only write intermediate data file, don't create task
--priority P         Override priority (default: medium)
--effort E           Override effort (default: medium)
--type T             Override issue type
--labels L           Comma-separated labels
--status S           Override status (default: Ready)
--skip-duplicates    Silently skip already-imported PRs
--commit             Auto-commit to git
--silent             Output only filename
--source PLATFORM    Force platform (github|gitlab|bitbucket)
--max-diff-lines N   Truncate diff at N lines (default: 5000)
--no-diff            Skip diff extraction entirely
--no-reviews         Skip review comment extraction
```

### Phase 6: Duplicate detection

```bash
check_duplicate_pr_import() {
    local pr_num="$1"
    local url_pattern="$2"  # e.g., /pull/42 or /merge_requests/42
    grep -rl "^pull_request:.*${url_pattern}$" "$TASK_DIR"/ "$ARCHIVED_DIR"/ 2>/dev/null
}
```

### Phase 7: Register in ait dispatcher

In the `ait` script, add:
```bash
pr-import)  shift; exec "$SCRIPTS_DIR/aitask_pr_import.sh" "$@" ;;
```

## Verification Steps

1. **Unit test with GitHub PR:**
   ```bash
   # Data-only mode (writes intermediate file)
   ./ait pr-import --batch --pr 1 --data-only
   cat .aitask-pr-data/1.md  # Verify structure
   
   # Full import (creates task)
   ./ait pr-import --batch --pr 1 --commit
   ./ait ls -v  # Verify task with PR metadata
   ```

2. **Test duplicate detection:**
   ```bash
   ./ait pr-import --batch --pr 1 --commit  # Should warn about duplicate
   ./ait pr-import --batch --pr 1 --skip-duplicates --commit  # Should skip silently
   ```

3. **Test interactive mode:**
   ```bash
   ./ait pr-import  # Should show fzf menu
   ```

4. **Run shellcheck:**
   ```bash
   shellcheck aiscripts/aitask_pr_import.sh
   ```

5. **Verify .gitignore update:**
   ```bash
   git check-ignore .aitask-pr-data/test.md  # Should be ignored
   ```
