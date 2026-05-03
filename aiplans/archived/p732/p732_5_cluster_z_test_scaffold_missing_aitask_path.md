---
Task: t732_5_cluster_z_test_scaffold_missing_aitask_path.md
Parent Task: aitasks/t732_fix_failing_pre_existing_test_suite.md
Sibling Tasks: aitasks/t732/t732_*.md
Archived Sibling Plans: aiplans/archived/p732/p732_*.md
Worktree: (current branch — fast profile sets create_worktree:false)
Branch: (current branch)
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-03 18:49
---

# p732_5 — Cluster Z: Test scaffolds missing aitask_path.sh

## Goal

Make the 4 failing tests pass by adding `cp aitask_path.sh` to each test's scaffold block (Strategy 1 — minimal patch). The broader helper-extraction + 55-test convergence (Strategy 2-full from the original child task description) is **out of scope here** and is captured as a separate follow-up task created in Step 4 below.

## Verify-mode decision (this run)

User confirmed Strategy 1 over Strategy 2 because:
- 51 of the 55 affected tests pass today — the helper port is preventive infrastructure, not part of the bug fix.
- CLAUDE.md "Don't add features, refactor, or introduce abstractions beyond what the task requires" applies.
- The follow-up task preserves the helper extraction as in-scope work (per the "Plan split: in-scope children, not deferred follow-ups" memory) but as its own task with its own scope, not buried as an out-of-scope footnote here.

## Single root cause (confirmed)

`lib/aitask_path.sh` was added by t695_3 (Apr 28) and is now sourced unconditionally on `./ait` line 7 and from many helper scripts. The 4 failing tests scaffold a fake `.aitask-scripts/lib/` and don't copy `aitask_path.sh`; they crash because they invoke `./ait` or scripts that source it.

## Confirmed failures (today)

All 4 share the error pattern `… line N: <scratch>/.aitask-scripts/lib/aitask_path.sh: No such file or directory`:
- `tests/test_task_push.sh` (./ait git ...)
- `tests/test_brainstorm_cli.sh` (aitask_brainstorm_init.sh line 15)
- `tests/test_explain_context.sh` (aitask_explain_context.sh line 11)
- `tests/test_migrate_archives.sh` (./ait migrate-archives)

## Scaffold locations identified during verification

- `tests/test_task_push.sh` — TWO scaffold blocks at lines 288-291 + 316-319 (two fake repos in one test). Both need the `cp aitask_path.sh` line.
- `tests/test_brainstorm_cli.sh` — single block starting at line 92 (line 96 is the first `cp` after `mkdir`).
- `tests/test_explain_context.sh` — `mkdir` at line 81; `cp` block follows. Needs the `cp` line added in that block.
- `tests/test_migrate_archives.sh` — single block at line 80 (line 85 is the first `cp` after `mkdir`).

## Steps

1. For each of the 4 failing tests, add this line in the scaffold block (next to the existing `cp .../terminal_compat.sh` line):
   ```bash
   cp "$PROJECT_DIR/.aitask-scripts/lib/aitask_path.sh" "$repo_dir/.aitask-scripts/lib/"
   ```
   (Adjust the destination — some tests use `.aitask-scripts/lib/` relative, others use `$repo_dir/.aitask-scripts/lib/` — match the surrounding style.)
   Note `test_task_push.sh` has two scaffold blocks; both need the line.
2. Run the 4 failing tests one by one to confirm they pass:
   ```bash
   bash tests/test_task_push.sh && \
     bash tests/test_brainstorm_cli.sh && \
     bash tests/test_explain_context.sh && \
     bash tests/test_migrate_archives.sh
   ```
3. Sanity-check no nearby test regressed:
   ```bash
   for t in tests/test_brainstorm*.sh tests/test_explain*.sh tests/test_migrate*.sh tests/test_task_push.sh; do
     bash "$t" >/dev/null 2>&1 || echo "FAIL: $t"
   done
   ```
4. **Create a follow-up task** for the helper extraction work (Strategy 2-full). Use `aitask_create.sh --batch` per the **Batch Task Creation Procedure**. The follow-up task should:
   - Reference t732_5 as origin context.
   - Specify the helper extraction (`tests/lib/test_scaffold.sh` with `setup_fake_aitask_repo()`).
   - Specify the convergence of all 55 affected tests (inventory query in body).
   - Note the regression-test loop required.
   - Be a standalone parent task (NOT a child of t732 — t732's scope is just the 13 originally-failing tests).

## Verification

- Originally-failing 4 tests pass: `for t in tests/test_task_push.sh tests/test_brainstorm_cli.sh tests/test_explain_context.sh tests/test_migrate_archives.sh; do bash "$t" || break; done`.
- No regressions in the same-area tests (Step 3 above).
- New follow-up task exists in `aitasks/` with the helper-extraction scope.

## Step 9

Archive via `./.aitask-scripts/aitask_archive.sh 732_5`.

## Final Implementation Notes

- **Actual work done:** Added `cp aitask_path.sh` to the 4 originally-failing tests' scaffold blocks (5 inserts total — `test_task_push.sh` had two scaffold blocks). After running, `test_brainstorm_cli.sh` and `test_explain_context.sh` revealed a SECOND time-bomb of the same class: their scripts also source `lib/python_resolve.sh`. Added `cp python_resolve.sh` to those two tests as well (3 more inserts — explain_context got both libs added together). Total: 8 lines added across 4 files. All 4 originally-failing tests now pass with full counts: test_task_push 18/18, test_brainstorm_cli 31/31, test_explain_context 29/29, test_migrate_archives 28/28. Adjacent regression check (test_brainstorm*, test_explain*, test_migrate*, test_task_push) all green.
- **Deviations from plan:** Plan only anticipated `aitask_path.sh` as the missing lib; `python_resolve.sh` was a second discovered miss for 2 of the 4 tests. Same root-cause class (system lib sourced by helpers), so the Strategy 1 patch generalized cleanly.
- **Issues encountered:** None blocking. The two-step nature of the fix (run, hit second missing lib, add it, re-run) is exactly the time-bomb pattern that motivates the t734 follow-up task.
- **Key decisions:**
  1. Used `cp` from `$PROJECT_DIR` for all 4 tests (including `test_explain_context.sh` which inlines other libs via heredoc) — the libs being copied are simple and the test isn't testing PATH or version-resolution behavior, so a direct `cp` of the real file is fine and stays in sync with future changes.
  2. Took Strategy 1 over Strategy 2 per user's verify-mode decision; spawned t734 (`test_scaffold_helper_for_fake_aitask_repo`) as the standalone follow-up task with helper extraction + 51-test convergence + CLAUDE.md guardrail recommendation.
- **Upstream defects identified:** None — the failing scripts (`./ait`, `aitask_brainstorm_init.sh`, `aitask_explain_context.sh`, `aitask_migrate_archives.sh`) themselves are correct in sourcing the system libs unconditionally. The bug class is purely in the test scaffolds. The broader scope (51 tests with the same time-bomb) is captured in t734, not as an upstream defect.
- **Notes for sibling tasks:** Other t732 children that touch shell tests (especially t732_3 Cluster C) should be aware: any new test that scaffolds a fake `.aitask-scripts/lib/` MUST include `aitask_path.sh` and `python_resolve.sh` until t734 lands. Once t734 lands, tests should `source tests/lib/test_scaffold.sh` and call `setup_fake_aitask_repo`.
