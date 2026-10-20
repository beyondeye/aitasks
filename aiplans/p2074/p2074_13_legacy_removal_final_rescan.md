---
Task: t2074_13_legacy_removal_final_rescan.md
Parent Task: aitasks/t2074_remove_legacy_repository_mode_support.md
Sibling Tasks: aitasks/t2074/t2074_10_python_layout_enforcement.md, aitasks/t2074/t2074_11_instructions_and_skill_prose.md, aitasks/t2074/t2074_12_website_and_aidocs_sweep.md, aitasks/t2074/t2074_1_data_layout_classifier.md, aitasks/t2074/t2074_2_branch_mode_test_fixtures.md, aitasks/t2074/t2074_3_setup_install_transition.md, aitasks/t2074/t2074_4_convert_tests_artifacts_attachments.md, aitasks/t2074/t2074_5_convert_tests_task_writers.md, aitasks/t2074/t2074_6_convert_tests_gates_locks.md, aitasks/t2074/t2074_7_convert_tests_crew_board_python.md, aitasks/t2074/t2074_8_convert_tests_sync_git_core.md, aitasks/t2074/t2074_9_runtime_layout_enforcement.md
Archived Sibling Plans: aiplans/archived/p2074/p2074_*_*.md
Base branch: main
Output branch: main
---

# t2074_13: Final rescan, backlog reconciliation, tripwire

The full scan pattern list is in the task file.

## Steps
1. Reconcile the backlog: t1619, t1625, t1678, t1984, t1708 and t1796. For
   each, confirm the owner's note landed, update the obsolete criteria or
   create follow-up tasks (with confirmation), and record the disposition.
2. Rescan for explicit terms and implicit fallbacks across every listed tree.
   Classify each hit as historical, rejection test, setup-only conversion or
   repair, unrelated, or defect, and record the table in this plan. Fix
   trivial defects here and spawn follow-up tasks for the rest.
3. Post-phase `legacy_branch_tripwire`: write
   `tests/test_no_legacy_layout_branches.sh` with a per-line allowlist and
   planted-probe controls.
4. Walk the parent's acceptance criteria and cite the evidence for each one.

## Verification
- The tripwire test, including its planted controls.
- The full bash suite, every file run individually.
- The Python suite.
- `aitask_skill_verify.sh`.
- The website build and `check_links.py --build`.

## Step 9
Commit with `chore: … (t2074_13)`. After this child is archived, archive the
parent t2074.
