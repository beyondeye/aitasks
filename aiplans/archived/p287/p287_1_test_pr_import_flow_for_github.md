---
Task: t287_1_test_pr_import_flow_for_github.md
Parent Task: aitasks/t287_test_task_from_pull_flow_for_github.md
Sibling Tasks: aitasks/t287/t287_2_*.md, aitasks/t287/t287_3_*.md
Archived Sibling Plans: aiplans/archived/p287/p287_*_*.md
Worktree: (none — working on current branch)
Branch: (current)
Base branch: main
---

# Plan: Test PR Import Flow for GitHub (t287_1)

## Context

Verify the GitHub backend of `aitask_pr_import.sh` works correctly using PR #1 in beyondeye/aitasks. This is the first step in the E2E verification of the task-from-pull-request flow for GitHub.

## Steps

### Step 1: Test `--list` mode

```bash
./aiscripts/aitask_pr_import.sh --batch --source github --list --silent
```

Expected: PR #1 appears with title "Update LICENSE reference in README.md".

### Step 2: Test `--data-only` mode

```bash
./aiscripts/aitask_pr_import.sh --batch --source github --pr 1 --data-only --silent
```

Verify `.aitask-pr-data/1.md` has all required fields with correct values.

### Step 3: Verify contributor email resolution

Check that `contributor_email` uses the correct GitHub noreply format.

### Step 4: User verification

Show output at each step, ask user to confirm.

## Step 9: Post-Implementation

Archive task, push changes.

## Final Implementation Notes

- **Actual work done:** Ran all three verification steps against PR #1 in beyondeye/aitasks. All checks passed with no issues found.
- **Step 1 (`--list`):** Output `1\tUpdate LICENSE reference in README.md` — correct.
- **Step 2 (`--data-only`):** All 14 frontmatter fields verified correct. Description, changed files, and diff sections all present and accurate. Notably, `additions: 1`, `deletions: 2`, `changed_files: 1` are all correct (unlike GitLab which had `additions: 0` / `deletions: 0` issues in t277_3).
- **Step 3 (email):** Resolved to `5619462+beyondeye@users.noreply.github.com` — correct noreply format with numeric ID.
- **Deviations from plan:** None. All commands worked as expected.
- **Issues encountered:** None. GitHub backend works correctly.
- **Notes for sibling tasks:**
  - The contributor email `5619462+beyondeye@users.noreply.github.com` should be used in t287_2 for verifying the `Co-authored-by` trailer format.
  - The `state` field value is `OPEN` (uppercase) in the data file — t287_2 should verify this is handled correctly in task creation.
  - `.aitask-pr-data/1.md` was cleaned up after verification. t287_2 will need to re-fetch or create its own data file.

## Verification

All verification is inline — each step produces visible output checked against expected values. All steps PASSED.
