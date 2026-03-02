---
priority: high
effort: medium
depends: [t287_2]
issue_type: test
status: Implementing
labels: []
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-02 16:57
updated_at: 2026-03-02 19:43
---

## Context

Part of t287 (test task-from-pull-request flow for GitHub). This is the third child task, verifying that `aitask_pr_close.sh` correctly generates close comments and executes close actions for GitHub PRs.

Depends on t287_2 (task creation must work first, since close references task commits and plans).

**Test PR:** PR #1 in `beyondeye/aitasks` — "Update LICENSE reference in README.md" by beyondeye.

## Key Files to Modify

No code changes expected — this is a verification/testing task. If bugs are found, fixes would be in:
- `aiscripts/aitask_pr_close.sh` — GitHub backend functions

## Reference Files for Patterns

- `aiplans/archived/p277/p277_3_create_test_mr_and_run_e2e_gitlab_import_test.md` — GitLab E2E test (Step 4 tested close flow)
- `aiscripts/aitask_pr_close.sh` — GitHub backend: `github_close_pr()`, `github_post_comment()`, `github_get_pr_state()`

## Implementation Plan

### Step 1: Test dry-run close

```bash
./aiscripts/aitask_pr_close.sh --dry-run --pr-url "https://github.com/beyondeye/aitasks/pull/1" 287
```

Verify output:
- [ ] Comment body format is correct (includes "Resolved via aitask" header)
- [ ] Implementation notes section is present (from plan file if available)
- [ ] Associated commits section lists relevant commits
- [ ] Contributor mention (@beyondeye) is included
- [ ] `gh pr close` command would be generated correctly

### Step 2: User decides on actual close

Ask user:
- "Actually close PR #1?" → If yes, run without `--dry-run`
- "Leave open for future testing?" → Skip actual close

### Step 3: If closing, verify on GitHub

If user chose to close:
- Verify comment was posted on GitHub PR
- Verify PR state changed to CLOSED

## Verification

User confirms dry-run output format at each step. If actual close is performed, verify on GitHub web UI.
