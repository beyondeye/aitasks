---
priority: high
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [claudeskills, aitask_reviewguide, portability]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-23 00:12
updated_at: 2026-02-25 10:50
boardcol: now
boardidx: 10
---

## Problem

The `aitask-reviewguide-import` Claude skill and `aitask_setup.sh` have hardcoded GitHub-specific code that breaks when the git remote is GitLab or Bitbucket.

### aitask-reviewguide-import skill (`.claude/skills/aitask-reviewguide-import/SKILL.md`)

The skill assumes all remote URLs are GitHub URLs:

1. **URL detection** (Step 1b): Only checks for `github.com` patterns (`/blob/`, `/tree/`). GitLab uses the same URL structure but with `gitlab.com`. Bitbucket uses different patterns (`/src/` instead of `/blob/`, no `/tree/` equivalent).

2. **Content fetching** (Step 1c): Uses `gh api repos/{owner}/{repo}/contents/{path}?ref={branch}` exclusively. No equivalent for:
   - GitLab: `glab api projects/{id}/repository/files/{path}?ref={branch}` or REST API
   - Bitbucket: `bkt` CLI or REST API

3. **Directory listing** (Step 1c): Uses `gh api "repos/{owner}/{repo}/contents/{path}?ref={branch}"` to list files. No GitLab/Bitbucket equivalent.

4. **Fallback URL construction**: Converts to `raw.githubusercontent.com` which is GitHub-specific. GitLab equivalent is `gitlab.com/{owner}/{repo}/-/raw/{branch}/{path}`.

### aitask_setup.sh (`aiscripts/aitask_setup.sh`)

1. **Duplicated platform detection**: Has inline `_detect_git_platform()` (lines 72-84) that duplicates `detect_platform()` from `task_utils.sh`. Should reuse the shared function.

2. **Hardcoded GitHub API for bkt download**: Uses `api.github.com/repos/avivsinai/bitbucket-cli/releases/latest` (line 145) and `github.com/avivsinai/bitbucket-cli/releases/download/...` (line 147). These are acceptable since the bkt tool is hosted on GitHub, but should be documented as intentional.

## Solution

### For aitask-reviewguide-import skill:

Follow the same dispatcher pattern used in `aitask_issue_import.sh` and `aitask_issue_update.sh`:

1. Add URL detection for GitLab (`gitlab.com`, `/blob/`, `/tree/` or `/-/blob/`, `/-/tree/`) and Bitbucket (`bitbucket.org`, `/src/`)
2. Add platform-specific content fetching:
   - GitHub: `gh api` (existing)
   - GitLab: `glab api` or `WebFetch` with raw URL
   - Bitbucket: `WebFetch` with raw URL (Bitbucket has simple raw URLs)
3. Add platform-specific directory listing or fallback to WebFetch + HTML parsing
4. Update fallback raw URL construction per platform
5. Use `detect_platform_from_url()` from `task_utils.sh` to determine which backend to use

### For aitask_setup.sh:

1. Replace inline `_detect_git_platform()` with sourcing `task_utils.sh` and using `detect_platform()`
2. Add a comment documenting that `api.github.com` URLs for bkt download are intentional (bkt is hosted on GitHub regardless of the user's platform)

## Reference

- Existing multi-platform pattern: `aiscripts/aitask_issue_import.sh` (lines 319-388 dispatchers)
- Platform detection: `aiscripts/lib/task_utils.sh` (`detect_platform`, `detect_platform_from_url`)
- Extension guide: `aidocs/gitremoteproviderintegration.md`
