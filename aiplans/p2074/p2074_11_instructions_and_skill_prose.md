---
Task: t2074_11_instructions_and_skill_prose.md
Parent Task: aitasks/t2074_remove_legacy_repository_mode_support.md
Sibling Tasks: aitasks/t2074/t2074_10_python_layout_enforcement.md, aitasks/t2074/t2074_12_website_and_aidocs_sweep.md, aitasks/t2074/t2074_13_legacy_removal_final_rescan.md, aitasks/t2074/t2074_1_data_layout_classifier.md, aitasks/t2074/t2074_2_branch_mode_test_fixtures.md, aitasks/t2074/t2074_3_setup_install_transition.md, aitasks/t2074/t2074_4_convert_tests_artifacts_attachments.md, aitasks/t2074/t2074_5_convert_tests_task_writers.md, aitasks/t2074/t2074_6_convert_tests_gates_locks.md, aitasks/t2074/t2074_7_convert_tests_crew_board_python.md, aitasks/t2074/t2074_8_convert_tests_sync_git_core.md, aitasks/t2074/t2074_9_runtime_layout_enforcement.md
Archived Sibling Plans: aiplans/archived/p2074/p2074_*_*.md
Base branch: main
Output branch: main
---

# t2074_11: Instructions and skill prose

The canonical edits and the regeneration list are in the task file.

## Steps
1. Edit the canonical sources:
   - `seed/aitasks_agent_instructions.seed.md`
   - `CLAUDE.md` (hand edit)
   - `ait-git/SKILL.md`
   - `repo-structure.md`
   - `SKILL.md:762`
   - `cross-repo-child-assignment.md:131`
   - `README.md`
   - the setup comment at :1297

   Leave the anchor at `SKILL.md:843` untouched.
2. Regenerate `AGENTS.md`, `.codex/instructions.md` and
   `.opencode/instructions.md` through the setup assemblers. Then regenerate
   the goldens and the remote prerenders.
3. Do the port check and create follow-up tasks for any stray non-rendered
   wrappers. Report the untracked leftover files.

## Verification
- `aitask_skill_verify.sh`
- `tests/test_skill_render_*.sh`
- `tests/test_agent_instructions.sh`
- the grep listed in the task file

## Step 9
Commit with `documentation: … (t2074_11)`, then archive.
