---
priority: high
effort: medium
depends: [t287_1]
issue_type: test
status: Ready
labels: []
created_at: 2026-03-02 16:57
updated_at: 2026-03-02 16:57
---

## Context

Part of t287 (test task-from-pull-request flow for GitHub). This is the second child task, verifying that `aitask_pr_import.sh` can create a full task file from a GitHub PR with correct contributor metadata, and that the Contributor Attribution Procedure produces the correct `Co-authored-by` trailer format.

Depends on t287_1 (PR import data verification must pass first).

**Test PR:** PR #1 in `beyondeye/aitasks` — "Update LICENSE reference in README.md" by beyondeye.

## Key Files to Modify

No code changes expected — this is a verification/testing task. If bugs are found, fixes would be in:
- `aiscripts/aitask_pr_import.sh` — task creation from PR data

## Reference Files for Patterns

- `.claude/skills/task-workflow/procedures.md` — Contributor Attribution Procedure (defines expected commit format)
- `aiscripts/aitask_pr_import.sh` — `github_resolve_contributor_email()` function

## Implementation Plan

### Step 1: Create a task from PR #1

```bash
./aiscripts/aitask_pr_import.sh --batch --source github --pr 1 --priority low --effort low --type chore --status Ready --silent
```

### Step 2: Verify task file metadata

Read the created task file and verify:
- [ ] `pull_request: https://github.com/beyondeye/aitasks/pull/1`
- [ ] `contributor: beyondeye`
- [ ] `contributor_email: <id>+beyondeye@users.noreply.github.com`
- [ ] Task description includes PR title and body text
- [ ] Priority, effort, type match the flags

### Step 3: Verify contributor attribution format

Simulate the Contributor Attribution Procedure:
- Read `contributor` and `contributor_email` from the task
- Verify the expected commit message would be:
  ```
  chore: <description> (t<N>)

  Based on PR: https://github.com/beyondeye/aitasks/pull/1

  Co-authored-by: beyondeye <<id>+beyondeye@users.noreply.github.com>
  ```

### Step 4: Clean up

Delete the test task file created in Step 1 (it's just for testing, not a real task).

## Verification

User confirms task metadata and attribution format are correct at each step.
