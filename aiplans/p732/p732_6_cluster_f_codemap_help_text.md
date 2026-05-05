---
Task: t732_6_cluster_f_codemap_help_text.md
Parent Task: aitasks/t732_fix_failing_pre_existing_test_suite.md
Sibling Tasks: aitasks/t732/t732_7_verify_full_suite_zero_failures.md
Archived Sibling Plans: aiplans/archived/p732/p732_1_cluster_a_textual_tui_api_drift.md, aiplans/archived/p732/p732_2_cluster_b_python_resolve_version_comparison.md, aiplans/archived/p732/p732_3_cluster_c_branch_mode_and_upgrade_commit.md, aiplans/archived/p732/p732_4_cluster_d_external_tool_drift.md, aiplans/archived/p732/p732_5_cluster_z_test_scaffold_missing_aitask_path.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-05 01:12
---

# p732_6 — Cluster F: codemap help text drift (verified)

## Context

`tests/test_contribute.sh:558` asserts that `aitask_codemap.sh --help` output contains the literal phrase `"shared aitasks Python"`. The current help text does not contain that phrase, so the assertion fails (1 of 123 in `test_contribute.sh`).

**Root cause confirmed via git history:**

- The phrase was introduced in commit `8f70bd7a` (t348 — "Rewrite codemap scanning in Python") in both the help text and the test assertion.
- It was removed from the help text in commit `82ce8d98` (t695_4 — "Migrate python3 callers to lib/python_resolve.sh helper"), where the help was rewritten to:
  ```
  - Runs with the framework Python resolved by lib/python_resolve.sh
    (venv > ~/.aitask/bin/python3 symlink > system python3)
  ```
- The test was NOT updated in t695_4 — it still asserts the old wording.
- `grep -r "shared aitasks Python"` across the entire codebase (sources, docs, README, CLAUDE.md, aidocs, website, seed) finds **only the stale test assertion**. The phrase is no longer canonical anywhere.

The current help text **functionally documents the venv resolution** using the new resolver name. Per the task description's decision tree, this is case 1: "String was removed from the help recently and the help still functionally documents the venv → the test should be updated to match the new wording."

## Recommended fix

Update the single assertion in `tests/test_contribute.sh:558` to match a stable substring of the current help, consistent with the four sibling assertions on lines 559-562 (which all check stable substrings of the help text).

**Replace line 558:**
```bash
assert_contains "codemap help mentions shared venv" "shared aitasks Python" "$output"
```
**with:**
```bash
assert_contains "codemap help mentions framework Python resolver" "framework Python resolved by lib/python_resolve.sh" "$output"
```

Why this substring:
- It is a stable, contiguous string in the current help (line 49 of `aitask_codemap.sh`).
- It joins the family of sibling assertions (lines 559-562) that verify the help documents specific behaviors.
- It is more accurate — the previous wording confused "shared venv" naming with the actual resolver mechanism.
- It is robust against trivial future rewordings of the path string in the parenthetical.

Do **NOT** modify `aitask_codemap.sh`. The help text is up-to-date and consistent with the canonical t695_4 refactor; reverting it to old wording would re-introduce drift.

## Files to modify

- `tests/test_contribute.sh:558` — update the failing assertion.

## Verification

1. `bash tests/test_contribute.sh` reports `123 passed / 0 failed`.
2. Manual smoke: `./.aitask-scripts/aitask_codemap.sh --help` renders the resolver line.
3. `grep -rn "shared aitasks Python" tests/ .aitask-scripts/ aidocs/ aitasks/ README.md CLAUDE.md website/ seed/` returns nothing (the legacy phrase is fully retired).

## Step 9 — Post-implementation

Archive via `./.aitask-scripts/aitask_archive.sh 732_6` (handled by the standard task-workflow Step 9).

## Final Implementation Notes

- **Actual work done:** Single-line edit to `tests/test_contribute.sh:558`, replacing the stale literal `"shared aitasks Python"` with `"framework Python resolved by lib/python_resolve.sh"` and renaming the assertion description from `"codemap help mentions shared venv"` to `"codemap help mentions framework Python resolver"`. No other code or test was touched. No changes to `aitask_codemap.sh`.
- **Deviations from plan:** None. The plan correctly identified case 1 (stale test, current help functionally documents the venv resolution) and the implementation matched it exactly.
- **Issues encountered:** None. The fix was a one-line text edit; `bash tests/test_contribute.sh` went from 122/123 to 123/123 in a single iteration.
- **Key decisions:** Chose `"framework Python resolved by lib/python_resolve.sh"` as the new substring because (a) it is the most stable, semantically-meaningful contiguous string in the new help wording, (b) it is unaffected by future trivial path-format edits in the parenthetical line below it, and (c) it cleanly joins the family of sibling assertions on lines 559-562 (which all check stable behavior-naming substrings of the help text).
- **Upstream defects identified:** None. The drift was purely the result of t695_4's refactor not updating its callers' tests; no separate pre-existing bug was uncovered. (The unrelated, pre-existing modification to `.aitask-scripts/brainstorm/brainstorm_app.py` in the working tree at pick-time was left untouched and is not part of this task.)
- **Notes for sibling tasks:** Sibling t732_7 (`verify full suite zero failures`) should now find that `tests/test_contribute.sh` is fully green. The pattern used here — when a refactor renames an internal-mechanism string referenced by a test, prefer updating the test to a stable behavior-naming substring of the new wording rather than re-introducing the old phrase — is a generalizable rule for the remaining clusters' tests should they show similar drift.
