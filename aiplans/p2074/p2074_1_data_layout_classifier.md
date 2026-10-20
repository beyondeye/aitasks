---
Task: t2074_1_data_layout_classifier.md
Parent Task: aitasks/t2074_remove_legacy_repository_mode_support.md
Sibling Tasks: aitasks/t2074/t2074_10_python_layout_enforcement.md, aitasks/t2074/t2074_11_instructions_and_skill_prose.md, aitasks/t2074/t2074_12_website_and_aidocs_sweep.md, aitasks/t2074/t2074_13_legacy_removal_final_rescan.md, aitasks/t2074/t2074_2_branch_mode_test_fixtures.md, aitasks/t2074/t2074_3_setup_install_transition.md, aitasks/t2074/t2074_4_convert_tests_artifacts_attachments.md, aitasks/t2074/t2074_5_convert_tests_task_writers.md, aitasks/t2074/t2074_6_convert_tests_gates_locks.md, aitasks/t2074/t2074_7_convert_tests_crew_board_python.md, aitasks/t2074/t2074_8_convert_tests_sync_git_core.md, aitasks/t2074/t2074_9_runtime_layout_enforcement.md
Archived Sibling Plans: aiplans/archived/p2074/p2074_*_*.md
Base branch: main
Output branch: main
---

# t2074_1: Data layout classifiers (C1a / C1b), additive

The binding contract is C1a and C1b in the parent plan
(`aiplans/p2074_remove_legacy_repository_mode_support.md`). The full detail is
in the task file. Nothing in this child changes the behaviour of existing callers.

## Steps
1. Read `lib/data_symlinks.sh` (`ait_main_worktree_root`,
   `ait_linked_worktree_roots`, `ait_canon_path`, `ait_data_link_target`,
   `AIT_DATA_LINKS`) and `_ait_detect_data_worktree` in `task_utils.sh:77-147`.
   Reuse their three-state topology results; do not re-derive them.
2. Add `ait_data_repo_state` to `lib/data_symlinks.sh`.
   - Resolution order:
     1. cwd inside the data worktree;
     2. local marker (`./.aitask-data`, then `<toplevel>/.aitask-data`);
     3. the main checkout's marker (only when local resolution fails);
     4. otherwise `legacy`, `uninitialized` or `not_a_repo`;
     5. `indeterminate:topology`, returned as a state.
   - Validate a resolved data worktree in this order: `stale_marker`, then
     `foreign_repo` (canonical common-dir), then `wrong_branch`. A rebase
     `head-name` means wedged, not broken.
   - Check the filesystem first and fall back to git. Cache the result in a
     new per-process global.
3. Add `ait_data_paths_state`: `ready`, `unlinked`, `misdirected`, `dangling`
   or `mixed`. It compares canonical `$PWD/$TASK_DIR` and `$PWD/$PLAN_DIR`
   against `<data>/aitasks` and `<data>/aiplans`.
4. Both functions always return 0. Make every internal `$( )` errexit-safe
   (`|| var=""` with an explicit failure branch).
5. Add the `.aitask-scripts/aitask_data_layout.sh` CLI. It prints
   `REPO:<state>` and `PATHS:<state>`. Add it to the helper whitelists per
   `aidocs/framework/aitasks_extension_points.md`.
6. Add `.aitask-scripts/lib/data_layout.py`. It runs the CLI once and caches
   the result. Expose `repo_state()`, `paths_state()` and `data_worktree()`.
7. `git-health` reporting: apply the shared-file gate to `task_utils.sh`
   (t2064). If the gate is blocked, send a note handing the item to t2074_9.
8. Add `tests/test_data_layout_classifier.sh`, with fixtures for every state
   and reason, the positive cases (T13c, T13d, linked, separate-git-dir,
   mid-rebase, nested), the never-dies cases under errexit, and the
   filesystem-vs-git differential. Add `tests/test_data_layout.py` for the
   parity checks.

## Verification
- Run the new tests.
- `bash tests/test_task_git.sh` and `bash tests/test_init_data.sh` stay green.
- Run `shellcheck` on the touched scripts.

## Step 9
Commit with `feature: … (t2074_1)`, then archive per Step 9.
