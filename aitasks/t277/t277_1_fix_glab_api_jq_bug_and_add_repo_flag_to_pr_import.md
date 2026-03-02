---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: []
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-02 15:45
updated_at: 2026-03-02 16:01
---

## Context

The GitLab backend in `aitask_pr_import.sh` has two issues that prevent it from working correctly:

1. **`glab api --jq` flag does not exist** — `gitlab_fetch_pr_files()` at line 243 uses `--jq` which is not a valid `glab api` flag. The error is silently swallowed by `2>/dev/null || echo ""`.
2. **All `glab` commands fail from non-GitLab repos** — When the current working directory has a GitHub (or other) git remote, all `glab mr` and `glab api` commands fail because they can't resolve the repo context. `glab mr` commands support `-R` for repo override, but `glab api` uses `:fullpath` placeholder which resolves from git remote only.

## Key Files to Modify

- `aiscripts/aitask_pr_import.sh` — All GitLab backend functions (lines 198-314)

## Implementation Plan

### 1. Fix `--jq` bug in `gitlab_fetch_pr_files()` (line 243)

Replace:
```bash
glab api "projects/:fullpath/merge_requests/$mr_num/changes" --jq '.changes[] | ...' 2>/dev/null || echo ""
```
With:
```bash
glab api "projects/:fullpath/merge_requests/$mr_num/changes" 2>/dev/null | jq -r '.changes[] | ...' || echo ""
```

### 2. Add `--repo` CLI flag support

- Add `REPO_OVERRIDE=""` variable near line 21
- Add `--repo` to the `parse_args()` case statement (around line 1382)
- Add `--repo` to `show_help()`

### 3. Create helper functions for repo override

```bash
# Returns "-R <repo>" if REPO_OVERRIDE is set, empty string otherwise
glab_repo_flag() {
    if [[ -n "$REPO_OVERRIDE" ]]; then
        echo "-R" "$REPO_OVERRIDE"
    fi
}

# Returns URL-encoded repo path for glab api, or ":fullpath" for auto-detection
glab_api_project_path() {
    if [[ -n "$REPO_OVERRIDE" ]]; then
        # URL-encode slashes: group/project -> group%2Fproject
        echo "${REPO_OVERRIDE//\//%2F}"
    else
        echo ":fullpath"
    fi
}
```

### 4. Update all GitLab backend functions

Functions to update:
- `gitlab_fetch_pr()` (line 207): `glab mr view "$mr_num" -F json` → add `$(glab_repo_flag)`, replace `:fullpath` with `$(glab_api_project_path)` in glab api call
- `gitlab_fetch_pr_diff()` (line 236): `glab mr diff "$mr_num"` → add `$(glab_repo_flag)`
- `gitlab_fetch_pr_files()` (line 241): fix `--jq` bug + replace `:fullpath`
- `gitlab_fetch_pr_reviews()` (line 246): replace `:fullpath`
- `gitlab_fetch_pr_review_comments()` (line 259): replace `:fullpath`
- `gitlab_list_prs()` (line 273): `glab mr list` → add `$(glab_repo_flag)`
- `gitlab_preview_pr()` (line 311): `glab mr view "$mr_num"` → add `$(glab_repo_flag)`
- `gitlab_resolve_contributor_email()` (line 288): `glab api "users?username=..."` — this one doesn't use `:fullpath` but is a global API call, should work fine

### 5. Verify the additions/deletions=0 issue

`gitlab_fetch_pr()` hardcodes `additions: 0, deletions: 0` (lines 230-231). This is a known limitation — the detailed per-file counts come from `gitlab_fetch_pr_files()`. Document this as a TODO comment.

## Reference Files for Patterns

- The GitHub backend functions (lines 70-196) show the expected pattern
- `detect_platform()` in `aiscripts/lib/task_utils.sh:81` shows platform detection
- `glab mr view --help` confirms `-R` flag support
- `glab api --help` does NOT have `-R` — must use explicit project path

## Verification Steps

```bash
# After implementation, test from the aitasks repo (GitHub remote):
./aiscripts/aitask_pr_import.sh --batch --source gitlab --repo beyondeye/testrepo_gitlab --list --silent
# Should list MRs from the GitLab repo (once test MR exists)

# Test data fetch:
./aiscripts/aitask_pr_import.sh --batch --source gitlab --repo beyondeye/testrepo_gitlab --pr 1 --data-only --silent
# Should create .aitask-pr-data/1.md with correct GitLab MR data
```
