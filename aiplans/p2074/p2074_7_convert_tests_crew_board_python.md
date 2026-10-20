---
Task: t2074_7_convert_tests_crew_board_python.md
Parent Task: aitasks/t2074_remove_legacy_repository_mode_support.md
Sibling Tasks: aitasks/t2074/t2074_10_python_layout_enforcement.md, aitasks/t2074/t2074_11_instructions_and_skill_prose.md, aitasks/t2074/t2074_12_website_and_aidocs_sweep.md, aitasks/t2074/t2074_13_legacy_removal_final_rescan.md, aitasks/t2074/t2074_1_data_layout_classifier.md, aitasks/t2074/t2074_2_branch_mode_test_fixtures.md, aitasks/t2074/t2074_3_setup_install_transition.md, aitasks/t2074/t2074_4_convert_tests_artifacts_attachments.md, aitasks/t2074/t2074_5_convert_tests_task_writers.md, aitasks/t2074/t2074_6_convert_tests_gates_locks.md, aitasks/t2074/t2074_8_convert_tests_sync_git_core.md, aitasks/t2074/t2074_9_runtime_layout_enforcement.md
Archived Sibling Plans: aiplans/archived/p2074/p2074_*_*.md
Base branch: main
Output branch: main
---

# t2074_7: convert_tests_crew_board_python

The binding rules are the parent plan's Probe definition (quarantine files,
completion evidence) and C0/C1. The file list and method are in the task file.
The authoritative case list is t2074_2's measurement note, delivered in this
task's `## Inbox`.

## Steps
1. Read the inbox note (failing cases, baseline, quarantine file name), and
   read t2074_2's plan.
2. For each file, read its fixture builder, convert it with
   `ait_fixture_to_branch_mode` / `convert_to_branch_mode`, and rewrite the
   code-branch commit assertions to use `fixture_data_git`. Keep every original
   behavioural claim.
3. Move cases whose only purpose is legacy behaviour, verbatim, into this
   batch's quarantine file (its header names t2074_9 as the deleter).
4. Run each file on the current tree. Then run it under the probe, in an
   isolated worktree that is never committed. Check the exit status, the
   summary line and `TOTAL` against the baseline minus the moved assertions;
   for Python, check the retained ids pass in junit.
5. Record a per-file evidence table in Final Implementation Notes.

## Verification
Every non-quarantined file in this batch passes both runs and carries
completion evidence.

## Step 9
Commit with `test: … (t2074_7)`, then archive.
