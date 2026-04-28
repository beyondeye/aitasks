---
Task: t684_investigate_test_revert_analyze_task_children_areas_regressi.md
Base branch: main
plan_verified: []
---

# Plan: Fix test_revert_analyze.sh regression (t684)

## Context

`tests/test_revert_analyze.sh` reports `Results: 43 passed, 17 failed, 60 total`. The task description (t684) hypothesizes regressions in the production script's regex or child-discovery logic. **That hypothesis is wrong.** The script logic is sound; the regression is in the **test fixture**.

`.aitask-scripts/aitask_query_files.sh:30` sources `lib/archive_scan.sh`. The test fixture's `setup_test_repo()` (lines 87–89) copies a hand-curated list of three lib files (`terminal_compat.sh`, `task_utils.sh`, `archive_utils.sh`) but **not** `archive_scan.sh`. With `set -euo pipefail`, the missing source line kills `aitask_query_files.sh` before any subcommand runs. Its caller (`get_child_ids` at `aitask_revert_analyze.sh:108`) silences stderr with `2>/dev/null`, so the failure is invisible — `get_child_ids` returns empty, `build_search_ids` only sees the parent ID, and `--task-children-areas` reports `NO_CHILDREN`.

Reproduction:

```
$ bash -c 'source aitask_query_files.sh' (without archive_scan.sh)
.aitask-scripts/aitask_query_files.sh: line 30: archive_scan.sh: No such file or directory
exit=1
```

This is the exact drift bug t678 (commit `7b99044d`) addressed in three other tests: hand-curated copy lists silently rot when a script gains a new transitive lib dependency. t678 replaced them with `cp -R "$PROJECT_DIR/.aitask-scripts" ...` plus a `find` to strip `__pycache__`. `tests/test_revert_analyze.sh` was not in t678's scope and still has the legacy pattern — `archive_scan.sh` was added to `aitask_query_files.sh`'s requirements after the fixture was written, and nothing forced the test to keep up.

The fix is to apply the same t678 pattern to this one test. The production script (`aitask_revert_analyze.sh`) needs no changes.

## Files modified

- `tests/test_revert_analyze.sh` — replace hand-curated `cp` list in `setup_test_repo()` with `cp -R` of the full `.aitask-scripts` tree.

## Implementation

In `tests/test_revert_analyze.sh`, replace lines 83–90:

```bash
    # Copy required scripts
    mkdir -p "$tmpdir/.aitask-scripts/lib"
    cp "$PROJECT_DIR/.aitask-scripts/aitask_revert_analyze.sh" "$tmpdir/.aitask-scripts/"
    cp "$PROJECT_DIR/.aitask-scripts/aitask_query_files.sh" "$tmpdir/.aitask-scripts/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" "$tmpdir/.aitask-scripts/lib/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" "$tmpdir/.aitask-scripts/lib/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" "$tmpdir/.aitask-scripts/lib/"
    chmod +x "$tmpdir/.aitask-scripts/"*.sh
```

with:

```bash
    # Mirror the full .aitask-scripts/ tree so transitive deps (e.g.
    # lib/archive_scan.sh) are present. Hand-curated copy lists drift
    # silently as new sources/imports are added.
    cp -R "$PROJECT_DIR/.aitask-scripts" "$tmpdir/.aitask-scripts"
    find "$tmpdir/.aitask-scripts" -type d -name __pycache__ -prune -exec rm -rf {} +
    chmod +x "$tmpdir/.aitask-scripts/"*.sh
```

The comment is taken nearly verbatim from t678 (`tests/test_crew_report.sh`) so that future readers grep-find the pattern. `mkdir -p "$tmpdir/.aitask-scripts/lib"` is dropped — `cp -R` re-creates the full tree.

## Verification

1. `bash tests/test_revert_analyze.sh` reports `Results: 60 passed, 0 failed, 60 total`.
2. `shellcheck tests/test_revert_analyze.sh` passes.
3. Spot-check that no script under `.aitask-scripts/` is unintentionally executed by the fixture by virtue of being copied (`set +x` paths, etc.) — none expected; the test only invokes `aitask_revert_analyze.sh` and `aitask_query_files.sh` by explicit path.

## Out of scope (potential follow-up)

A grep for the legacy pattern shows ~58 other tests still copy individual `lib/*.sh` files by hand. They will exhibit the same drift bug whenever their referenced scripts gain new transitive dependencies. **Not fixing them in t684** — the task is bounded to the failing test. A separate sweep task ("apply t678 cp -R pattern to remaining tests") would be a reasonable follow-up; I'll surface it via Step 8b/8c if appropriate after the fix lands.

## Final Implementation Notes

- **Actual work done:** Replaced lines 83–90 of `tests/test_revert_analyze.sh` (the hand-curated `cp` list of 5 files) with the t678 pattern: `cp -R "$PROJECT_DIR/.aitask-scripts" "$tmpdir/.aitask-scripts"` plus a `find ... -name __pycache__ ... -exec rm -rf` pass to keep the copy clean. `mkdir -p "$tmpdir/.aitask-scripts/lib"` was dropped because `cp -R` re-creates the tree. The comment text mirrors `tests/test_crew_report.sh` (t678) so future grep finds the same idiom in both places.
- **Deviations from plan:** None. The plan was followed verbatim.
- **Issues encountered:** None during implementation. During verification, `shellcheck` reported one warning (`SC2164` on `cd "$tmpdir"` at line 91) — confirmed pre-existing by stashing the change and re-running shellcheck, which produced the identical warning on the unchanged line. Out of scope for t684 and not introduced by this fix.
- **Key decisions:**
  - Adopted t678's `cp -R` pattern verbatim rather than just adding a single `cp ... archive_scan.sh` line. Single-line fixes leave the test fragile to the next transitive dep that gets added; `cp -R` permanently eliminates the drift class.
  - Did **not** modify `aitask_revert_analyze.sh` or `aitask_query_files.sh`. The original task description hypothesised a regression in the production scripts (regex / child-discovery path / frontmatter field). Investigation showed the production scripts are correct — the failure was 100% in the test fixture's library-copy list. Fixing the production scripts would have been a wrong-fix; leaving them alone keeps the diff minimal and faithful to the actual root cause.
  - Did not touch the ~58 other tests that still use the legacy hand-curated copy pattern. Out of scope for t684 (see "Upstream defects identified" below for the suggested follow-up).
- **Upstream defects identified:**
  - `tests/*.sh (~58 files) — many test fixtures still mirror lib/ files by hand (e.g., legacy pattern: `cp "$PROJECT_DIR/.aitask-scripts/lib/X.sh" .aitask-scripts/lib/`). Each is a latent drift bug: any new `source` line in a copied script silently breaks the fixture without raising a visible test error (because callers redirect stderr). t678 began the migration to `cp -R` for three tests; this task extends it to one more (`test_revert_analyze.sh`). A sweep task to convert the remaining ~58 tests is the appropriate follow-up. Surface this at Step 8b.

  No defect was identified in the production scripts (`aitask_revert_analyze.sh`, `aitask_query_files.sh`, or any sourced lib).
