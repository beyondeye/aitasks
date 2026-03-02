---
priority: medium
effort: medium
depends: [t277_2]
issue_type: test
status: Ready
labels: []
created_at: 2026-03-02 15:46
updated_at: 2026-03-02 15:46
---

## Context

After t277_1 (fix import bugs + add --repo flag) and t277_2 (add repo support to close/update scripts), this task performs the actual end-to-end testing of the GitLab PR import flow.

This is an interactive task — requires user participation for creating the MR and verifying results on GitLab.

## Key Steps

### 1. Create a test MR in GitLab

- Clone `beyondeye/testrepo_gitlab` to `/tmp/testrepo_gitlab` (if not already cloned)
- Create a feature branch `test/pr-import-test` 
- Add a test file (e.g., `test_change.md`) with some content
- Modify an existing file (e.g., add a line to README.md)
- Push the branch
- Create an MR with:
  - Title: "Test PR for import flow verification"
  - Description with multiple paragraphs
  - Labels (if available in the repo)
- After MR creation, add a comment on the MR
- Note the MR number

### 2. Test `aitask_pr_import.sh` with `--data-only`

```bash
./aiscripts/aitask_pr_import.sh --batch --source gitlab --repo beyondeye/testrepo_gitlab --pr <MR_NUM> --data-only --silent
```

Verify `.aitask-pr-data/<MR_NUM>.md` contains:
- [ ] Correct MR number and URL
- [ ] Correct contributor username and email
- [ ] Platform is `gitlab`
- [ ] State is correct (opened/merged)
- [ ] Description text is present
- [ ] Comments section has the test comment
- [ ] Changed files list is accurate (not empty)
- [ ] Diff content is present

### 3. Test `aitask_pr_import.sh` with `--list`

```bash
./aiscripts/aitask_pr_import.sh --batch --source gitlab --repo beyondeye/testrepo_gitlab --list --silent
```

Verify the output lists the test MR.

### 4. Test `aitask_pr_close.sh` with `--dry-run`

```bash
./aiscripts/aitask_pr_close.sh --dry-run --pr-url "https://gitlab.com/beyondeye/testrepo_gitlab/-/merge_requests/<MR_NUM>" 277
```

Verify the dry-run output looks correct (comment body, close action).

### 5. Ask user to verify results

At each step, show the output to the user and ask them to confirm it looks correct or if there are issues to fix.

### 6. Cleanup

- Close the test MR on GitLab (or leave it for future testing)
- Remove the clone from `/tmp/testrepo_gitlab`

## Verification

All verification is inline — each step produces visible output that should be checked against expected values. The user will confirm correctness interactively.
