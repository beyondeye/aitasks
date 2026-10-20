---
Task: t2074_2_branch_mode_test_fixtures.md
Parent Task: aitasks/t2074_remove_legacy_repository_mode_support.md
Sibling Tasks: aitasks/t2074/t2074_10_python_layout_enforcement.md, aitasks/t2074/t2074_11_instructions_and_skill_prose.md, aitasks/t2074/t2074_12_website_and_aidocs_sweep.md, aitasks/t2074/t2074_13_legacy_removal_final_rescan.md, aitasks/t2074/t2074_1_data_layout_classifier.md, aitasks/t2074/t2074_3_setup_install_transition.md, aitasks/t2074/t2074_4_convert_tests_artifacts_attachments.md, aitasks/t2074/t2074_5_convert_tests_task_writers.md, aitasks/t2074/t2074_6_convert_tests_gates_locks.md, aitasks/t2074/t2074_7_convert_tests_crew_board_python.md, aitasks/t2074/t2074_8_convert_tests_sync_git_core.md, aitasks/t2074/t2074_9_runtime_layout_enforcement.md
Archived Sibling Plans: aiplans/archived/p2074/p2074_*_*.md
Base branch: main
Output branch: main
---

# t2074_2: Shared branch-mode fixtures and the flip measurement

The binding rules are the Probe definition and C1 in the parent plan. The full
detail is in the task file.

## Steps
1. Write `tests/lib/data_branch_fixture.sh`, providing
   `ait_fixture_to_branch_mode <repo> [--remote <bare>]` and
   `fixture_data_git`.
   - Create an orphan `aitask-data` branch with `git worktree add`, a
     **registered** worktree, at `.aitask-data`.
   - Move the existing `aitasks/` and `aiplans/` into it, then commit.
   - `git rm -r --cached` them from main and add the `.gitignore` lines.
   - Create the links with production `ait_ensure_data_symlinks` (source
     `lib/data_symlinks.sh` from `$PROJECT_DIR`).
   - Push to the remote when one is given.
2. Write `convert_to_branch_mode(root)` in `tests/lib/branch_mode_repo.py`,
   sharing internals with `make_branch_mode_repo`.
3. Convert the clone-style builders to registered worktrees without changing
   their signatures: `board_fixture.py` `_layout`/`build_tree`/
   `build_fixture_tree`, and `metadata_update_fixture.sh:188`, `:124` and
   `:146`. Read each one fully before changing it.
4. Write the `tests/test_data_branch_fixture.sh` self-test: the helper layout
   classifies `branch`/`ready` (via `aitask_data_layout.sh` from t2074_1) the
   same way a real `setup_data_branch` layout does, and the data is
   byte-identical.
5. Document the fixtures in `aidocs/framework/testing_conventions.md`.
6. Measurement (`measure_flip_breakage`):
   - Record the baseline on the unpatched tree: per-file summary line and
     `TOTAL` for bash, collected ids for Python.
   - In an isolated `git worktree`, apply the probe patch (never commit it)
     and run everything. Record failures per test case.
   - Assign each failure to a batch (t2074_4 to t2074_8). Mark the retired
     cases and fix the quarantine file names and their owners.
   - Write the tables into this plan's Final Implementation Notes.
   - Run `./ait note 2074_<n> --from 2074_2 --file -` for each batch.

## Verification
- Run the self-test.
- Run the converted-builder consumers: the Python suite,
  `test_usage_update.sh`, `test_verified_update.sh` and
  `test_verified_update_flags.sh`.
- Check that the notes were appended.

## Step 9
Commit with `test: … (t2074_2)`, then archive.
