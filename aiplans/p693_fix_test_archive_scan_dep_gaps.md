---
Task: t693_fix_test_archive_scan_dep_gaps.md
Worktree: (none — current branch per `fast` profile)
Branch: main
Base branch: main
---

# Plan for t693 — Generalize archive_scan.sh fixture fix

## Context

t682 fixed `tests/test_pr_contributor_metadata.sh`'s `setup_project()` by adding a missing `cp` of `lib/archive_scan.sh` into the test sandbox — the fixture had been silently broken since `aitask_claim_id.sh:26` started sourcing `lib/archive_scan.sh` (added in t433_7 / t470_1). With stderr suppressed via `2>/dev/null` in test invocations, the missing file produced empty output and misleading assertion failures rather than a clear error.

t693 is the cleanup task to generalize that same fix to four other test files flagged in t682's review.

## Investigation findings (deviations from task description)

End-to-end repro under `/tmp/t693_repro` confirmed the underlying defect: with only `archive_utils.sh` copied (and not `archive_scan.sh`), `aitask_create.sh --commit` fails with:

```
Error: Atomic ID counter failed: .../aitask_claim_id.sh: line 26: .../lib/archive_scan.sh: No such file or directory.
```

Per-file status against the task description's claims:

| File | Task description claim | Actual status |
|------|------------------------|---------------|
| `tests/test_data_branch_setup.sh` | "copies neither archive_utils.sh nor archive_scan.sh" | **Already correct.** Test 11 (line 504) uses `cp -r .aitask-scripts/lib`, which copies the entire `lib/` directory. All 51 tests pass. **No change needed.** |
| `tests/test_data_branch_migration.sh` | "copies archive_utils.sh but not archive_scan.sh" | **Confirmed gap. Currently failing.** Test 5 (`aitask_create.sh --batch --commit`) silently fails because `set -e` is honored in the parent shell; only Tests 1–4 ever run. |
| `tests/test_issue_import_contributor.sh` | "copies archive_utils.sh but not archive_scan.sh" | **Latent gap.** Setup copies `aitask_claim_id.sh` but Tests 5/6 only create *drafts* (no `--commit`), so the atomic counter is not invoked. All 58 pass today. Future `--commit`-style tests would break — fix defensively. |
| `tests/test_parallel_child_create.sh` | "copies archive_utils.sh but not archive_scan.sh" | **Latent gap.** Setup copies `aitask_claim_id.sh` but child creation uses `get_next_child_number` (local sibling scan, see `aitask_create.sh:1545`), not the atomic counter — so all 21 tests pass today. Future parent-creation tests would break — fix defensively. |

Source-of-truth dep chain (from t682): `aitask_claim_id.sh:26` sources `lib/archive_scan.sh`, which sources both `lib/terminal_compat.sh` and `lib/archive_utils.sh`. Sandbox fixtures must therefore include all three lib files alongside any copy of `aitask_claim_id.sh`.

## Implementation

### Change 1 — `tests/test_data_branch_migration.sh` (real fix)

Insert one new `cp` line in `setup_migrated_project()` immediately after the existing `archive_utils.sh` copy at line 115:

```bash
        cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/lib/archive_scan.sh" .aitask-scripts/lib/   # NEW
```

### Change 2 — `tests/test_issue_import_contributor.sh` (defensive)

Same one-line addition in `setup_project()` after line 92:

```bash
        cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/lib/archive_scan.sh" .aitask-scripts/lib/   # NEW
```

### Change 3 — `tests/test_parallel_child_create.sh` (defensive)

Same one-line addition in `setup_test_repo()` after line 80:

```bash
        cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/lib/archive_scan.sh" .aitask-scripts/lib/   # NEW
```

### No change to `tests/test_data_branch_setup.sh`

The file already uses `cp -r .aitask-scripts/lib` which is dependency-set-agnostic. Add a brief Final Implementation Note recording this so future readers don't waste time hunting for the gap.

## Verification

Run each test file from a clean shell **without** stderr suppression to confirm the fix and detect any new regressions:

```bash
bash tests/test_data_branch_migration.sh        # was failing at Test 5; should now reach Test 7 / "ALL TESTS PASSED"
bash tests/test_issue_import_contributor.sh     # was 58/58; should remain 58/58
bash tests/test_parallel_child_create.sh        # was 21/21; should remain 21/21
bash tests/test_data_branch_setup.sh            # was 51/51; should remain 51/51 (sanity, no edits)
```

Pre-fix baseline already captured (see Investigation): `test_data_branch_migration.sh` aborts mid-run with exit code 1 after Test 4. Post-fix it must complete with `ALL TESTS PASSED` (or equivalent).

## Out of scope

- Refactoring the four duplicate `setup_project*` helpers into a shared `tests/lib/setup_project.sh` (mentioned by t682 as the durable fix). Keep that as a separate future task — it changes the test architecture rather than just plugging known gaps.
- Adjusting `aitask_create.sh`/`aitask_claim_id.sh` to suppress the missing-file failure modes more loudly. The fixture fix is the right layer.

## Step 9 reminder

Per task-workflow Step 9, after Step 8 commits land:
- No worktree to remove (profile `fast` keeps current branch).
- Run `verify_build` from `aitasks/metadata/project_config.yaml` if configured.
- Archive task with `./.aitask-scripts/aitask_archive.sh 693`.

## Final Implementation Notes

- **Actual work done:** Added a single `cp "$PROJECT_DIR/.aitask-scripts/lib/archive_scan.sh" .aitask-scripts/lib/` line to the setup helpers in three test files: `tests/test_data_branch_migration.sh` (`setup_migrated_project`), `tests/test_issue_import_contributor.sh` (`setup_project`), and `tests/test_parallel_child_create.sh` (`setup_test_repo`). Inserted immediately after the existing `archive_utils.sh` copy in each helper. No code changes elsewhere.
- **Deviations from plan:** None for the three edits. Confirmed the plan's per-file analysis was correct: `tests/test_data_branch_setup.sh` was a false alarm in the original task description — its Test 11 setup uses `cp -r .aitask-scripts/lib`, which is dependency-set-agnostic, so no edit was needed there.
- **Issues encountered:** `tests/test_data_branch_migration.sh` was silently aborting at Test 5 because `set -e` (line 5) was honored in the parent shell — `set +euo pipefail` (line 182) only applied inside the `setup_migrated_project()` subshell invoked via `$(...)`, not in the global script scope. The aborting failure mode was only visible by running the test and observing it never printed past `--- Test 5 ---`. After the fix the file completes 21/21 (Tests 5–7 included).
- **Key decisions:**
  - Kept the fix minimal — one `cp` line per file, inserted at the same position pattern as t682's fix to `test_pr_contributor_metadata.sh`. No refactor toward a shared `tests/lib/setup_project.sh` helper (out of scope; left as future work in plan).
  - Applied the fix defensively to two test files (`test_issue_import_contributor.sh`, `test_parallel_child_create.sh`) that don't currently exercise the failing code path. Rationale: these helpers already copy `aitask_claim_id.sh`, so the dep-set should be complete and forward-compatible; the marginal cost is one line per file.
- **Upstream defects identified:** None.
- **Verification:** Ran each of the four target test files post-edit. Results: `test_data_branch_migration.sh` 21/21 (was aborting at Test 5), `test_issue_import_contributor.sh` 58/58, `test_parallel_child_create.sh` 21/21, `test_data_branch_setup.sh` 51/51 (sanity, no edits). No regressions.
