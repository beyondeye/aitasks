---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [testing, bash_scripts]
created_at: 2026-04-28 13:41
updated_at: 2026-04-28 13:41
boardidx: 10
---

## Origin

Spawned from t684 during Step 8b review. t684 fixed `tests/test_revert_analyze.sh` by replacing its hand-curated `cp` list with `cp -R "$PROJECT_DIR/.aitask-scripts" ...` (the t678 pattern). The diagnosis revealed this is a recurring drift bug, not a one-off.

## Upstream defect

`tests/*.sh (~58 files) — many test fixtures still mirror lib/ files by hand` (e.g., legacy pattern `cp "$PROJECT_DIR/.aitask-scripts/lib/X.sh" .aitask-scripts/lib/`). Each is a latent drift bug: any new `source` line added to a copied script silently breaks the fixture without raising a visible test error, because callers commonly redirect stderr to `/dev/null`. t678 began the migration to `cp -R` for three tests; t684 extended it to one more (`test_revert_analyze.sh`). The remaining ~58 tests still use the legacy pattern.

## Diagnostic context

`test_revert_analyze.sh` reported 17/60 failing assertions for two seemingly unrelated patterns (`--task-commits` missing children, `--task-children-areas` returning `NO_CHILDREN`). The root cause was a single missing `cp lib/archive_scan.sh` in the fixture: `aitask_query_files.sh` started sourcing `archive_scan.sh` after the test fixture was written, the fixture's hand-curated copy list wasn't updated, and `set -euo pipefail` caused `aitask_query_files.sh` to exit at the missing-source line. The caller silenced stderr (`2>/dev/null || return 0`), so child enumeration failed silently. Two distinct test failure clusters all traced back to that one missing file.

This pattern will recur every time:

1. A script gets a new `source` directive for a previously-uncopied lib file, OR
2. A new lib file is added that happens to be sourced transitively.

Hand-curated copy lists do not detect these. `cp -R` does.

## Suggested approach

1. Enumerate all tests in `tests/*.sh` that still use the hand-curated pattern. Starting list (from `grep -l 'PROJECT_DIR/.aitask-scripts/lib' tests/*.sh` at t684 close): 58 files including `test_archive_scan.sh`, `test_create_manual_verification.sh`, `test_archive_no_overbroad_add.sh`, `test_archive_verification_gate.sh`, `test_claim_id.sh`, `test_draft_finalize.sh`, `test_format_yaml_list.sh`, `test_brainstorm_cli.sh`, `test_migrate_archives.sh`, `test_archive_folded.sh`, `test_data_branch_setup.sh`, `test_file_references.sh`, `test_last_used_labels.sh`, `test_explain_cleanup.sh`, `test_fold_mark.sh`, `test_archive_carryover.sh`, `test_codeagent.sh`, `test_lock_reclaim.sh`, `test_parallel_child_create.sh`, `test_contribute.sh`, `test_issue_import_contributor.sh`, `test_multi_session_monitor.sh`, `test_archive_utils.sh`, `test_archive_related_issues.sh`, `test_python_resolve.sh`, `test_sed_compat.sh`, `test_auto_merge_file_ref.sh`, `test_create_silent_stdout.sh`, `test_task_push.sh`, `test_crew_init.sh`, `test_task_git.sh`, `test_verifies_field.sh`, `test_explain_binary.sh`, `test_task_lock.sh`, `test_crew_template_includes.sh`, `test_web_merge.sh`, `test_fold_file_refs_union.sh`, `test_fold_validate.sh`, `test_init_data.sh`, `test_zip_old.sh`, `test_fold_content.sh`, `test_multi_session_minimonitor.sh`, `test_lock_force.sh`, `test_launch_mode_field.sh`, `test_lock_diag.sh`, `test_multi_session_primitives.sh`, `test_merge_issues.sh`, `test_find_files.sh`, `test_resolve_tar_zst.sh`, `test_repo_fetch.sh`, `test_pr_contributor_metadata.sh`, `test_terminal_compat.sh`, `test_verified_update.sh`, `test_verification_followup.sh`, `test_tui_switcher_multi_session.sh`, `test_setup_git.sh`, `test_tmux_exact_session_targeting.sh`, `test_crew_setmode.sh`, `run_all_python_tests.sh`. (Re-enumerate at task start in case the count drifted.)

2. For each, replace the hand-curated `cp lib/*.sh` block with the canonical t678/t684 idiom:
   ```bash
   # Mirror the full .aitask-scripts/ tree so transitive deps are present.
   # Hand-curated copy lists drift silently as new sources/imports are added.
   cp -R "$PROJECT_DIR/.aitask-scripts" "$tmpdir/.aitask-scripts"
   find "$tmpdir/.aitask-scripts" -type d -name __pycache__ -prune -exec rm -rf {} +
   ```
   Adapt the destination path to match each test's existing structure (some use `$tmpdir/.aitask-scripts`, others use a relative `.aitask-scripts` from inside a `cd` block).

3. Run each test after migration to confirm 100% pass rate. Some tests may have been silently passing because their assertions happened not to exercise the missing-lib code paths — those will surface real failures only after the fix, which is good (the pre-existing latent drift bug becomes visible).

4. Consider whether the cp/find idiom should be extracted into a shared helper (e.g., `tests/lib/test_setup.sh`) sourced by every test, so future fixture changes touch one place.

## Verification

- All migrated tests pass individually.
- `grep -l 'PROJECT_DIR/.aitask-scripts/lib' tests/*.sh` returns no matches (all converted).
- Spot-check 2-3 migrated tests by deleting an arbitrary lib file in the fixture path post-cp — `cp -R` paths fail loudly; hand-curated paths fail silently. (Optional sanity check, not a regression test.)

## References

- t678 (commit 7b99044d): "test: Replace hand-curated test copy lists with cp -R" — original migration of 3 tests (`test_crew_groups.sh`, `test_crew_report.sh`, `test_data_branch_migration.sh`).
- t684: this task — extended to `test_revert_analyze.sh` after a real failure.
