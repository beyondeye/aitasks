---
priority: medium
effort: low
depends: []
issue_type: bug
status: Done
labels: [testing, bash_scripts]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-28 10:09
updated_at: 2026-04-28 11:01
completed_at: 2026-04-28 11:01
---

## Origin

Spawned from t682 during Step 8b review.

## Upstream defect

Four other test files in `tests/` have the same fixture gap that t682 fixed in `tests/test_pr_contributor_metadata.sh`: their `setup_project()` (or equivalent helper) copies a subset of `.aitask-scripts/lib/` into the test sandbox but omits `archive_scan.sh`, which `aitask_claim_id.sh:26` sources unconditionally. Tests using the `--commit`/claim path fail silently (stderr is suppressed in the test setup) and produce misleading assertion failures rather than a clear "missing dep" error.

- `tests/test_data_branch_setup.sh — setup helper invokes aitask_claim_id.sh but copies neither lib/archive_utils.sh nor lib/archive_scan.sh; likely silently broken with the same stderr-suppressed-claim-failure pattern as t682`
- `tests/test_data_branch_migration.sh — copies lib/archive_utils.sh but not lib/archive_scan.sh; likely silently broken if --commit / claim path is exercised`
- `tests/test_issue_import_contributor.sh — copies lib/archive_utils.sh but not lib/archive_scan.sh; likely silently broken if --commit / claim path is exercised`
- `tests/test_parallel_child_create.sh — copies lib/archive_utils.sh but not lib/archive_scan.sh; likely silently broken if --commit / claim path is exercised`

## Diagnostic context

t682 hypothesized "real regression in `aitask_create.sh --pull-request` / `aitask_update.sh ...` write paths". Investigation showed both scripts write `pull_request`, `contributor`, `contributor_email` correctly. The actual root cause was that `aitask_claim_id.sh:26` sources `lib/archive_scan.sh` (added in the t433_7 archive-v2 swap and t470_1 tar.zst migration), but the test's `setup_project()` was never updated to copy that file. With stderr suppressed via `2>/dev/null`, the missing-file error was invisible — assertions read empty content and produced 14 misleading "expected pull_request:..., got ''" failures.

This task generalizes that fix to every other test file with the same gap.

## Suggested fix

For each affected test file, locate its setup-project helper and ensure it copies BOTH `archive_utils.sh` AND `archive_scan.sh` (and possibly other lib files `aitask_claim_id.sh` transitively depends on — re-check by grepping `^source` in `aitask_claim_id.sh` and its sourced libs). After patching each helper, run the test from a clean shell with stderr unsuppressed to confirm `--commit`/claim now succeeds.

A more durable fix would refactor the test helpers to a single shared `tests/lib/setup_project.sh` so a future dependency change in `aitask_claim_id.sh` only needs one update — but that is out of scope for this bug ticket.

## Verification

For each of the four files, run:

```bash
bash tests/test_data_branch_setup.sh
bash tests/test_data_branch_migration.sh
bash tests/test_issue_import_contributor.sh
bash tests/test_parallel_child_create.sh
```

All four should report `ALL TESTS PASSED` (or whatever success marker each file uses) with no FAIL lines hidden by stderr suppression.
