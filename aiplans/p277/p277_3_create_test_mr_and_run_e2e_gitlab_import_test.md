---
Task: t277_3_create_test_mr_and_run_e2e_gitlab_import_test.md
Parent Task: aitasks/t277_test_pull_request_import_for_gitlab.md
Sibling Tasks: aitasks/t277/t277_1_*.md, aitasks/t277/t277_2_*.md
Archived Sibling Plans: aiplans/archived/p277/p277_1_*.md, aiplans/archived/p277/p277_2_*.md
Worktree: (none — working on current branch)
Branch: (current)
Base branch: main
---

# Plan: Create test MR and run end-to-end GitLab import test

## Context

After t277_1 (bug fixes + --repo flag) and t277_2 (repo support in close/update scripts), this task performs the actual end-to-end verification using a real GitLab MR in `beyondeye/testrepo_gitlab`.

This is an interactive task — user participation needed for MR creation and result verification.

## Steps

### Step 1: Create test MR in GitLab

- Clone `beyondeye/testrepo_gitlab` to `/tmp/testrepo_gitlab`
- Create branch `test/pr-import-test` from `master` (default branch)
- Add a test file, modify an existing file
- Push and create MR with `glab mr create -R beyondeye/testrepo_gitlab`
- Add a comment on the MR: `glab mr note <NUM> -R beyondeye/testrepo_gitlab -m "Test comment"`
- Record MR number

### Step 2: Test `--list` mode

```bash
./aiscripts/aitask_pr_import.sh --batch --source gitlab --repo beyondeye/testrepo_gitlab --list --silent
```
Expected: MR number and title appear in output.

### Step 3: Test `--data-only` mode

```bash
./aiscripts/aitask_pr_import.sh --batch --source gitlab --repo beyondeye/testrepo_gitlab --pr <NUM> --data-only --silent
```
Verify `.aitask-pr-data/<NUM>.md` for correct: pr_number, pr_url, contributor, platform=gitlab, description, comments, files, diff.

### Step 4: Test `aitask_pr_close.sh --dry-run`

```bash
./aiscripts/aitask_pr_close.sh --dry-run --pr-url "https://gitlab.com/beyondeye/testrepo_gitlab/-/merge_requests/<NUM>" 277
```
Verify output format looks correct.

### Step 5: User verification at each step

Ask user to confirm output at each step. Fix any issues found.

### Step 6: Cleanup

- Close MR or leave for future testing (ask user)
- Remove `/tmp/testrepo_gitlab` clone

## Step 9: Post-Implementation

Archive task, push changes.

## Verification

All verification is inline — each step produces visible output checked against expected values.

## Final Implementation Notes

- **Actual work done:** Created MR #1 in `beyondeye/testrepo_gitlab` with a feature branch (`test/pr-import-test`), test file, and a comment. Ran all 4 e2e test steps: `--list` returned correct MR number+title, `--data-only` produced correct `.aitask-pr-data/1.md` with all fields populated, `--dry-run` close showed correct comment body and action. All tests passed. MR was closed and local clone cleaned up.
- **Deviations from plan:** None — all steps executed as planned.
- **Issues encountered:** (1) `additions: 0` / `deletions: 0` in the data file is a known GitLab API limitation (documented in t277_1). Per-file counts (`README.md +2 -0`, `test_change.md +9 -0`) are computed correctly. (2) The `## Description` header appears twice in the data file — the script adds it, and the MR body already starts with `## Description`. This is cosmetic and does not affect functionality.
- **Notes for sibling tasks:** The full GitLab cross-repo import flow is verified end-to-end. All helper functions (`glab_repo_args()`, `glab_api_project_path()`, `gitlab_extract_repo_from_url()`, `glab_repo_flag()`) work correctly with the `-R` flag pattern. The `glab` CLI at `/usr/bin/glab` handles cross-repo operations without needing to be in a GitLab-cloned directory.
