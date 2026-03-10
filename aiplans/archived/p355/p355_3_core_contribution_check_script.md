---
Task: t355_3_core_contribution_check_script.md
Parent Task: aitasks/t355_check_for_existing_issues_overlap.md
Sibling Tasks: aitasks/t355/t355_4_*.md through t355_7_*.md
Archived Sibling Plans: aiplans/archived/p355/p355_1_extend_contribute_metadata_with_fingerprint_and_auto_labels.md, aiplans/archived/p355/p355_2_extend_metadata_parser_for_fingerprint_fields.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

Previous siblings (t355_1, t355_2) added fingerprint fields to the `<!-- aitask-contribute-metadata -->` block and extended the parser. This task creates the script that uses that data to detect overlapping contribution issues and post analysis comments.

## Files to Create

- `.aitask-scripts/aitask_contribution_check.sh` — new core script
- `tests/test_contribution_check.sh` — tests

## Files to Modify

- `.aitask-scripts/lib/task_utils.sh` — extract `parse_contribute_metadata()` here (shared by both scripts)
- `.aitask-scripts/aitask_issue_import.sh` — remove local `parse_contribute_metadata()`, now sourced from `task_utils.sh`
- `tests/test_issue_import_contributor.sh` — update `setup_parse_function()` to source from `task_utils.sh` instead of duplicating
- `aitasks/t355/t355_7_documentation_and_seed_distribution.md` — add note about GitLab/Bitbucket CI/CD token configuration requirements

## Implementation Plan

### 0. Extract `parse_contribute_metadata()` to shared lib

Move `parse_contribute_metadata()` from `.aitask-scripts/aitask_issue_import.sh:396-445` into `.aitask-scripts/lib/task_utils.sh`. Guard with `_AIT_CONTRIBUTE_METADATA_LOADED` to prevent double-sourcing (standard pattern in this codebase).

Then in `aitask_issue_import.sh`:
- Remove the function body (lines 392-445)
- It already sources `task_utils.sh`, so the function becomes available automatically

Then in `tests/test_issue_import_contributor.sh`:
- Update `setup_parse_function()` to source from `task_utils.sh` instead of containing a hardcoded copy
- The test helper currently duplicates the function (lines 56-114); replace with a source command

Run existing tests to verify no regression: `bash tests/test_issue_import_contributor.sh`

### 1. Create `.aitask-scripts/aitask_contribution_check.sh`

Standard boilerplate: `#!/usr/bin/env bash`, `set -euo pipefail`, source `terminal_compat.sh` + `task_utils.sh`.

**Global state:**
```
CHECK_PLATFORM, ARG_ISSUE, ARG_PLATFORM, ARG_REPO, ARG_LIMIT=50, ARG_DRY_RUN, ARG_SILENT
OVERLAP_CHECK_VERSION=1
```

**Functions (in order):**

1. `show_help()` — usage text
2. `parse_args()` — positional issue number + `--platform`, `--repo`, `--limit`, `--dry-run`, `--silent`, `--help`
3. `parse_contribute_metadata()` — sourced from `lib/task_utils.sh` (extracted in Step 0). Sets 8 CONTRIBUTE_* globals.
4. **Platform backends** (3 platforms × 5 operations each):
   - `*_check_cli()`, `*_fetch_issue()`, `*_list_contribution_issues()`, `*_post_comment()`, `*_add_label()`, `*_list_repo_labels()`

   **GitHub**: `gh` CLI (pre-installed in GitHub Actions). Uses `gh issue view/list/comment/edit`, `gh label list`. Auth via `$GH_TOKEN` or `$GITHUB_TOKEN` (auto-provided in Actions).

   **GitLab**: CLI-first (`glab`) with curl + REST API fallback. **Critical**: `CI_JOB_TOKEN` does NOT have access to issues/notes/labels API endpoints. The script requires a project/personal access token stored as `$GITLAB_TOKEN` CI/CD variable with `api` scope. Each function checks `command -v glab && glab auth status` first; if unavailable, falls back to curl:
   - API base: `$CI_API_V4_URL` (predefined in GitLab CI) or `https://gitlab.com/api/v4`
   - Project ID: `$CI_PROJECT_ID` (predefined in GitLab CI) or resolved from repo path
   - Auth header: `--header "PRIVATE-TOKEN: $GITLAB_TOKEN"`
   - Endpoints: `GET /projects/:id/issues`, `POST /projects/:id/issues/:iid/notes`, `GET /projects/:id/labels`, `PUT /projects/:id/issues/:iid` (for label update)

   **Bitbucket**: curl + REST API only (no `bkt` dependency — too niche for CI/CD). Auth: Basic auth with `$BITBUCKET_USER:$BITBUCKET_TOKEN` (API token, replacing deprecated app passwords — app passwords fully disabled June 2026). Repo identification from `$BITBUCKET_WORKSPACE`/`$BITBUCKET_REPO_SLUG` (predefined in Pipelines) or from `--repo` flag.
   - API base: `https://api.bitbucket.org/2.0`
   - Endpoints: `GET /repositories/{workspace}/{repo_slug}/issues`, `GET .../issues/{id}`, `POST .../issues/{id}/comments`
   - No issue labels API — no-op for label operations
   - No label-based issue filtering — list returns all open issues, filtered by metadata presence in the main loop

5. **Dispatchers**: `source_check_cli()`, `source_fetch_issue()`, `source_list_contribution_issues()`, `source_post_comment()`, `source_add_label()`, `source_list_repo_labels()` — case on `$CHECK_PLATFORM`
6. `compute_overlap_score()` — weighted set-intersection scoring:
   - File paths: shared × 3, Dirs: shared × 2, Areas: shared × 2, Change type match: +1
   - Uses `declare -A` associative arrays (bash 4+)
   - Sets `OVERLAP_DETAIL` global with human-readable summary
7. `format_overlap_comment()` — markdown table with top 5 results, label suggestions section, machine-readable `<!-- overlap-results top_overlaps: N:S,N:S overlap_check_version: 1 -->` block
   - Thresholds: ≥7 "high", ≥4 "likely", <4 "low"
8. `resolve_label_suggestions()` — matches auto_labels against repo labels, sets `LABEL_SUGGESTIONS`
9. `main()` flow:
   - Resolve platform (flag or `detect_platform()`)
   - Fetch target issue → parse fingerprint → save target values
   - List contribution issues → loop: parse each fingerprint, compute score, skip self and zero-score
   - Sort scored issues descending
   - Resolve label suggestions
   - Format comment
   - If `--dry-run`: print comment, exit
   - Otherwise: post comment + apply matching labels
10. Guard: `if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then main "$@"; fi`

### 2. Create `tests/test_contribution_check.sh`

Standard test pattern with assert_eq/assert_contains helpers, PASS/FAIL/TOTAL counters.

**Test cases:**
1. `compute_overlap_score` — exact match (score=8: 1 file×3 + 1 dir×2 + 1 area×2 + type=1)
2. `compute_overlap_score` — no overlap (score=0)
3. `compute_overlap_score` — directory-only overlap (score=2)
4. `compute_overlap_score` — empty fields (score=0, no errors)
5. `compute_overlap_score` — multiple shared files (e.g., 2 files×3=6)
6. `format_overlap_comment` — with scored results (verify table, thresholds, machine-readable block)
7. `format_overlap_comment` — no results (verify "No overlapping" message)
8. `parse_contribute_metadata` — full body with fingerprint (verify all 6 fields)
9. `parse_contribute_metadata` — body without metadata (empty globals)
10. Threshold classification (score=9→high, score=5→likely, score=2→low)
11. Syntax check: `bash -n`
12. Help output: `--help` exits 0, shows usage

All tests source the script in subshells (`source .aitask-scripts/aitask_contribution_check.sh`), then set globals and call functions directly.

### 3. Update t355_7 task file with CI/CD configuration requirements

Add a note to `aitasks/t355/t355_7_documentation_and_seed_distribution.md` specifying that documentation must cover per-platform CI/CD token configuration:
- **GitHub Actions**: `$GITHUB_TOKEN` auto-provided, no extra setup
- **GitLab CI**: `CI_JOB_TOKEN` cannot access issues/notes/labels APIs. Must create a project access token with `api` scope and store as `$GITLAB_TOKEN` CI/CD variable.
- **Bitbucket Pipelines**: Must create an API token (app passwords deprecated, fully disabled June 2026) and store as `$BITBUCKET_USER` + `$BITBUCKET_TOKEN` repository variables.

## Key Design Decisions

- **Extract parse_contribute_metadata() to lib/task_utils.sh** — eliminates duplication across `aitask_issue_import.sh`, `test_issue_import_contributor.sh`, and this new script. All three now source the shared copy.
- **BASH_SOURCE guard on main()** — enables sourcing for tests
- **`--repo` flag uses `-R` for gh** — enables cross-repo operation in CI
- **CI/CD-first design**: GitHub uses `gh` (pre-installed in Actions, auth via `$GITHUB_TOKEN`). GitLab uses `glab` with curl fallback — **`CI_JOB_TOKEN` cannot access issue/notes/labels APIs**, so `$GITLAB_TOKEN` (project access token with `api` scope) is required as a CI/CD variable. Bitbucket uses curl + REST API only — auth via `$BITBUCKET_USER:$BITBUCKET_TOKEN` (API token, replacing deprecated app passwords by June 2026).
- **Bitbucket: no label ops** — silent no-ops; no label-based issue filtering either, so all issues are fetched and filtered by metadata presence in the main loop

## Verification

1. After Step 0 (refactor): `bash tests/test_issue_import_contributor.sh` — verify no regression from extraction
2. `bash -n .aitask-scripts/aitask_contribution_check.sh`
3. `shellcheck .aitask-scripts/aitask_contribution_check.sh`
4. `shellcheck .aitask-scripts/lib/task_utils.sh` (verify extracted function passes)
5. `bash tests/test_contribution_check.sh`
6. `./.aitask-scripts/aitask_contribution_check.sh --help`
7. Existing tests still pass: `bash tests/test_contribute.sh && bash tests/test_issue_import_contributor.sh`

## Final Implementation Notes

- **Actual work done:** Implemented all plan steps faithfully. Created `aitask_contribution_check.sh` (~740 lines) with 3 platform backends (GitHub/GitLab/Bitbucket), overlap scoring engine, comment formatting, and label resolution. Extracted `parse_contribute_metadata()` to shared lib. Created comprehensive test suite (56 assertions). Added script to all 5 allowlist files (seed + active for Claude Code, Gemini CLI, OpenCode). Updated t355_7 with CI/CD token documentation requirements.
- **Deviations from plan:** Plan mentioned `_AIT_CONTRIBUTE_METADATA_LOADED` guard for the extracted function; skipped it since `task_utils.sh` already has its own `_AIT_TASK_UTILS_LOADED` guard that prevents the entire file from being sourced twice. Added `classify_overlap()` as a separate helper (plan had thresholds inline in `format_overlap_comment`). Bitbucket backend uses curl-only (no `bkt` CLI) as planned. GitLab uses `glab` with curl fallback as planned.
- **Issues encountered:** Shellcheck flagged `SC2034` warnings for CONTRIBUTE_* globals in `task_utils.sh` — expected for library functions that set globals for callers (same as when function lived in `aitask_issue_import.sh`). Fixed real shellcheck issues: replaced `sed 's|/|%2F|g'` with `${var//\//%2F}` bash substitution, removed unused `encoded_body` variable, removed unused `target_title`/`target_url` locals.
- **Key decisions:** Used `local -n` (nameref) for `format_overlap_comment()` to pass arrays by reference. Used colon as field separator in scored results array with `tr ':' '-'` sanitization for titles/details. Test file sources the script directly (BASH_SOURCE guard enables this) rather than extracting functions.
- **Notes for sibling tasks:** The script follows the same platform backend pattern as `aitask_issue_import.sh` and `aitask_contribute.sh`. Platform dispatchers use `CHECK_PLATFORM` (not `SOURCE` like issue_import). The `BASH_SOURCE` guard on `main()` is essential for t355_6 (contribution-review skill) to source individual functions. All allowlist files must be kept in sync — 5 files total (seed: claude, opencode, gemini; active: claude, gemini).
