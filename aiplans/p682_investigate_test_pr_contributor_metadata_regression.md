---
Task: t682_investigate_test_pr_contributor_metadata_regression.md
Worktree: (current branch — no worktree)
Branch: main
Base branch: main
---

## Context

Task t682 reports that `tests/test_pr_contributor_metadata.sh` fails 14/30 assertions, all with the same shape: `pull_request:`, `contributor:`, `contributor_email:` fields are expected but `actual: ''` — i.e. the field name is also absent. The task hypothesizes a real regression in `aitask_create.sh --pull-request` / `aitask_update.sh --pull-request --contributor --contributor-email` (the write paths dropping these fields).

**The hypothesis is wrong.** Investigation traced the failure to the test fixture, not production code:

- `aitask_create.sh` `create_task_file()` (line 1358) and `create_child_task_file()` (line 358) both serialize `pull_request`, `contributor`, `contributor_email` correctly when present (lines 1417–1425, 417–424).
- `aitask_update.sh` (lines 1461–1476, 488–495) correctly threads the values into the rewrite.
- Tests 1 and 3 (which do NOT use `--commit`) PASS — they exercise the same write path and confirm the fields are written for drafts.
- Tests 2, 4, 5, 6, 9, 10 (which DO use `--commit`) FAIL — these go through `aitask_claim_id.sh --claim` to obtain a real ID before writing.

Reproducing Test 2 with stderr unsuppressed reveals the actual error:

```
Error: Atomic ID counter failed: <tmp>/.aitask-scripts/aitask_claim_id.sh: line 26:
<tmp>/.aitask-scripts/lib/archive_scan.sh: No such file or directory.
Run 'ait setup' to initialize the counter.
```

`aitask_claim_id.sh:26` sources `lib/archive_scan.sh` (added during the t433_7 archive-v2 swap and the t470_1 tar.zst migration). The `setup_project()` function in `tests/test_pr_contributor_metadata.sh` was written before that and copies only `archive_utils.sh` — never `archive_scan.sh`. The `--init` and `--claim` invocations both fail with "No such file or directory", but the test redirects stderr to `/dev/null`, so the failure is silent. No task file is created, the assertion reads empty content, and 14 assertions fail.

Verified the fix locally by manually adding the missing copy: `Created: aitasks/t1_pr_committed.md` with all three fields present in the YAML frontmatter.

The production write paths are correct. This is a test-fixture-only fix.

## Out of scope (surface in Step 8b as upstream defects)

Other test files with the same gap (verified by grep for `cp .*archive_scan` next to `cp .*archive_utils`):

- `tests/test_data_branch_setup.sh` — copies neither archive_utils nor archive_scan
- `tests/test_data_branch_migration.sh` — copies archive_utils only
- `tests/test_issue_import_contributor.sh` — copies archive_utils only
- `tests/test_parallel_child_create.sh` — copies archive_utils only

Whether each of those tests actually invokes `aitask_claim_id.sh --claim` at runtime determines whether they are silently broken too. They are out of scope for t682 — surface as a separate upstream defect in the Final Implementation Notes.

## Implementation

Single-file change to `tests/test_pr_contributor_metadata.sh`.

In `setup_project()` (around line 73), after the existing line:

```bash
cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
```

add:

```bash
cp "$PROJECT_DIR/.aitask-scripts/lib/archive_scan.sh" .aitask-scripts/lib/
```

No other changes. Do NOT touch `aitask_create.sh`, `aitask_update.sh`, or any production code — they are correct.

## Verification

```bash
bash tests/test_pr_contributor_metadata.sh
```

Expected output:
```
Results: 30 passed, 0 failed, 30 total
ALL TESTS PASSED
```

(Existing baseline: 16 passed, 14 failed, 30 total.)

## Step 9: Post-Implementation

Standard archival flow — no separate worktree/branch was created (profile `fast`, working on `main`). Single test-file commit. Plan file commit via `./ait git`.
