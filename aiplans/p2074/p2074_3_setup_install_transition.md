---
Task: t2074_3_setup_install_transition.md
Parent Task: aitasks/t2074_remove_legacy_repository_mode_support.md
Sibling Tasks: aitasks/t2074/t2074_10_python_layout_enforcement.md, aitasks/t2074/t2074_11_instructions_and_skill_prose.md, aitasks/t2074/t2074_12_website_and_aidocs_sweep.md, aitasks/t2074/t2074_13_legacy_removal_final_rescan.md, aitasks/t2074/t2074_1_data_layout_classifier.md, aitasks/t2074/t2074_2_branch_mode_test_fixtures.md, aitasks/t2074/t2074_4_convert_tests_artifacts_attachments.md, aitasks/t2074/t2074_5_convert_tests_task_writers.md, aitasks/t2074/t2074_6_convert_tests_gates_locks.md, aitasks/t2074/t2074_7_convert_tests_crew_board_python.md, aitasks/t2074/t2074_8_convert_tests_sync_git_core.md, aitasks/t2074/t2074_9_runtime_layout_enforcement.md
Archived Sibling Plans: aiplans/archived/p2074/p2074_*_*.md
Base branch: main
Output branch: main
---

# t2074_3: Setup and install transition (the only converter and repair tool)

The binding rules are C4 (the recovery matrix), C1 and C6 in the parent plan.
The full detail is in the task file.

## Steps
1. In `setup_data_branch`, replace the :1571 shortcut with dispatch on both
   classifiers (from t2074_1), before any write.
   - Configured means `branch` **and** `ready`.
   - Otherwise, dispatch on C1b when C1a is `branch`, and on C1a in every
     other case.
2. Extract `ait_repair_data_links` from `ait_link_worktree_data` in
   `lib/data_symlinks.sh`:
   - preflight conflicts (real files or dirs) and refuse them all;
   - repoint misdirected links;
   - create missing links;
   - print a warning naming each old target.

   Re-point `ait_link_worktree_data` at it and keep its contract.
3. Remove the fresh-setup `[Y/n]` prompt. Keep a single confirmation for the
   legacy migration. A decline exits non-zero and changes nothing.
4. The legacy fallbacks (1716, 1747, `abort_data_branch_setup`) become teardown
   plus a non-zero exit, with the originals intact.
5. Repair `stale_marker` with `git worktree prune`/`repair`, then re-add, but
   only when the stale dir holds no unique files. All other broken states
   refuse and print move-aside steps that never delete anything.
6. Rewrite the comments on the `_ait_data_branch_exclude_re` and
   `commit_framework_data_files` guards.
7. In `install.sh`, `ensure_data_root` refuses instead of creating a real dir.
   A legacy project gets a conversion notice on install and upgrade, with no
   migration.
8. Tests:
   - extend `test_data_branch_setup.sh` (26/26b/27/31 exit status, T14/T23 as
     refusal);
   - update `test_install_create_data_dirs.sh` T2/T4, `test_t644` scenario C,
     `test_setup_hooks_only.sh` and the T43 structural check;
   - add the "configured" test;
   - add the recovery tests, which refuse, apply the recovery, then re-read
     the state. They include the misdirected-to-an-existing-dir case and use
     a before/after content manifest plus git snapshots.
9. Send a note to t1619 with the committed SHA.

## Verification
- Run every test named in the task file.
- Run `shellcheck .aitask-scripts/aitask_setup.sh install.sh`.
- By hand: a fresh `ait setup` in temp repos, with and without `origin`.

## Step 9
Commit with `refactor: … (t2074_3)`, then archive.
