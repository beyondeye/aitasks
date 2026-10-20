---
Task: t2074_10_python_layout_enforcement.md
Parent Task: aitasks/t2074_remove_legacy_repository_mode_support.md
Sibling Tasks: aitasks/t2074/t2074_11_instructions_and_skill_prose.md, aitasks/t2074/t2074_12_website_and_aidocs_sweep.md, aitasks/t2074/t2074_13_legacy_removal_final_rescan.md, aitasks/t2074/t2074_1_data_layout_classifier.md, aitasks/t2074/t2074_2_branch_mode_test_fixtures.md, aitasks/t2074/t2074_3_setup_install_transition.md, aitasks/t2074/t2074_4_convert_tests_artifacts_attachments.md, aitasks/t2074/t2074_5_convert_tests_task_writers.md, aitasks/t2074/t2074_6_convert_tests_gates_locks.md, aitasks/t2074/t2074_7_convert_tests_crew_board_python.md, aitasks/t2074/t2074_8_convert_tests_sync_git_core.md, aitasks/t2074/t2074_9_runtime_layout_enforcement.md
Archived Sibling Plans: aiplans/archived/p2074/p2074_*_*.md
Base branch: main
Output branch: main
---

# t2074_10: Python layout enforcement

The binding contract is C0 and C1 in the parent plan. Python reads the layout
only through `lib/data_layout.py`.

## Steps
1. Change `board_task_manager._task_git_cmd` to resolve through
   `data_layout.py` from the repo root. It raises a clear error when the state
   is not `branch`. Update the callers (`aitask_board.py:6629`,
   `board_detail_screen.py:59,1970`) to surface that error and never fall back
   to plain git.
2. At board startup, check the C0 reader class. A non-ready layout shows a
   refusal with the recovery text. The sync gate becomes an explicit refusal
   toast.
3. Reword `desync_state.py` `missing_worktree` and the matching
   `syncer_app.py` row.
4. Reword `REASON_DEST_LEGACY_LAYOUT` to "destination not converted — run
   `ait setup` there". It stays a refusal.
5. Record the disposition of `parallel_admission_collect.py:68-80`.
6. Tests: update `test_desync_state.py`, `test_syncer_rows.py` and the
   `test_cross_repo_*` files. Add a board test on a broken-layout fixture, and
   a test for `_task_git_cmd` from a non-root cwd.

## Verification
`bash tests/run_all_python_tests.sh`; the last line must read
`PYTHON SUITE: PASSED`.

## Step 9
Commit with `refactor: … (t2074_10)`, then archive.
