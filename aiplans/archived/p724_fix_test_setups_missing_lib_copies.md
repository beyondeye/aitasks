---
Task: t724_fix_test_setups_missing_lib_copies.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan: Fix test setups missing lib/aitask_path.sh and lib/python_resolve.sh copies

## Context

Four `tests/test_*.sh` files have a `setup_*_project()` helper that copies `.aitask-scripts/aitask_verification_parse.sh` into a fixture directory but does NOT copy the two lib files that script sources at line 5 and line 7:

- `.aitask-scripts/lib/aitask_path.sh`
- `.aitask-scripts/lib/python_resolve.sh`

Confirmed failure signature in all four tests:
```
./.aitask-scripts/aitask_verification_parse.sh: line 5: <fixture>/.aitask-scripts/lib/aitask_path.sh: No such file or directory
```

The task description (t724) only flagged the two tests that surfaced during t723's regression sweep, but a focused audit of every test that copies `aitask_verification_parse.sh` found two more tests with the same live failure (not latent — they fail too).

**Current failure counts** (from running each test on `main`):

| Test | Failures | Total | `setup_*` line range |
|---|---|---|---|
| `tests/test_archive_verification_gate.sh` | 15 | 21 | `setup_archive_project()` 151–198, lib copies 175–179 |
| `tests/test_archive_carryover.sh` | 4 | 5 | `setup_archive_project()` 166–209, lib copies 188–192 |
| `tests/test_verification_followup.sh` | 14 | 21 | (helper) lib copies 94–97 |
| `tests/test_create_manual_verification.sh` | 4 | 7 | (helper) lib copies 94–97 |

The fix is the same 2-line append per file.

## Files to modify

1. `tests/test_archive_verification_gate.sh` — append 2 `cp` lines after line 179 (the `archive_utils.sh` copy)
2. `tests/test_archive_carryover.sh` — append 2 `cp` lines after line 192 (the `archive_utils.sh` copy)
3. `tests/test_verification_followup.sh` — append 2 `cp` lines after line 97 (the `archive_scan.sh` copy)
4. `tests/test_create_manual_verification.sh` — append 2 `cp` lines after line 97 (the `archive_scan.sh` copy)

## Implementation

In each of the four files, add these two lines into the lib-copy block (right after the existing lib `cp` lines):

```bash
cp "$PROJECT_DIR/.aitask-scripts/lib/aitask_path.sh" .aitask-scripts/lib/
cp "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh" .aitask-scripts/lib/
```

Match the existing indentation (4 spaces inside the function body). Do not add `2>/dev/null || true` — these libs are required, so a missing source file should fail loudly during fixture setup rather than masking the problem at test time.

## Verification

Run all four affected tests after the change:

```bash
bash tests/test_archive_verification_gate.sh
bash tests/test_archive_carryover.sh
bash tests/test_verification_followup.sh
bash tests/test_create_manual_verification.sh
```

Expected: each prints `ALL TESTS PASSED` (or equivalent 0-failure summary). Currently they print 15, 4, 14, and 4 failures respectively.

Also re-run the one passing test that already references `aitask_verification_parse.sh` to confirm no regression:

```bash
bash tests/test_python_resolution_fallback.sh
```

(It sets up its own minimal fixture that already includes the libs; should remain green.)

## Out of scope (intentional)

- **Helper extraction** (task description suggestion #3 — `_copy_framework_files()`): 31 tests in `tests/` duplicate their own `setup_*_project()` helper; centralizing is a separate refactor with much wider blast radius. Three similar lines is better than a premature abstraction. Note this in Final Implementation Notes as a candidate follow-up if duplication keeps biting.
- **Cp-vs-source linter** (task description suggestion #2): The Explore-agent audit done during planning already confirmed the 4 affected tests above are the complete set for `aitask_verification_parse.sh`. A general linter that catches this class of bug for ANY script is a separate task and would belong as a sibling refactor task, not bolted onto this fix.

## Step 9 (Post-Implementation)

After the changes pass review and the user approves, commit with the standard `<issue_type>: <description> (t724)` message format (issue_type=`bug`), then proceed to archival per the shared task-workflow Step 9.

## Final Implementation Notes

- **Actual work done:** Added two `cp` lines (`lib/aitask_path.sh`, `lib/python_resolve.sh`) to the lib-copy block of all four affected `tests/test_*.sh` files: `test_archive_verification_gate.sh` (after the `archive_utils.sh` line), `test_archive_carryover.sh` (same), `test_verification_followup.sh` (after `archive_scan.sh`), `test_create_manual_verification.sh` (same). +8 lines total, no other changes.
- **Deviations from plan:** None. Implementation matched the plan exactly.
- **Issues encountered:** None during implementation. During the planning audit (Phase 1 Explore agent + targeted runs), discovered that t724's task description undercounted the affected tests — it named only the two surfaced during t723's regression sweep, but `test_verification_followup.sh` (14 failures / 28 asserts) and `test_create_manual_verification.sh` (4 failures / 12 asserts) were also actively failing for the identical reason. All four were rolled into the same fix because the cure is mechanical and the audit was already done.
- **Key decisions:**
  - Did not add `2>/dev/null || true` to the new `cp` lines: the libs are required by `aitask_verification_parse.sh:5,7`, so a missing source file should fail loudly during fixture setup rather than masking the problem at test time. This matches the pattern used for required libs already in the block (`terminal_compat.sh`, `task_utils.sh`, `pid_anchor.sh`); only "optional" `archive_utils.sh` carries the silent-fallback.
  - Did NOT extract a shared `_copy_framework_files()` helper as suggested in the task description's fix point #3. 31 tests in `tests/` duplicate their own `setup_*_project()` helper — extraction has wide blast radius and belongs as a separate refactor task. Three similar lines is better than a premature abstraction.
  - Did NOT build a generic cp-vs-source linter (task description fix point #2). The Explore-agent audit already enumerated the complete set of affected tests for `aitask_verification_parse.sh`; a general linter for ANY script's source-graph is its own task.
- **Upstream defects identified:** None. The bug is entirely self-contained in the test setup helpers — `aitask_verification_parse.sh` and the lib files it sources are correct as-is. No defects in framework code surfaced during diagnosis.
- **Verification results:** After the fix, all four tests pass (34/34, 13/13, 28/28, 12/12 asserts). `test_python_resolution_fallback.sh` (the one passing test that already references `aitask_verification_parse.sh` because it bundles the libs in its own fixture) remained green.
- **Candidate follow-up (not filed):** If this class of bug bites a third time, consider opening a dedicated refactor task to extract a `tests/lib/copy_framework.sh` helper (or similar) that owns the canonical lib-copy list once. Not filed now per the "don't file vague follow-ups" feedback memory — wait for concrete recurrence with named affected tests.
