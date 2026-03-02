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

## Verification

User confirms task metadata and attribution format at each step.
