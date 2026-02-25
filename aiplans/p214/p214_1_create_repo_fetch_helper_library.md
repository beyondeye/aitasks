---
Task: t214_1_create_repo_fetch_helper_library.md
Parent Task: aitasks/t214_multi_platform_reviewguide_import_and_setup_dedup.md
Sibling Tasks: aitasks/t214/t214_2_*.md, aitasks/t214/t214_3_*.md, aitasks/t214/t214_4_*.md
Worktree: (none — working on current branch)
Branch: (current)
Base branch: main
---

## Implementation Plan

### Step 1: Create `aiscripts/lib/repo_fetch.sh`

Create the file with the standard library structure:

```bash
#!/usr/bin/env bash
# repo_fetch.sh — Multi-platform repository file fetching and directory listing
# Supports GitHub, GitLab, and Bitbucket URLs

[[ -n "${_AIT_REPO_FETCH_LOADED:-}" ]] && return 0
_AIT_REPO_FETCH_LOADED=1

# Source terminal_compat.sh for die/warn/info
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/terminal_compat.sh"
```

### Step 2: Implement `repo_detect_platform_from_url()`

Simple hostname matching (same pattern as `detect_platform_from_url()` in `task_utils.sh`):

```bash
repo_detect_platform_from_url() {
    local url="$1"
    if [[ "$url" == *"gitlab.com"* ]]; then echo "gitlab"
    elif [[ "$url" == *"bitbucket.org"* ]]; then echo "bitbucket"
    elif [[ "$url" == *"github.com"* ]]; then echo "github"
    else echo ""; fi
}
```

### Step 3: Implement `repo_parse_url()`

Sets global variables `_RF_PLATFORM`, `_RF_OWNER`, `_RF_REPO`, `_RF_BRANCH`, `_RF_PATH`, `_RF_TYPE`.

Key parsing logic per platform:
- **GitHub:** Strip `https://github.com/`, split on `/blob/` or `/tree/`, first two segments are owner/repo, after split is `{branch}/{path}`
- **GitLab:** Strip `https://gitlab.com/`, split on `/-/blob/` or `/-/tree/`, first two segments are owner/repo
- **Bitbucket:** Strip `https://bitbucket.org/`, split on `/src/`, first two segments are owner/repo. File vs directory: check if last path segment has a `.` extension → file, otherwise → directory

Branch/path split: first segment after the split token is the branch, rest is the path.

### Step 4: Implement `repo_fetch_file()`

Takes a URL, calls `repo_parse_url()`, then dispatches:

- **GitHub:** Try `gh api`, fallback to `curl` on raw URL
- **GitLab:** Try `glab api` with URL-encoded path, fallback to `curl` on raw URL
- **Bitbucket:** Use `curl` on raw URL directly

### Step 5: Implement `repo_list_md_files()`

Takes a directory URL, calls `repo_parse_url()`, then dispatches:

- **GitHub:** `gh api` with jq filter for `.md` files
- **GitLab:** `glab api` repository/tree endpoint with jq filter for `.md` blobs
- **Bitbucket:** Bitbucket REST API 2.0 with jq filter

### Step 6: Run shellcheck

```bash
shellcheck aiscripts/lib/repo_fetch.sh
```

## Post-Implementation (Step 9)
Archive task and plan. Push changes.
