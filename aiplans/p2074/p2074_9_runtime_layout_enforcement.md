---
Task: t2074_9_runtime_layout_enforcement.md
Parent Task: aitasks/t2074_remove_legacy_repository_mode_support.md
Sibling Tasks: aitasks/t2074/t2074_10_python_layout_enforcement.md, aitasks/t2074/t2074_11_instructions_and_skill_prose.md, aitasks/t2074/t2074_12_website_and_aidocs_sweep.md, aitasks/t2074/t2074_13_legacy_removal_final_rescan.md, aitasks/t2074/t2074_1_data_layout_classifier.md, aitasks/t2074/t2074_2_branch_mode_test_fixtures.md, aitasks/t2074/t2074_3_setup_install_transition.md, aitasks/t2074/t2074_4_convert_tests_artifacts_attachments.md, aitasks/t2074/t2074_5_convert_tests_task_writers.md, aitasks/t2074/t2074_6_convert_tests_gates_locks.md, aitasks/t2074/t2074_7_convert_tests_crew_board_python.md, aitasks/t2074/t2074_8_convert_tests_sync_git_core.md
Archived Sibling Plans: aiplans/archived/p2074/p2074_*_*.md
Base branch: main
Output branch: main
---

# t2074_9: Runtime layout enforcement (the flip)

The binding contract is C0, C2, C3, C5 and C6 in the parent plan, plus its
Probe definition. The task file numbers the work items 1-10; this plan runs
them in that order.

## Steps
0. Shared-file gate on `task_utils.sh` (t2064). Read the inbox notes, then
   confirm that t2074_3 through t2074_8 have landed.
1. Enforcers: add `ait_require_data_repo` and `ait_require_data_paths`.
   - `ait_require_data_repo` is wired into rung 4 and runs first in
     `assert_data_worktree_clean`.
   - `ait_require_data_paths` runs first in `assert_task_data_writable`,
     before the bypass.
   - Messages name the C4 recovery.
2. Delete every `"."` branch in `task_utils.sh`, `aitask_sync.sh`,
   `txn_snapshot.sh` and `task_automerge.sh`, then rewrite the related
   comments.
3. C3 errexit audit:
   `grep -n '_ait_data_gitdir\|ait_data_mode\|_ait_detect_data_worktree\|_data_wedge' .aitask-scripts -r`.
   Fix each `local`- or `if`/`||`-guarded site and give it a test. Move the
   gate's non-git seam onto the classifier.
4. Writer audit: every writer must reach `assert_task_data_writable` before
   its first write. Test with and without `--commit`.
5. Dispatcher C0 mapping table in `ait`: exempt list with a rationale for each
   entry, fail-closed default, and a drift test.
6. Tokens and their consumers:
   - drift check: drop `LEGACY_MODE_SKIP` and `--unsynced`, together with the
     call sites;
   - init_data: `NEEDS_CONVERSION` exits 3, `NO_DATA_BRANCH` exits 3;
   - metadata_commit: `MODE:` is always `branch`;
   - lock_diag: `check_fail`.

   Also update the skills (`remote-drift-check.md`, `merge-target-sync.md`,
   `SKILL.md` Step 7, and pickrem/pickweb `.j2` Step 0a), regenerate the
   goldens and remote prerenders, and run `aitask_skill_verify.sh`.
7. Delete the quarantine files and add their refusal replacements. Rework
   T15, T9 and T23. Add the T13c/T13d enforcement acceptance cases.
8. Write `tests/test_data_layout_refusal.sh`:
   - a C0-derived matrix covering dirty, untracked and ignored data;
   - a manifest plus git/remote snapshots;
   - positive controls and a planted write-before-refusal mutant.
9. Post-phase `remote_skill_init_smoke`.
10. Send notes to t1625, t1678, t1984 and t1796 with the committed SHA.

## Verification
- Run every bash test individually and the full Python suite (last line must
  read PASSED).
- Run `aitask_skill_verify.sh` and the render goldens.
- Run `shellcheck`.
- By hand, in a temp legacy repo: confirm the refusal, then convert it with
  `ait setup`.

## Step 9
Commit with `refactor: … (t2074_9)`. Commit task and plan files with
`./ait git`. Then archive.
