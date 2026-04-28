---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [testing, bash_scripts]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-27 17:26
updated_at: 2026-04-28 09:43
boardidx: 50
---

The macOS audit (t658) baseline run revealed a substantial regression in `tests/test_pr_contributor_metadata.sh`: 14/30 assertions fail. Every failure has the same shape — `pull_request:`, `contributor:`, and `contributor_email:` fields are expected in the committed task file but are missing.

## Failure summary (from baseline log)

```
=== PR/Contributor Metadata Field Tests ===
--- Test 2: Create+commit with PR metadata ---
FAIL: pull_request in committed task (expected output containing 'pull_request: https://github.com/owner/repo/pull/99', got '')
FAIL: contributor in committed task (expected output containing 'contributor: contributor1', got '')
FAIL: contributor_email in committed task (expected output containing 'contributor_email: 789+contributor1@users.noreply.github.com', got '')
--- Test 4: Update task with PR fields ---
FAIL: pull_request after update (expected output containing 'pull_request: https://gitlab.com/group/project/-/merge_requests/5', got '')
... (similar across Tests 5, 6, 9, 10) ...
Results: 16 passed, 14 failed, 30 total
```

`actual: ''` on every failure means the field name is also absent from the output, not just the value — i.e., the field never gets written.

## Hypothesis

This is likely a real regression in `aitask_create.sh --pull-request` / `aitask_update.sh --pull-request --contributor --contributor-email` (or the equivalent flags) — they appear to no longer persist these fields to frontmatter. Since the test passes Test 1 (draft create) and Tests 7/8 (extraction functions) but fails the actual-frontmatter checks, the bug is probably in the write path of one of those scripts, not the parsing layer.

This test is **not** macOS-specific (the warnings about empty cloned repo also appear) — it would fail on Linux too. Out of scope for the macOS audit, but a real bug.

## Suggested approach

1. Pick one failing assertion (e.g. Test 2) and reproduce in isolation against the current `aitask_create.sh` and `aitask_update.sh`.
2. Trace where `--pull-request` / `--contributor` / `--contributor-email` flags get parsed and where they're supposed to be written to frontmatter.
3. Identify the regression commit (likely a refactor that dropped these fields from the write path).
4. Fix the write path; re-run the test until 30/30 assertions pass.

## Verification

`bash tests/test_pr_contributor_metadata.sh` reports `Results: 30 passed, 0 failed, 30 total`.
