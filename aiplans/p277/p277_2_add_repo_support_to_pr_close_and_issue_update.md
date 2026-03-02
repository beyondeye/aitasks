---
Task: t277_2_add_repo_support_to_pr_close_and_issue_update.md
Parent Task: aitasks/t277_test_pull_request_import_for_gitlab.md
Sibling Tasks: aitasks/t277/t277_1_*.md, aitasks/t277/t277_3_*.md
Archived Sibling Plans: aiplans/archived/p277/p277_1_*.md
Worktree: (none — working on current branch)
Branch: (current)
Base branch: main
---

# Plan: Add repo support to aitask_pr_close.sh and aitask_issue_update.sh

## Context

After t277_1 establishes the `--repo` pattern in `aitask_pr_import.sh`, this task applies the same pattern to `aitask_pr_close.sh` and `aitask_issue_update.sh`. These scripts detect the platform from the PR/issue URL (correct), but `glab` commands still need `-R <repo>` to work from non-GitLab directories.

Key difference from t277_1: These scripts already have the URL available, so the repo slug can be extracted from the URL rather than requiring a separate `--repo` flag.

## Steps

### Step 1: aitask_pr_close.sh — Add repo extraction from URL

Add a function to extract repo slug from GitLab PR URL (near line 87):

```bash
gitlab_extract_repo_from_url() {
    local url="$1"
    echo "$url" | sed 's|https://gitlab.com/||; s|/-/merge_requests/.*||'
}
```

Add a module-level variable: `GITLAB_REPO_SLUG=""`

In the `run_close()` function (or wherever the platform is determined), after detecting GitLab:
```bash
if [[ "$SOURCE" == "gitlab" ]]; then
    GITLAB_REPO_SLUG=$(gitlab_extract_repo_from_url "$PR_URL")
fi
```

### Step 2: aitask_pr_close.sh — Update GitLab functions to use -R

- `gitlab_get_pr_status()`: `glab mr view "$mr_num" -R "$GITLAB_REPO_SLUG" -F json`
- `gitlab_add_comment()`: `glab mr note "$mr_num" -R "$GITLAB_REPO_SLUG" -m "$body"`
- `gitlab_close_pr()`: add `-R "$GITLAB_REPO_SLUG"` to both `glab mr note` and `glab mr close`

### Step 3: aitask_issue_update.sh — Same pattern

Add repo extraction for issue URLs:
```bash
gitlab_extract_repo_from_issue_url() {
    local url="$1"
    echo "$url" | sed 's|https://gitlab.com/||; s|/-/issues/.*||'
}
```

Add `GITLAB_REPO_SLUG=""` and set it after platform detection.

Update functions:
- `gitlab_get_issue_status()`: add `-R "$GITLAB_REPO_SLUG"` to `glab issue view`
- `gitlab_add_comment()`: add `-R "$GITLAB_REPO_SLUG"` to `glab issue note`
- `gitlab_close_issue()`: add `-R "$GITLAB_REPO_SLUG"` to both `glab issue note` and `glab issue close`

## Step 9: Post-Implementation

Archive task, update linked issues/PRs, push changes.

## Verification

```bash
# Syntax check:
bash -n aiscripts/aitask_pr_close.sh
bash -n aiscripts/aitask_issue_update.sh

# Dry-run test (once test MR exists from t277_3):
./aiscripts/aitask_pr_close.sh --dry-run --pr-url "https://gitlab.com/beyondeye/testrepo_gitlab/-/merge_requests/1" 277
./aiscripts/aitask_issue_update.sh --dry-run --issue-url "https://gitlab.com/beyondeye/testrepo_gitlab/-/issues/1" 277
```
