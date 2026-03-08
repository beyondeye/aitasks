---
Task: t321_5_contribute_testing.md
Parent Task: aitasks/t321_removeautoupdatefromdocsorimplement.md
Sibling Tasks: aitasks/t321/t321_1_*.md, aitasks/t321/t321_2_*.md, aitasks/t321/t321_3_*.md, aitasks/t321/t321_4_*.md
Worktree: (current directory)
Branch: (current branch)
Base branch: main
---

# Implementation Plan: t321_5 — Testing

## Overview

Create `tests/test_contribute.sh` — a self-contained test script for `aitask_contribute.sh`.

## Steps

### 1. Test scaffold

Follow `tests/test_claim_id.sh` pattern:
- `set -euo pipefail`
- `assert_eq()`, `assert_contains()` helpers
- `setup()` / `cleanup()` with `trap cleanup EXIT`
- PASS/FAIL counter and summary

### 2. Test environment setup

Create temp directory with:
- `.aitask-scripts/VERSION` file with test version
- `.aitask-scripts/lib/` with required library files (symlinked from real repo)
- `.aitask-scripts/aitask_contribute.sh` (symlinked from real repo)
- `AITASK_CONTRIBUTE_UPSTREAM_DIR` pointing to a temp "upstream" directory with reference files
- Mock git remote pointing to `beyondeye/aitasks` (for mode detection)

### 3. Test cases

1. **test_help** — `--help` exits 0
2. **test_list_areas** — `--list-areas` outputs expected area names
3. **test_arg_parsing** — valid batch args don't error
4. **test_missing_files_error** — missing `--files` dies with error
5. **test_missing_title_error** — missing `--title` dies with error
6. **test_dry_run_structure** — dry-run output contains required sections:
   - `## Contribution:`, `### Motivation`, `### Changed Files`, `### Code Changes`
   - `<!-- aitask-contribute-metadata` block
7. **test_list_changes** — files differing from upstream appear in `--list-changes` output
8. **test_large_diff_preview** — file with >50 line diff produces:
   - Preview truncated to 50 lines
   - `<!-- full-diff:` HTML comment with complete diff
   - Preview note text present
9. **test_small_diff_inline** — file with <50 line diff shows full diff directly (no HTML comment)
10. **test_contributor_metadata** — metadata block contains contributor and contributor_email
11. **test_mode_detection** — clone mode detected for beyondeye/aitasks remote

### 4. Upstream mock strategy

Set `AITASK_CONTRIBUTE_UPSTREAM_DIR=/tmp/test_upstream`:
- Create "upstream" versions of test files in this directory
- Create modified "local" versions in the test project
- The script reads from `AITASK_CONTRIBUTE_UPSTREAM_DIR` instead of calling `repo_fetch_file()`

## Key Files

- **Create:** `tests/test_contribute.sh`
- **Reference:** `tests/test_claim_id.sh` (test pattern)
- **Reference:** `.aitask-scripts/aitask_contribute.sh` (script under test)

## Verification

- `bash tests/test_contribute.sh` — all tests pass
- `shellcheck tests/test_contribute.sh` passes
- No network access during tests

## Final Implementation Notes

- **Actual work done:** No new code was needed — `tests/test_contribute.sh` was already fully implemented during t321_1 (per user request to include tests in that task). Verification confirmed all 11 planned test cases are present with 31 assertions, all passing.
- **Deviations from plan:** The test file uses `cp` instead of symlinks for script dependencies (more robust for temp directory isolation). Uses `set +e` after setup instead of `set -euo pipefail` throughout, to allow test error handling.
- **Issues encountered:** One minor shellcheck style warning (SC2129 — consecutive appends could use grouped redirect). Not functionally relevant.
- **Key decisions:** Task archived as-is since all work was completed in t321_1. No additional test cases were needed beyond the 11 originally planned.
- **Notes for sibling tasks:** All contribute-related tests are in `tests/test_contribute.sh`. The issue import contributor tests are separately in `tests/test_issue_import_contributor.sh` (created during t321_2).

## Step 9 Reference
Post-implementation: archive task via task-workflow Step 9.
