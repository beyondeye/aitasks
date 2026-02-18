---
Task: t146_bitbucket_support.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

## Context

Task t146 adds Bitbucket Cloud support for issue import/update, following the same platform-extensible dispatcher pattern used by the existing GitHub and GitLab backends. The integration uses the community `bkt` CLI tool ([avivsinai/bitbucket-cli](https://github.com/avivsinai/bitbucket-cli)), which provides `gh`-style ergonomics with `--json` output.

The GitLab integration (t136) serves as the direct template — we follow the exact same file-by-file, function-by-function pattern.

## Key Discovery: `bkt` Pre-Normalizes JSON

Unlike the raw Bitbucket REST API 2.0, the `bkt --json` output already provides:
- `.body` — flat string (NOT `.content.raw`)
- `.url` — full URL (NOT `.links.html.href`)
- `.comments[].body` — flat string
- `.comments[].author` — email string (NOT an object)

This made the `jq` normalization much simpler than originally planned.

## `bkt` CLI Context Requirement

`bkt` requires an active context (`bkt context create ... --set-active`) before most commands work. This is different from `gh`/`glab` which auto-detect the repository from the git remote.

## Implementation Steps

### Step 0: Install `bkt` CLI and Authenticate ✅

- Installed `bkt` v0.8.1 from GitHub releases to `~/.local/bin/bkt`
- User authenticated via `bkt auth login https://bitbucket.org --kind cloud --web`
- Created context for test repo: `bkt context create testrepo --host "https://api.bitbucket.org/2.0" --workspace eyebeyond --repo test_repo_bitbucket --set-active`
- Probed JSON format: `bkt issue view 2 --comments --json` and `bkt issue list --state new --json`

### Step 1: Platform Detection — `aiscripts/lib/task_utils.sh` ✅

Added `bitbucket` detection to both `detect_platform()` and `detect_platform_from_url()`.

### Step 2: Issue Import — `aiscripts/aitask_issue_import.sh` ✅

Added 7 backend functions:
1. `bitbucket_check_cli()` — Checks `bkt`, `jq`, and `bkt auth status`
2. `bitbucket_fetch_issue()` — Fetches via `bkt issue view --comments --json`, normalizes: `.kind` → labels, `.comments[].author` string → `{login: .}` object, `.created_on` → `.createdAt`
3. `bitbucket_format_comments()` — Reuses `github_format_comments`
4. `bitbucket_list_issues()` — Fetches both `--state new` and `--state open` (Bitbucket default only returns `open`, missing `new`), extracts from `{"issues": [...]}` envelope
5. `bitbucket_map_labels()` — Reuses `github_map_labels`
6. `bitbucket_detect_type()` — Custom: `bug`→bug, `enhancement`/`proposal`→feature, `task`→chore
7. `bitbucket_preview_issue()` — `bkt issue view "$issue_num"`

Wired all 7 dispatchers and updated validation/help text.

### Step 3: Issue Update — `aiscripts/aitask_issue_update.sh` ✅

Added 5 backend functions:
1. `bitbucket_check_cli()` — Same as import
2. `bitbucket_extract_issue_number()` — Uses `/issues/[0-9]+` pattern (handles trailing slug)
3. `bitbucket_get_issue_status()` — Normalizes 7 Bitbucket states to `OPEN`/`CLOSED`
4. `bitbucket_add_comment()` — `bkt issue comment "$issue_num" -b "$body"`
5. `bitbucket_close_issue()` — Two-step: comment first, then close (like GitLab)

Wired all 5 dispatchers and updated validation/help text.

### Step 4: Setup Script — `aiscripts/aitask_setup.sh` ✅

- Added `bitbucket` to `_detect_git_platform()`
- Added `bitbucket)` case to platform CLI selection
- Added `bkt` installation for all OS variants:
  - **Arch Linux:** Downloads binary from GitHub releases to `~/.local/bin/bkt`
  - **Debian/Ubuntu:** Downloads `.deb` package from GitHub releases
  - **Fedora:** Downloads binary from GitHub releases to `/usr/local/bin/bkt`
  - **macOS:** `brew install avivsinai/tap/bitbucket-cli`

### Step 5: Documentation — `README.md` ✅

- Updated CLI tools line to mention `bkt`
- Replaced Bitbucket TODO placeholder with full auth instructions including context setup

### Step 6: Documentation — `docs/commands.md` ✅

Updated all references: issue-import, issue-update, setup sections to mention Bitbucket.

### Step 7: Integration Guide — `aidocs/gitremoteproviderintegration.md` ✅

- Added Bitbucket column to field mapping table
- Added 6 Bitbucket-specific pitfalls to Common Pitfalls section

## Files Modified

1. `aiscripts/lib/task_utils.sh` — Added bitbucket detection
2. `aiscripts/aitask_issue_import.sh` — 7 backend functions + 7 dispatcher cases + validation
3. `aiscripts/aitask_issue_update.sh` — 5 backend functions + 5 dispatcher cases + validation
4. `aiscripts/aitask_setup.sh` — Platform detection + bkt installation for all OSes
5. `README.md` — Bitbucket auth instructions
6. `docs/commands.md` — Updated issue-import/update/setup sections
7. `aidocs/gitremoteproviderintegration.md` — Added Bitbucket to field mapping + pitfalls

## Automated Testing — All 8 Tests Passed ✅

Test repo: `/home/ddt/Work/TESTS/test_repo_bitbucket` (remote: `https://beyondeye2@bitbucket.org/eyebeyond/test_repo_bitbucket.git`)

| Test | Result |
|------|--------|
| 1a. Import help mentions bitbucket | PASS |
| 1b. Update help mentions bitbucket | PASS |
| 2. Platform auto-detection from git remote | PASS |
| 3. Import issue #1 with explicit `--source bitbucket` | PASS |
| 4. Import issue #2 with auto-detection | PASS |
| 5. Issue update dry-run | PASS |
| 6. Issue update — post comment | PASS |
| 7. Issue update — close with comment (two-step) | PASS |
| 8. Re-open issue for future testing | PASS |

## Step 9 (Post-Implementation)

After implementation and testing: archive task, update issue if linked, push.
