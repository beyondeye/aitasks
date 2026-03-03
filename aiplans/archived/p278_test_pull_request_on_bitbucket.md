---
Task: t278_test_pull_request_on_bitbucket.md
Worktree: (none — working on current branch)
Branch: (current)
Base branch: main
---

# Plan: Test PR import flow for Bitbucket

## Context

Task t260 implemented the PR import workflow for GitHub/GitLab/Bitbucket. Task t277 tested and fixed the GitLab flow end-to-end, revealing bugs and missing `--repo` flag support. This task performs the same e2e verification for Bitbucket using `eyebeyond/test_repo_bitbucket`.

The `bkt` CLI is installed, authenticated, and has context `testrepo` set to `eyebeyond/test_repo_bitbucket`. All `bkt` commands will use this context by default.

## Pre-flight: Verify bkt commands work

Before creating a PR, verify basic `bkt` commands work with the current context:
- `bkt pr list --json` — should return JSON (possibly empty list)
- Check if `bkt pr comment` uses `--text` flag (help says `--text`, but code uses `-b`)

Fix any issues found before proceeding.

## Step 1: Create a test PR in Bitbucket

- Clone `eyebeyond/test_repo_bitbucket` to `/tmp/test_repo_bitbucket`
- Create branch `test/pr-import-test` from `main`
- Modify README (add a line) and add a test file `test_change.md`
- Push branch
- Create PR with `bkt pr create --source test/pr-import-test --target main --title "Test PR for import flow verification" --description "..."`
- Add a comment on the PR: `bkt pr comment <NUM> --text "Test comment for import verification"`
- Record PR number

**Key files:** None modified — external repo operations.

## Step 2: Test `--list` mode

```bash
./aiscripts/aitask_pr_import.sh --batch --source bitbucket --list --silent
```

Expected: PR number and title appear in output.

**Note:** Since `bkt` uses context (not `--repo` override like glab), the list should work without `--repo` flag. The script calls `bkt pr list --json` directly.

## Step 3: Test `--data-only` mode

```bash
./aiscripts/aitask_pr_import.sh --batch --source bitbucket --pr <NUM> --data-only --silent
```

Verify `.aitask-pr-data/<NUM>.md` contains:
- Correct PR number and URL
- Correct contributor username
- Platform = bitbucket
- Description text present
- Comments section has the test comment
- Diff content present (or document limitation)

## Step 4: Test `aitask_pr_close.sh --dry-run`

```bash
./aiscripts/aitask_pr_close.sh --dry-run --pr-url "https://bitbucket.org/eyebeyond/test_repo_bitbucket/pull-requests/<NUM>" 278
```

Verify output format looks correct.

## Step 5: Fix any issues found

Based on t277 experience, potential issues:
- `bkt pr comment` flag: code uses `-b` but help shows `--text` — need to verify
- `bitbucket_fetch_pr_files()` returns empty string — may need to parse diff for file list
- Missing `--workspace`/`--repo` support for cross-repo operations (not blocking for this test since context is set, but worth noting)

Fix any bugs discovered during testing.

## Step 6: Cleanup

- Close/decline the test PR (ask user)
- Remove `/tmp/test_repo_bitbucket` clone

## Step 9: Post-Implementation

Archive task, push changes per standard workflow.

## Verification

All verification is inline — each step produces visible output checked against expected values. User confirms correctness at each step.

## Final Implementation Notes

- **Actual work done:** Created test PR #1 in `eyebeyond/test_repo_bitbucket`, ran all e2e test steps (`--list`, `--data-only`, `--dry-run` close, actual close/decline). Fixed 8 bugs in `aitask_pr_import.sh` and 3 bugs in `aitask_pr_close.sh`. All Bitbucket functions now work correctly with Bitbucket Cloud via the `bkt` CLI.
- **Deviations from plan:** More bugs found than anticipated. The `bkt` CLI wraps JSON output in container objects (`.pull_request`, `.pull_requests`) unlike the raw Bitbucket API. Several `bkt` subcommands (`pr diff`, `pr comment`) only support Data Center, requiring API fallbacks for Cloud. Had to set up SSH key for Bitbucket push access.
- **Issues encountered:**
  1. `bkt pr view --json` wraps data in `.pull_request` — all jq filters needed `.pull_request // .` unwrapping
  2. `bkt pr list --json` wraps in `.pull_requests` array — not `.values` as expected
  3. `bkt pr comment` is Data Center only — used `bkt api --method POST .../comments` with JSON input
  4. `bkt pr diff` is Data Center only — used `bkt api .../diff` endpoint
  5. `bitbucket_fetch_pr_files()` was empty — now uses diffstat API
  6. additions/deletions/changed_files hardcoded to 0 — now computed from diffstat API
  7. `bitbucket_resolve_contributor_email()` doubled emails (e.g., `email@bitbucket.org`) — now checks for `@` before appending
  8. No `--repo` flag support for Bitbucket — added `bitbucket_resolve_repo()` and `bkt_repo_args()` helpers
  9. Duplicate `## Description` header in data file — cosmetic, same as GitLab (t277)
  10. Auth token expired — user re-authenticated via `bkt auth login`
  11. SSH key needed for Bitbucket push — generated ed25519 key and user added it
- **Key decisions:**
  - Used `bkt api` for Cloud-only features (diff, comments) rather than raw `curl` — consistent with the CLI's auth handling
  - `bitbucket_resolve_repo()` reads from `REPO_OVERRIDE` first, falls back to active `bkt context`
  - `bkt_repo_args()` only emits `--workspace`/`--repo` flags when `REPO_OVERRIDE` is set (context handles default case)
  - In `aitask_pr_close.sh`, extract workspace/repo from the PR URL directly (no context dependency)
