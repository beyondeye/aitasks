---
Task: t2074_12_website_and_aidocs_sweep.md
Parent Task: aitasks/t2074_remove_legacy_repository_mode_support.md
Sibling Tasks: aitasks/t2074/t2074_10_python_layout_enforcement.md, aitasks/t2074/t2074_11_instructions_and_skill_prose.md, aitasks/t2074/t2074_13_legacy_removal_final_rescan.md, aitasks/t2074/t2074_1_data_layout_classifier.md, aitasks/t2074/t2074_2_branch_mode_test_fixtures.md, aitasks/t2074/t2074_3_setup_install_transition.md, aitasks/t2074/t2074_4_convert_tests_artifacts_attachments.md, aitasks/t2074/t2074_5_convert_tests_task_writers.md, aitasks/t2074/t2074_6_convert_tests_gates_locks.md, aitasks/t2074/t2074_7_convert_tests_crew_board_python.md, aitasks/t2074/t2074_8_convert_tests_sync_git_core.md, aitasks/t2074/t2074_9_runtime_layout_enforcement.md
Archived Sibling Plans: aiplans/archived/p2074/p2074_*_*.md
Base branch: main
Output branch: main
---

# t2074_12: Website and aidocs sweep

The scope, the known hits and the report format are in the task file. Follow
`aidocs/framework/documentation_conventions.md`.

## Steps
1. Build the inventory. Grep `website/content/` for explicit terms and for
   implicit promises (see the task file), then read every page under
   getting-started, installation, setup, commands, concepts, workflows, tuis,
   skills and development. Build the full page list first, so the report can
   cover every page.
2. Rewrite each affected page so it describes only the single supported model.
   Add the setup data-branch step, the migration and its decline behaviour, the
   repair, and the upgrade notice to `commands/setup-install.md`.
3. Add an "Unsupported or damaged layouts" troubleshooting section: the states
   from C1a and C1b, the exact refusal text, and the C4 recovery for each.
   Link to it from the installation, sync and setup pages using `relref`.
4. Update `aitasks_extension_points.md:122-125`, `tui_conventions.md:476`, and
   any other aidocs hits.
5. Revise or replace any diagram or screenshot that still shows the retired
   choice.
6. Write the website sweep report in Final Implementation Notes: pages
   reviewed, the change made on each, and every retained reference with its
   justification.

## Verification
From `website/`:
- `hugo build --gc --minify`
- `python3 check_links.py --build`, which must pass
- `python3 check_link_relevance.py`, then triage every hit with each target
  opened

## Step 9
Commit with `documentation: … (t2074_12)`, then archive.
