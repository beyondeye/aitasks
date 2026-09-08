---
priority: medium
effort: medium
depends: [1729]
issue_type: bug
status: Ready
labels: [verification, bug]
anchor: 1705
followup_kind: verification_failure
created_at: 2026-09-08 17:16
updated_at: 2026-09-08 17:16
---

## Failed verification item from t1729

> The fixture ladder: confirm `tests/lib/fake_agent_binary.py` takes rung 1 on Linux (copies the system `sleep`, which carries no restricted flag), never the compiled or symlink rungs.

### Source

- **Manual-verification task:** `aitasks/t1737_verify_macos_fixes_on_linux.md` (item #4)
- **Origin feature task:** t1729
- **Origin archived plan:** `aiplans/archived/p1729_fix_macos_only_suite_failures.md`

### Commits that introduced the failing behavior

- ce3a10af3 bug: Fix the macOS-only suite failures, and the mktemp idiom behind one (t1729)

### Files touched by those commits

- .agents/skills/task-workflow-remote-codex-/manual-verification.md
- aidocs/framework/sed_macos_issues.md
- .aitask-scripts/aitask_add_model.sh
- .aitask-scripts/aitask_archive.sh
- .aitask-scripts/aitask_brainstorm_init.sh
- .aitask-scripts/aitask_create_manual_verification.sh
- .aitask-scripts/aitask_crew_command.sh
- .aitask-scripts/aitask_crew_setmode.sh
- .aitask-scripts/aitask_resource_admission.sh
- .aitask-scripts/aitask_run_project_command.sh
- .aitask-scripts/aitask_update.sh
- .aitask-scripts/aitask_verification_followup.sh
- .aitask-scripts/lib/terminal_compat.sh
- .claude/skills/task-workflow/manual-verification.md
- .claude/skills/task-workflow-remote-/manual-verification.md
- .opencode/skills/task-workflow-remote-/manual-verification.md
- tests/golden/procs/task-workflow/manual-verification-default.md
- tests/golden/procs/task-workflow/manual-verification-fast.md
- tests/golden/procs/task-workflow/manual-verification-remote.md
- tests/lib/fake_agent_binary.py
- tests/test_agent_keys.py
- tests/test_board_startup_focus_live.py
- tests/test_brainstorm_init_proposal_file.sh
- tests/test_codebrowser_startup_focus_live.py
- tests/test_contribution_review.sh
- tests/test_merge_issues.sh
- tests/test_prompt_scoping_live.py
- tests/test_sed_compat.sh
- tests/test_skill_render_task_workflow.sh
- tests/test_stats_data.sh
- tests/test_tmux_exec.py

### Next steps

Reproduce the failure locally (see the commits and files above, and the origin archived plan for implementation context), identify the offending change, and fix. This task was auto-generated from a manual-verification failure in t1737 item #4.
