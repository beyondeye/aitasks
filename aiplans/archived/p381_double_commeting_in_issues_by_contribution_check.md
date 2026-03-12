---
Task: t381_double_commeting_in_issues_by_contribution_check.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

## Context

The `contribution-check.yml` GitHub Actions workflow posts duplicate comments on contribution issues. Two separate causes:

1. **GitHub (primary bug):** The workflow triggers on both `opened` and `labeled` events. When the script adds auto-labels (line 778), those label additions fire new `labeled` events, re-triggering the workflow and posting a duplicate comment.

2. **All platforms (defense-in-depth):** The script `aitask_contribution_check.sh` has no idempotency — it always posts a new comment without checking if one already exists. This affects:
   - **GitHub**: double-trigger from auto-labels
   - **GitLab (scheduled mode)**: every 6-hour scan re-comments on all matching issues
   - **Bitbucket (scheduled mode)**: every scheduled run re-comments on all matching issues

## Fix

### Step 1: Fix GitHub workflow `if` condition

**Files:** Both contain the same `if` condition — the seed file has extra comment lines at the top shifting line numbers:
- `.github/workflows/contribution-check.yml` (line 13)
- `seed/ci/github/contribution-check.yml` (line 18)

Change the `if` condition in both to distinguish between `opened` and `labeled` events:

```yaml
if: >-
  (github.event.action == 'opened' && contains(github.event.issue.labels.*.name, 'contribution')) ||
  (github.event.action == 'labeled' && github.event.label.name == 'contribution')
```

- **`opened`**: Run if the issue has the `contribution` label (same as before)
- **`labeled`**: Only run when the `contribution` label itself was just added — not when the script adds auto-labels

### Step 2: Add idempotency check to `aitask_contribution_check.sh`

Added platform-specific `*_has_overlap_comment()` functions (GitHub, GitLab, Bitbucket) plus `source_has_overlap_comment()` dispatcher. Each checks existing issue comments for the `<!-- overlap-results` HTML marker.

Both comment-posting paths in `main()` now check for existing comments before posting:
- No-fingerprint path (line ~741)
- Normal overlap analysis path (line ~810)

### Step 3: Tests

Added 4 idempotency tests (Tests 16-19) to `tests/test_contribution_check.sh`:
- Test 16: Detects existing overlap comment
- Test 17: Returns false when no overlap comment present
- Test 18: Returns false for empty comments
- Test 19: Dispatcher routes to correct platform backend

## Files Modified

1. `.github/workflows/contribution-check.yml` — fix `if` condition
2. `seed/ci/github/contribution-check.yml` — fix `if` condition
3. `.aitask-scripts/aitask_contribution_check.sh` — add `*_has_overlap_comment()` functions + idempotency check in `main()`
4. `tests/test_contribution_check.sh` — 4 new idempotency tests

## Final Implementation Notes

- **Actual work done:** Fixed the GitHub workflow double-trigger and added idempotency to the contribution check script for all platforms (GitHub, GitLab, Bitbucket)
- **Deviations from plan:** Used `*_has_overlap_comment()` (boolean) functions instead of `*_find_overlap_comment()` (returning IDs) since we only need to check existence, not update. Simpler and less code.
- **Issues encountered (initial fix insufficient):** The first fix distinguished `opened` vs `labeled` events in the `if` condition, but this was not enough. GitHub fires **both** `opened` and `labeled` events simultaneously when an issue is created with a label already attached. Both conditions matched, so two workflow runs still triggered at the exact same second — and the idempotency check couldn't help either since both runs started before either posted a comment.
- **Corrected fix:** Removed `opened` from the trigger entirely (`types: [labeled]` only) and simplified the condition to `github.event.label.name == 'contribution'`. This works because GitHub fires a `labeled` event for each label applied at issue creation time, so `labeled` alone covers both "new issue with contribution label" and "contribution label added to existing issue". The idempotency check in the script remains as defense-in-depth for GitLab/Bitbucket scheduled runs.
- **Key lesson:** GitHub Actions fires `opened` + `labeled` simultaneously for issues created with labels. Never use both trigger types if you only want one run per issue — use `labeled` alone when label presence is the real trigger.
