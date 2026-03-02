---
Task: t287_2_test_task_creation_and_contributor_attribution.md
Parent Task: aitasks/t287_test_task_from_pull_flow_for_github.md
Sibling Tasks: aitasks/t287/t287_1_*.md, aitasks/t287/t287_3_*.md
Archived Sibling Plans: aiplans/archived/p287/p287_*_*.md
Worktree: (none — working on current branch)
Branch: (current)
Base branch: main
---

# Plan: Test Task Creation and Contributor Attribution (t287_2)

## Context

Verify that `aitask_pr_import.sh` creates a full task file from a GitHub PR with correct contributor metadata, and that the Contributor Attribution Procedure produces the correct `Co-authored-by` format.

## Steps

### Step 1: Create task from PR #1

```bash
./aiscripts/aitask_pr_import.sh --batch --source github --pr 1 --priority low --effort low --type chore --status Ready --silent
```

### Step 2: Verify task file metadata

Read created task file. Check `pull_request`, `contributor`, `contributor_email` fields.

### Step 3: Verify contributor attribution format

Simulate the procedure and verify the expected multi-line commit message format.

### Step 4: Clean up

Delete the test task file.

## Step 9: Post-Implementation

Archive task, push changes.

## Final Implementation Notes

- **Actual work done:** Ran all four verification steps against PR #1 in beyondeye/aitasks. All checks passed with no issues found.
- **Step 1 (Create task):** `aitask_pr_import.sh --batch --source github` created draft task file `draft_20260302_1939_update_license_reference_in_readmemd.md` successfully. Draft was read directly for metadata verification (finalize not needed for testing).
- **Step 2 (Verify metadata):** All 9 frontmatter fields verified correct:
  - `pull_request: https://github.com/beyondeye/aitasks/pull/1` — correct
  - `contributor: beyondeye` — correct
  - `contributor_email: 5619462+beyondeye@users.noreply.github.com` — correct (matches p287_1 findings)
  - `priority: low`, `effort: low`, `issue_type: chore`, `status: Ready` — all match flags
  - Description includes PR title ("Update LICENSE reference in README.md") and body text
- **Step 3 (Verify attribution format):** Confirmed the Contributor Attribution Procedure (procedures.md) produces the correct multi-line commit format with `Co-authored-by: beyondeye <5619462+beyondeye@users.noreply.github.com>` trailer.
- **Step 4 (Clean up):** Test draft file deleted.
- **Deviations from plan:** Minor — used draft file directly instead of finalizing to a numbered task, since finalize requires interactive mode and metadata verification doesn't need a task number.
- **Issues encountered:** None. GitHub PR import and task creation work correctly end-to-end.
- **Notes for sibling tasks:**
  - The full task creation pipeline (import → draft → metadata) works correctly for GitHub.
  - t287_3 (PR close flow) can rely on the task creation working correctly — the contributor metadata is properly populated.
  - The `Co-authored-by` format with numeric GitHub user ID prefix (`5619462+beyondeye`) is correctly resolved and stored.

## Verification

All verification is inline — each step's output was checked against expected values. All steps PASSED.
