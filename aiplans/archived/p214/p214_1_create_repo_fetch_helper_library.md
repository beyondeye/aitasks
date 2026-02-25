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

### Step 7: Create automated tests (integrated from t214_2)

Created `tests/test_repo_fetch.sh` with 42 tests:
- 36 offline tests: platform detection (4), URL parsing (32 including GitHub/GitLab/Bitbucket file/dir/nested/trailing-slash/root)
- 6 network tests (gated by `SKIP_NETWORK=1`): file fetch (3), directory listing (3)

Test repos: cli/cli (GitHub), gitlab-org/gitlab (GitLab), tutorials/markdowndemo (Bitbucket file), atlassian/aws-s3-deploy (Bitbucket dir)

## Final Implementation Notes
- **Actual work done:** Created `aiscripts/lib/repo_fetch.sh` with 4 public functions and 6 platform backends, plus `tests/test_repo_fetch.sh` with 42 tests (integrating t214_2's test plan into this task)
- **Deviations from plan:** Added `_rf_base64_decode()` for macOS portability, `_rf_url_encode_path()` for GitLab API, and `_rf_has_cmd()` helper. GitLab directory listing has a curl fallback to the public REST API. Bitbucket URL construction handles empty paths (root directory).
- **Issues encountered:**
  - **`set -e` interaction with `[[ ]] && die`**: The pattern `[[ "$_RF_TYPE" != "file" ]] && die "..."` causes `set -e` to exit the script when the condition is false (type IS correct). Fixed by using `if/then/fi` instead. This is a classic bash pitfall.
  - **Bitbucket `pipes` directory**: The original test plan referenced `pipes` (correct name is `pipe`) and it has no `.md` files. Switched to root directory listing (`src/master/`) which has 4 `.md` files.
  - **Bitbucket root URL construction**: Empty `_RF_PATH` caused double slashes in API URL. Fixed by building `api_path` conditionally.
- **Key decisions:** CLI tools (gh, glab) are tried first with graceful fallback to curl raw URLs. Bitbucket has no CLI equivalent for file content, so curl is always used. GitHub directory listing has no curl fallback (requires gh CLI).
- **Notes for sibling tasks:**
  - t214_2 (tests): Already integrated into this task — the test file follows the spec from t214_2. Consider marking t214_2 as done/folded.
  - t214_3 (update reviewguide-import skill): Source `repo_fetch.sh` and replace hardcoded `gh api` calls with `repo_fetch_file()` and `repo_list_md_files()`. The library handles platform detection and dispatching internally.
  - t214_4 (setup.sh dedup): Unrelated to repo_fetch.sh — just needs to replace inline `_detect_git_platform()` with `detect_platform()` from task_utils.sh.
