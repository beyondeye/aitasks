---
Task: t277_1_fix_glab_api_jq_bug_and_add_repo_flag_to_pr_import.md
Parent Task: aitasks/t277_test_pull_request_import_for_gitlab.md
Sibling Tasks: aitasks/t277/t277_2_*.md, aitasks/t277/t277_3_*.md
Worktree: (none — working on current branch)
Branch: (current)
Base branch: main
---

# Plan: Fix glab API --jq bug and add --repo flag to aitask_pr_import.sh

## Context

The GitLab backend in `aitask_pr_import.sh` has two bugs preventing cross-repo imports:
1. `glab api --jq` flag doesn't exist — silently fails
2. All `glab` commands need repo context that doesn't exist when run from a non-GitLab directory

## Steps

### Step 1: Add REPO_OVERRIDE variable and --repo flag

In `aiscripts/aitask_pr_import.sh`:

- Add `REPO_OVERRIDE=""` near line 21 (alongside SOURCE)
- Add `--repo` case to `parse_args()` around line 1382
- Add `--repo` to `show_help()` around line 1338

### Step 2: Create helper functions

Add two helper functions in the GitLab backend section (after line 203):

```bash
# Get -R flag arguments for glab mr commands when REPO_OVERRIDE is set
# Usage: glab mr view "$mr_num" $(glab_repo_args) -F json
glab_repo_args() {
    if [[ -n "$REPO_OVERRIDE" ]]; then
        echo "-R $REPO_OVERRIDE"
    fi
}

# Get project path for glab api commands
# Returns URL-encoded REPO_OVERRIDE or :fullpath for auto-detection
glab_api_project_path() {
    if [[ -n "$REPO_OVERRIDE" ]]; then
        echo "${REPO_OVERRIDE//\//%2F}"
    else
        echo ":fullpath"
    fi
}
```

### Step 3: Update gitlab_fetch_pr()

Line 211: `glab mr view "$mr_num" -F json` → `glab mr view "$mr_num" $(glab_repo_args) -F json`
Line 212: Replace `:fullpath` with `$(glab_api_project_path)`

### Step 4: Fix gitlab_fetch_pr_files() — the --jq bug

Line 243: Replace `--jq '...'` with `| jq -r '...'`:

```bash
gitlab_fetch_pr_files() {
    local mr_num="$1"
    local project_path
    project_path=$(glab_api_project_path)
    glab api "projects/$project_path/merge_requests/$mr_num/changes" 2>/dev/null | jq -r '.changes[] | "\(.new_path)\t+\(.diff | split("\n") | map(select(startswith("+"))) | length)\t-\(.diff | split("\n") | map(select(startswith("-"))) | length)"' 2>/dev/null || echo ""
}
```

### Step 5: Update remaining GitLab backend functions

- `gitlab_fetch_pr_diff()`: add `$(glab_repo_args)` to `glab mr diff`
- `gitlab_fetch_pr_reviews()`: replace `:fullpath` with `$(glab_api_project_path)`
- `gitlab_fetch_pr_review_comments()`: replace `:fullpath` with `$(glab_api_project_path)`
- `gitlab_list_prs()`: add `$(glab_repo_args)` to `glab mr list`
- `gitlab_preview_pr()`: add `$(glab_repo_args)` to `glab mr view`

Note: `gitlab_resolve_contributor_email()` uses `glab api "users?username=..."` which is a global API endpoint (not project-scoped), so it doesn't need `:fullpath` replacement.

### Step 6: Add additions/deletions TODO comment

Add a comment at lines 230-231 documenting the known limitation:
```bash
# TODO: GitLab API doesn't provide total additions/deletions directly.
# Per-file counts are computed in gitlab_fetch_pr_files().
additions: 0,
deletions: 0,
```

## Step 9: Post-Implementation

Archive task, update linked issues/PRs, push changes.

## Verification

```bash
# Quick syntax check:
bash -n aiscripts/aitask_pr_import.sh

# Verify --repo flag is parsed:
./aiscripts/aitask_pr_import.sh --help 2>&1 | grep -q 'repo'

# Test list mode against real GitLab repo (requires test MR from t277_3):
./aiscripts/aitask_pr_import.sh --batch --source gitlab --repo beyondeye/testrepo_gitlab --list --silent
```

## Final Implementation Notes

- **Actual work done:** All 6 steps implemented as planned, plus one additional fix: `gitlab_resolve_contributor_email()` at line 291 also used the invalid `--jq` flag — fixed by piping to `jq -r` instead. Total: 32 insertions, 9 deletions in a single file.
- **Deviations from plan:** (1) Added fix for `--jq` in `gitlab_resolve_contributor_email()` which the original plan missed. (2) Moved the TODO comment for additions/deletions above the jq call instead of inline, because bash interprets parentheses inside jq heredoc strings.
- **Issues encountered:** Placing a `# TODO` comment with parentheses inside a jq expression caused a bash syntax error — the `()` in `gitlab_fetch_pr_files()` was interpreted as a subshell. Resolved by moving the comment above the jq call.
- **Notes for sibling tasks:** The `glab_repo_args()` and `glab_api_project_path()` helper functions are now available in the GitLab backend section (lines 206-222). t277_2 should follow the same pattern: extract repo slug from the PR/issue URL and pass it via `-R` to `glab mr`/`glab issue` commands. For `glab api` calls, URL-encode the slash in the repo path (`group%2Fproject`). The `--jq` flag is NOT valid for `glab api` — always pipe to `jq` instead.
