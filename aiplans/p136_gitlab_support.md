---
Task: t136_gitlab_support.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

## Context

The aitasks project currently supports only GitHub for issue import/update operations. The bash scripts `aitask_issue_import.sh` and `aitask_issue_update.sh` already use a platform-extensible dispatcher pattern with clearly marked `PLATFORM-EXTENSION-POINT` comments. This task adds GitLab as a second platform backend, including auto-detection from git remote/issue URLs, setup script changes to install `glab` CLI, and documentation updates.

## Design Decisions

- **Auto-detection**: Detect platform from git remote URL (for import) and issue URL (for update), with `--source` as override
- **Setup install**: Detect platform from git remote and install only the relevant CLI tool
- **JSON normalization**: GitLab backend functions normalize JSON output to match GitHub's field structure, so all consumer code works unchanged

## Implementation Steps

### 1. Add shared platform detection utility

**File: `aiscripts/lib/task_utils.sh`**

Add a `detect_platform()` function that examines the git remote URL:
```bash
detect_platform() {
    local remote_url
    remote_url=$(git remote get-url origin 2>/dev/null || echo "")
    if [[ "$remote_url" == *"gitlab"* ]]; then
        echo "gitlab"
    elif [[ "$remote_url" == *"github"* ]]; then
        echo "github"
    else
        echo ""  # unknown — caller decides fallback
    fi
}
```

Also add `detect_platform_from_url()` for issue URL detection:
```bash
detect_platform_from_url() {
    local url="$1"
    if [[ "$url" == *"gitlab"* ]]; then echo "gitlab"
    elif [[ "$url" == *"github"* ]]; then echo "github"
    else echo ""; fi
}
```

### 2. Add GitLab backend to `aitask_issue_import.sh`

**File: `aiscripts/aitask_issue_import.sh`**

Add GitLab backend functions after the GitHub backend section (~line 71):

- **`gitlab_check_cli()`**: Verify `glab` CLI installed and authenticated
  ```bash
  command -v glab || die "glab CLI required for GitLab. Install: https://gitlab.com/gitlab-org/cli"
  command -v jq || die "jq is required"
  glab auth status &>/dev/null || die "glab CLI not authenticated. Run: glab auth login"
  ```

- **`gitlab_fetch_issue()`**: Fetch issue via `glab api`, normalize JSON to match GitHub format:
  - Use `glab api "projects/:fullpath/issues/$issue_num"` for issue data
  - Use `glab api "projects/:fullpath/issues/$issue_num/notes?sort=asc&per_page=100"` for comments
  - Normalize with `jq`: `.description` → `.body`, `.web_url` → `.url`, `.labels[]` → `.labels[].name` objects, `.created_at` → `.createdAt`, system notes filtered out from comments, `.author.username` → `.author.login`

- **`gitlab_format_comments()`**: Same logic as GitHub — the JSON is already normalized to GitHub format by `gitlab_fetch_issue()`

- **`gitlab_list_issues()`**: Use `glab api "projects/:fullpath/issues?state=opened&per_page=100" --paginate`, normalize to match GitHub format (`iid` → `number`, labels as objects, `web_url` → `url`)

- **`gitlab_map_labels()`**: Same logic as GitHub — labels normalized to same `[{"name":"..."}]` format

- **`gitlab_detect_type()`**: Same logic as GitHub — reuse `github_detect_type` or extract shared logic

- **`gitlab_preview_issue()`**: Use `glab issue view "$issue_num"`

Wire up dispatchers (7 `case` statements) to add `gitlab)` branches.

**Auto-detection change**: Modify the default `SOURCE` from hardcoded `"github"` to auto-detected:
```bash
SOURCE=""  # Will be auto-detected if not set via --source
```
In `parse_args()`, after parsing, if `SOURCE` is empty, call `detect_platform()`. If that returns empty, die with error message listing supported platforms.

Update validation in `parse_args()` (line 753-757) to accept `gitlab`.

### 3. Add GitLab backend to `aitask_issue_update.sh`

**File: `aiscripts/aitask_issue_update.sh`**

Add GitLab backend functions after GitHub section (~line 33):

- **`gitlab_check_cli()`**: Same as import script
- **`gitlab_extract_issue_number()`**: Parse GitLab URL format `https://gitlab.com/group/project/-/issues/123` — extract number after last `/`  (same regex `grep -oE '[0-9]+$'` works for both platforms)
- **`gitlab_get_issue_status()`**: Use `glab api "projects/:fullpath/issues/$issue_num" | jq -r '.state'` — returns `opened`/`closed`. Normalize to `OPEN`/`CLOSED` to match GitHub format
- **`gitlab_add_comment()`**: Use `glab issue note "$issue_num" -m "$body"`
- **`gitlab_close_issue()`**: `glab issue close` doesn't support `--comment` flag, so: if comment provided, first post note, then close:
  ```bash
  gitlab_close_issue() {
      local issue_num="$1"
      local comment="$2"
      if [[ -n "$comment" ]]; then
          glab issue note "$issue_num" -m "$comment"
      fi
      glab issue close "$issue_num"
  }
  ```

Wire up dispatchers (5 `case` statements).

**Auto-detection change**: In `run_update()`, after extracting the issue URL (line 202), if `SOURCE` is still default, auto-detect from the issue URL using `detect_platform_from_url()`. This is better than git remote detection because the issue URL explicitly tells us the platform.

Update validation in `parse_args()` (line 365-368) to accept `gitlab`.

### 4. Update `aitask_setup.sh` for platform-aware CLI installation

**File: `aiscripts/aitask_setup.sh`**

Changes to `install_cli_tools()` (line 72):

- Add platform detection at the start:
  ```bash
  local platform
  platform=$(detect_platform)
  ```
- Build tools list dynamically:
  - Always: `fzf jq git`
  - If platform is `github` or empty: add `gh`
  - If platform is `gitlab`: add `glab`
  - If platform is empty (unknown): add `gh` as default

- Update the OS-specific installation blocks:
  - **Arch**: Map `glab` → `glab` package (it's in extra repo, no special mapping needed)
  - **Debian/Ubuntu**: For `glab`, download `.deb` from GitLab releases:
    ```bash
    if $need_glab; then
        info "Installing GitLab CLI..."
        local arch=$(dpkg --print-architecture)
        local glab_ver
        glab_ver=$(curl -s "https://gitlab.com/api/v4/projects/34675721/releases" | jq -r '.[0].tag_name' | sed 's/^v//')
        if [[ -n "$glab_ver" ]]; then
            local deb_file="glab_${glab_ver}_linux_${arch}.deb"
            curl -sLO "https://gitlab.com/gitlab-org/cli/-/releases/v${glab_ver}/downloads/${deb_file}"
            sudo dpkg -i "$deb_file"
            rm -f "$deb_file"
        else
            warn "Could not determine latest glab version. Install manually."
        fi
    fi
    ```
  - **Fedora**: `glab` is in official repos — `dnf install glab`
  - **macOS**: `brew install glab`

- Add `glab` authentication check after installation (similar to existing `gh auth status` check on line 77 of issue_import), but only if platform is gitlab.

- Source `task_utils.sh` to access `detect_platform()` function (or inline the detection).

### 5. Update README.md GitLab section

**File: `README.md`** (lines 133-135)

Replace the TODO placeholder with actual instructions:
```markdown
### GitLab

Authenticate the GitLab CLI:

\```bash
glab auth login
\```

Follow the prompts to authenticate via browser or token. This also configures
git credentials for pushing to GitLab remotes.
```

Also update the "Global dependencies" line (114) to mention `glab` as an alternative to `gh`:
```
- CLI tools: `fzf`, `gh` (for GitHub) or `glab` (for GitLab), `jq`, `git`
```

### 6. Update docs/commands.md

**File: `docs/commands.md`**

- Update `ait issue-import` section (line 373): Change "Import GitHub issues" → "Import GitHub/GitLab issues"
- Update `--source` option description (line 407): `github (default)` → `github, gitlab (auto-detected from git remote)`
- Add note about auto-detection behavior
- Update `ait issue-update` section (line 433): Same changes
- Update `--source` description (line 446): same as above
- Update help text in both scripts' `show_help()` functions

### 7. Update help text in scripts

- **`aitask_issue_import.sh`** `show_help()`: Update `--source` description and header
- **`aitask_issue_update.sh`** `show_help()`: Same updates

## Key Technical Details

### GitLab API JSON ↔ GitHub JSON Normalization

The GitLab `glab api` returns different field names than GitHub `gh`. The `gitlab_fetch_issue()` function normalizes using `jq`:

| GitHub field | GitLab field | Transform |
|---|---|---|
| `.body` | `.description` | rename |
| `.url` | `.web_url` | rename |
| `.labels[].name` | `.labels[]` (strings) | wrap in `{name: .}` |
| `.createdAt` | `.created_at` | rename |
| `.updatedAt` | `.updated_at` | rename |
| `.comments[].author.login` | `.notes[].author.username` | rename + filter system notes |
| `.state` = `OPEN`/`CLOSED` | `.state` = `opened`/`closed` | uppercase + trim "ed" |

### `glab issue close` vs `gh issue close`

`gh issue close` supports `--comment` flag. `glab issue close` does NOT. The `gitlab_close_issue()` function handles this by posting a note first, then closing.

### Auto-detection Flow

**Issue import** (`aitask_issue_import.sh`):
1. If `--source` provided → use it
2. Else → `detect_platform()` from git remote URL
3. If still empty → die with "Could not auto-detect platform. Use --source github|gitlab"

**Issue update** (`aitask_issue_update.sh`):
1. If `--source` provided → use it
2. Else → `detect_platform_from_url()` from the task's `issue` field URL
3. If still empty → `detect_platform()` from git remote as fallback
4. If still empty → die with error

### 8. Create git remote provider integration guide and update t146

After all implementation is complete and verified:

**Create `aidocs/gitremoteproviderintegration.md`** — a developer guide summarizing all the places in the aitasks framework that need to be updated to support a new git remote provider (like Bitbucket). This document should cover:

- **Overview**: The platform-extensible dispatcher architecture pattern
- **Extension checklist** — every file and section that needs changes:
  1. `aiscripts/lib/task_utils.sh` — Add platform detection patterns for the new provider
  2. `aiscripts/aitask_issue_import.sh` — Implement 7 backend functions (`<platform>_check_cli`, `_fetch_issue`, `_format_comments`, `_list_issues`, `_map_labels`, `_detect_type`, `_preview_issue`), add to 7 dispatcher `case` statements, add to `parse_args()` validation
  3. `aiscripts/aitask_issue_update.sh` — Implement 5 backend functions (`<platform>_check_cli`, `_extract_issue_number`, `_get_issue_status`, `_add_comment`, `_close_issue`), add to 5 dispatcher `case` statements, add to `parse_args()` validation
  4. `aiscripts/aitask_setup.sh` — Add CLI tool installation for each OS (Arch, Debian/Ubuntu, Fedora, macOS), add platform detection pattern, add auth check
  5. `README.md` — Add authentication section for the new provider
  6. `docs/commands.md` — Update issue-import and issue-update documentation
  7. Help text in both scripts' `show_help()` functions
- **JSON normalization requirements**: The expected normalized JSON structure that all backends must produce (matching the GitHub format), with a field mapping table
- **Auto-detection**: How `detect_platform()` and `detect_platform_from_url()` work, and how to add new URL patterns
- **CLI tool differences**: Notes on common CLI differences to watch for (e.g., `--comment` flag availability on close commands)

**Update `aitasks/t146_bitbucket_support.md`**: Add a reference to this integration guide:
```
See aidocs/gitremoteproviderintegration.md for the full checklist of files and sections to update.
```

## Files to Modify

1. `aiscripts/lib/task_utils.sh` — Add `detect_platform()` and `detect_platform_from_url()`
2. `aiscripts/aitask_issue_import.sh` — Add GitLab backend, auto-detection, update dispatchers/validation
3. `aiscripts/aitask_issue_update.sh` — Add GitLab backend, auto-detection, update dispatchers/validation
4. `aiscripts/aitask_setup.sh` — Platform-aware CLI installation
5. `README.md` — GitLab authentication instructions
6. `docs/commands.md` — Update issue-import and issue-update documentation
7. `aidocs/gitremoteproviderintegration.md` — New file: provider integration guide
8. `aitasks/t146_bitbucket_support.md` — Add reference to integration guide

## Verification

Test repo: `/home/ddt/Work/TESTS/testrepo_gitlab` (remote: `https://gitlab.com/beyondeye/testrepo_gitlab.git`)
Test issue: `#1` — "Test issue add ciao! to readme" (label: `documentation`)

Verified JSON structure from `glab issue view 1 -F json`:
- `title`, `description` (not `body`), `labels` = `["documentation"]` (strings not objects), `web_url`, `created_at`, `updated_at`, `state` = `"opened"`, `iid` = 1, `author.username` = `"beyondeye"`

**Test steps (run from the test repo directory):**

1. **Help text**: `ait issue-import --help` and `ait issue-update --help` — verify `--source` mentions `github, gitlab`
2. **Platform auto-detection**: Run import script in the GitLab test repo to verify `detect_platform()` returns `"gitlab"` from the remote URL
3. **Import issue #1**: `cd /home/ddt/Work/TESTS/testrepo_gitlab && /home/ddt/Work/aitasks/aiscripts/aitask_issue_import.sh --source gitlab --batch --issue 1` — verify task file is created with correct title, description, labels, issue URL
4. **Import auto-detect**: Same as above but without `--source` — should auto-detect gitlab from remote
5. **Issue update dry-run**: After importing, run `ait issue-update --dry-run <task_num>` on the created task — verify comment body is built correctly
6. **Issue update with comment**: `ait issue-update <task_num>` — verify comment appears on the GitLab issue
7. **Issue close**: `ait issue-update --close <task_num>` — verify issue gets closed with comment on GitLab

## Final Implementation Notes

- **Actual work done:** Implemented all planned steps: GitLab backend functions for both issue-import (7 functions) and issue-update (5 functions), platform auto-detection from git remote and issue URLs, setup script platform-aware CLI installation, README GitLab auth instructions, docs/commands.md updates, help text updates, integration guide document, and t146 reference.
- **Deviations from plan:** None significant. The `gitlab_format_comments`, `gitlab_map_labels`, and `gitlab_detect_type` functions in the import script reuse the GitHub implementations since the JSON is already normalized by `gitlab_fetch_issue()`. Used `glab issue view -F json` instead of `glab api` for fetching single issues (simpler, returns same data).
- **Issues encountered:** Test repo `task_types.txt` was empty (not populated by `ait setup --project-only`), needed manual copy. Test repo lacked atomic ID counter branch, so `--commit` flag failed — worked around by creating task file manually.
- **Key decisions:** (1) GitLab backend normalizes JSON to GitHub format in the fetch functions, so all consumer code works unchanged. (2) `glab issue close` doesn't support `--comment`, so `gitlab_close_issue()` posts note first then closes. (3) Auto-detection uses git remote URL for import and issue URL for update. (4) Setup script uses inline platform detection (doesn't source task_utils.sh which may not exist during initial setup).
- **Testing:** All 7 verification steps passed against test repo `beyondeye/testrepo_gitlab` on GitLab. Import with explicit `--source`, import with auto-detect, update dry-run, comment posting, and issue close all work correctly.

## Step 9 (Post-Implementation)

After implementation: archive task, update issue if linked, push.
