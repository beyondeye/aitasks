---
priority: medium
effort: medium
depends: [t277_1]
issue_type: bug
status: Ready
labels: []
created_at: 2026-03-02 15:46
updated_at: 2026-03-02 15:46
---

## Context

When `aitask_pr_close.sh` and `aitask_issue_update.sh` run for GitLab tasks from a non-GitLab working directory (e.g., a project whose git remote is GitHub), the `glab` commands fail because they can't resolve the repo context. These scripts detect the platform from the PR/issue URL (correct), but don't pass `-R <repo>` to `glab` commands.

This is a sibling task to t277_1 which adds `--repo` support to `aitask_pr_import.sh`. This task applies the same pattern to the close/update scripts.

**Prerequisite:** t277_1 must be completed first to establish the helper pattern.

## Key Files to Modify

- `aiscripts/aitask_pr_close.sh` — GitLab functions (lines 79-120)
- `aiscripts/aitask_issue_update.sh` — GitLab functions (lines 78-118)

## Implementation Plan

### 1. `aitask_pr_close.sh` — Extract repo from PR URL

Add a function to extract the GitLab repo slug from a PR URL:
```bash
# Extract "group/project" from "https://gitlab.com/group/project/-/merge_requests/1"
gitlab_extract_repo_from_url() {
    local url="$1"
    echo "$url" | sed 's|https://gitlab.com/||; s|/-/merge_requests/.*||'
}
```

Update all GitLab functions to accept and use the repo:
- `gitlab_get_pr_status()` line 96: `glab mr view "$mr_num" -F json` → add `-R "$repo"`
- `gitlab_add_comment()` line 109: `glab mr note "$mr_num" -m "$body"` → add `-R "$repo"`
- `gitlab_close_pr()` lines 118-120: `glab mr note` and `glab mr close` → add `-R "$repo"`

The repo slug should be extracted from `$PR_URL` early in the `run_close()` function and stored in a variable accessible to the backend functions.

### 2. `aitask_issue_update.sh` — Extract repo from issue URL

Same pattern:
```bash
# Extract "group/project" from "https://gitlab.com/group/project/-/issues/1"
gitlab_extract_repo_from_issue_url() {
    local url="$1"
    echo "$url" | sed 's|https://gitlab.com/||; s|/-/issues/.*||'
}
```

Update GitLab functions:
- `gitlab_get_issue_status()` line 95: `glab issue view` → add `-R "$repo"`
- `gitlab_add_comment()` line 107: `glab issue note` → add `-R "$repo"`
- `gitlab_close_issue()` lines 116-118: `glab issue note` and `glab issue close` → add `-R "$repo"`

### 3. Thread the repo through function calls

Option A (cleaner): Set a module-level variable `GITLAB_REPO_SLUG` after extracting from URL, used by all GitLab functions.

Option B: Pass as additional parameter to each function.

Recommend Option A for consistency with t277_1's `REPO_OVERRIDE` pattern.

## Reference Files for Patterns

- `aiscripts/aitask_pr_import.sh` — After t277_1, will have `glab_repo_flag()` helper pattern
- `aiscripts/aitask_pr_close.sh:87-93` — `gitlab_extract_pr_number()` already parses GitLab URLs
- `aiscripts/aitask_issue_update.sh:86-92` — `gitlab_extract_issue_number()` already parses GitLab URLs

## Verification Steps

```bash
# Test with --dry-run against a real GitLab MR (after t277_3 creates one):
./aiscripts/aitask_pr_close.sh --dry-run --pr-url "https://gitlab.com/beyondeye/testrepo_gitlab/-/merge_requests/1" 277

# Test issue update with --dry-run:
./aiscripts/aitask_issue_update.sh --dry-run --issue-url "https://gitlab.com/beyondeye/testrepo_gitlab/-/issues/1" 277
```
