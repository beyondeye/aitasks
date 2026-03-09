---
Task: t354_contribute_fail_because_of_missing_label.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: Fix missing "contribution" label failure in aitask_contribute.sh

## Context

The `aitask_contribute` skill fails when creating issues because the "contribution" label is hardcoded in `github_create_issue()` and `gitlab_create_issue()`, but may not exist on the target repository. Two problems:
1. All repo interaction should be encapsulated in the script — the AI agent shouldn't have to manually create labels
2. Creating labels requires admin permissions — normal contributors can't do it

## Approach: Try-with-label, retry-without-label

- Try creating the issue with `--label "contribution"` first
- If it fails, retry without the label and warn the user
- Do NOT attempt to create the label (requires elevated permissions)
- Add `--no-label` CLI flag to skip labels entirely

## Changes

**File: `.aitask-scripts/aitask_contribute.sh`**

1. Add `ARG_NO_LABEL=false` batch variable
2. Rewrite `github_create_issue()` with try-with-label/retry-without-label logic
3. Rewrite `gitlab_create_issue()` with same retry logic
4. Update `bitbucket_create_issue()` to accept 4th param (uniform interface)
5. Update `source_create_issue()` to pass `no_label` flag through
6. Rewrite `create_issue()` with error handling and `ARG_NO_LABEL` pass-through
7. Add `--no-label` to `parse_args()` and `show_help()`

**File: `tests/test_contribute.sh`**

8. Test 36: `--no-label` flag accepted in dry-run
9. Test 37: Help output includes `--no-label`

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned — try-with-label/retry-without pattern in platform functions, `--no-label` CLI flag, error handling in `create_issue()`, plus 2 new tests.
- **Deviations from plan:** None.
- **Issues encountered:** None — straightforward implementation.
- **Key decisions:** Retry logic placed in platform-specific functions (not the wrapper) since each platform has different CLI syntax. `warn()` used for label-skip notification since it goes to stderr and is visible even in `--silent` mode.
