---
priority: high
effort: medium
depends: []
issue_type: feature
status: Done
labels: [portability, shell]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-25 12:13
updated_at: 2026-02-25 12:42
completed_at: 2026-02-25 12:42
---

## Context

This is child task 1 of t214 (Multi-platform reviewguide import and setup dedup). The parent task identified that the `aitask-reviewguide-import` skill hardcodes GitHub-specific URL patterns and API calls for fetching files and listing directories. To support GitLab and Bitbucket, we need a reusable bash helper library that dispatches to the correct platform-specific backend.

## Key Files to Create

- `aiscripts/lib/repo_fetch.sh` — New helper library

## Reference Files for Patterns

- `aiscripts/lib/task_utils.sh:85-113` — Existing `detect_platform()` and `detect_platform_from_url()` functions to follow as pattern
- `aiscripts/aitask_issue_import.sh:64-388` — Existing multi-platform dispatcher pattern (`source_*` functions routing via `case $SOURCE`)
- `aiscripts/lib/terminal_compat.sh` — Source for `die()`, `warn()`, `info()` helpers

## Implementation Plan

### Functions to implement

1. **`repo_detect_platform_from_url(url)`** — Returns `github`, `gitlab`, `bitbucket`, or empty string
   - `github.com` in URL → github
   - `gitlab.com` in URL → gitlab
   - `bitbucket.org` in URL → bitbucket

2. **`repo_parse_url(url)`** — Sets global vars `_RF_PLATFORM`, `_RF_OWNER`, `_RF_REPO`, `_RF_BRANCH`, `_RF_PATH`, `_RF_TYPE` (file|directory)
   - GitHub: split on `/blob/` (file) or `/tree/` (dir), extract owner/repo from path segments
   - GitLab: split on `/-/blob/` or `/-/tree/`, extract owner/repo from path segments
   - Bitbucket: split on `/src/`, file vs dir detected by extension heuristic (has `.ext` = file, otherwise = directory)

3. **`repo_fetch_file(url)`** — Fetches a single file's raw content to stdout. Calls `repo_parse_url` internally.
   - GitHub: `gh api repos/{owner}/{repo}/contents/{path}?ref={branch} --jq '.content' | base64 -d`, fallback to `curl` on `raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}`
   - GitLab: `glab api "projects/{owner}%2F{repo}/repository/files/{url_encoded_path}/raw?ref={branch}"`, fallback to `curl` on `gitlab.com/{owner}/{repo}/-/raw/{branch}/{path}`
   - Bitbucket: `curl` on `bitbucket.org/{owner}/{repo}/raw/{branch}/{path}` (primary — no CLI equivalent for file content)

4. **`repo_list_md_files(url)`** — Lists `.md` filenames in a directory, one per line. Calls `repo_parse_url` internally.
   - GitHub: `gh api "repos/{owner}/{repo}/contents/{path}?ref={branch}" --jq '.[] | select(.name | endswith(".md")) | .name'`
   - GitLab: `glab api "projects/{owner}%2F{repo}/repository/tree?path={path}&ref={branch}&per_page=100" --jq '.[] | select(.type == "blob") | select(.name | endswith(".md")) | .name'`
   - Bitbucket: `curl "https://api.bitbucket.org/2.0/repositories/{owner}/{repo}/src/{branch}/{path}/?pagelen=100" | jq -r '.values[] | select(.path | endswith(".md")) | .path | split("/") | last'`

### Verified API methods (tested against live repos during planning)

| Method | Command | Result |
|--------|---------|--------|
| GitLab single file | `glab api "projects/gitlab-org%2Fgitlab/repository/files/README.md/raw?ref=master"` | 200 |
| GitLab raw fallback | `curl https://gitlab.com/gitlab-org/gitlab/-/raw/master/README.md` | 200 |
| GitLab dir listing | `glab api "projects/gitlab-org%2Fgitlab/repository/tree?path=doc/api&per_page=100"` | 91 .md files |
| Bitbucket single file | `curl https://bitbucket.org/tutorials/markdowndemo/raw/master/README.md` | 200 |
| Bitbucket dir listing | `curl https://api.bitbucket.org/2.0/repositories/atlassian/aws-s3-deploy/src/master/?pagelen=100` | 4 .md files |
| GitHub single file | `gh api repos/cli/cli/contents/README.md?ref=trunk --jq '.content' \| base64 -d` | 200 |
| GitHub dir listing | `gh api repos/cli/cli/contents/docs?ref=trunk` | 16 .md files |

### Design conventions
- Shebang: `#!/usr/bin/env bash`
- Guard: `[[ -n "${_AIT_REPO_FETCH_LOADED:-}" ]] && return 0; _AIT_REPO_FETCH_LOADED=1`
- Source `terminal_compat.sh` for `die()`, `warn()`, `info()`
- Global var prefix: `_RF_` (repo fetch)
- Fallback chain: CLI tool first, then `curl` on raw URL
- GitLab path URL-encoding: replace `/` with `%2F` in path for API calls
- base64 portability: use `base64 -d` on Linux; add macOS detection if needed

## Verification Steps

1. `shellcheck aiscripts/lib/repo_fetch.sh`
2. Source the library and test each function manually
3. Sibling task t214_2 provides automated tests
