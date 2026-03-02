---
Task: t287_3_test_pr_close_flow_for_github.md
Parent Task: aitasks/t287_test_task_from_pull_flow_for_github.md
Sibling Tasks: aitasks/t287/t287_1_*.md, aitasks/t287/t287_2_*.md
Archived Sibling Plans: aiplans/archived/p287/p287_*_*.md
Worktree: (none — working on current branch)
Branch: (current)
Base branch: main
---

# Plan: Test PR Close Flow for GitHub (t287_3)

## Context

Verify that `aitask_pr_close.sh` correctly generates close comments and executes close actions for GitHub PRs using the `gh` CLI.

## Steps

### Step 1: Test dry-run close

```bash
./aiscripts/aitask_pr_close.sh --dry-run --pr-url "https://github.com/beyondeye/aitasks/pull/1" 287
```

Verify comment body format and `gh pr close` command generation.

### Step 2: User decides on actual close

Ask user whether to actually close PR #1 or leave open for future testing.

### Step 3: If closing, verify on GitHub

Check comment posted and PR state changed.

## Step 9: Post-Implementation

Archive task, push changes.

## Verification

User confirms dry-run output format. If actual close, verify on GitHub web UI.
