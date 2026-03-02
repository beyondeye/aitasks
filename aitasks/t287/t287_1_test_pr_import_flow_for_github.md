---
priority: high
effort: medium
depends: []
issue_type: test
status: Ready
labels: []
created_at: 2026-03-02 16:57
updated_at: 2026-03-02 16:57
---

## Context

Part of t287 (test task-from-pull-request flow for GitHub). This is the first child task, verifying that `aitask_pr_import.sh` correctly extracts PR data from GitHub using the `gh` CLI.

The GitLab equivalent (t277_3) tested the same flow and found issues with `additions: 0`/`deletions: 0` (GitLab API limitation) and a duplicate `## Description` header. This task verifies the GitHub backend has no similar issues.

**Test PR:** PR #1 in `beyondeye/aitasks` — "Update LICENSE reference in README.md" by beyondeye. Simple change: 1 addition, 2 deletions, 1 changed file. State: OPEN.

## Key Files to Modify

No code changes expected — this is a verification/testing task. If bugs are found, fixes would be in:
- `aiscripts/aitask_pr_import.sh` — GitHub backend functions (lines ~78-196)

## Reference Files for Patterns

- `aiplans/archived/p277/p277_3_create_test_mr_and_run_e2e_gitlab_import_test.md` — GitLab E2E test plan (follow same structure)
- `aitasks/archived/t277/t277_3_create_test_mr_and_run_e2e_gitlab_import_test.md` — GitLab E2E test task

## Implementation Plan

### Step 1: Test `--list` mode

```bash
./aiscripts/aitask_pr_import.sh --batch --source github --list --silent
```

Expected: PR #1 appears with title "Update LICENSE reference in README.md" and state "OPEN".

### Step 2: Test `--data-only` mode

```bash
./aiscripts/aitask_pr_import.sh --batch --source github --pr 1 --data-only --silent
```

Verify `.aitask-pr-data/1.md` contains:
- [ ] `pr_number: 1`
- [ ] `pr_url: https://github.com/beyondeye/aitasks/pull/1`
- [ ] `contributor: beyondeye`
- [ ] `contributor_email:` in format `<id>+beyondeye@users.noreply.github.com`
- [ ] `platform: github`
- [ ] `title: "Update LICENSE reference in README.md"`
- [ ] `state: open` (or `OPEN`)
- [ ] `base_branch: main`
- [ ] `head_branch: test_pull_request`
- [ ] `additions: 1`, `deletions: 2`, `changed_files: 1`
- [ ] Description text is present
- [ ] Diff content is present and shows the actual changes
- [ ] Changed files section lists the modified file

### Step 3: Verify contributor email resolution

The GitHub email should use format `<numeric_id>+beyondeye@users.noreply.github.com`. The script calls `gh api users/beyondeye` to get the numeric ID.

### Step 4: User verification

Show output at each step. Ask user to confirm correctness. Document any issues found.

## Verification

All verification is inline — each step produces visible output to check against expected values.
