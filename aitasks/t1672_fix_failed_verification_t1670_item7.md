---
priority: medium
effort: medium
depends: [1597]
issue_type: bug
status: Ready
labels: [verification, bug]
anchor: 1595
followup_kind: verification_failure
created_at: 2026-09-01 17:11
updated_at: 2026-09-01 17:11
---

## Failed verification item from t1597

> TODO: verify .aitask-scripts/settings/settings_app.py end-to-end in tmux - the new resource_admission_command row renders in `ait settings` -> Project Config, edits with the plain string editor, and saves back to project_config.yaml losslessly

### Source

- **Manual-verification task:** `aitasks/t1670_manual_verification_pre_implementation_resource_admission_ho.md` (item #7)
- **Origin feature task:** t1597
- **Origin archived plan:** `aiplans/archived/p1597_pre_implementation_resource_admission_hook.md`

### Commits that introduced the failing behavior

- 68af4d67a enhancement: Add a pluggable pre-implementation resource admission hook (t1597)

### Files touched by those commits

- .agents/skills/task-workflow-remote-codex-/plan-approved-stop.md
- .agents/skills/task-workflow-remote-codex-/resource-admission.md
- .agents/skills/task-workflow-remote-codex-/SKILL.md
- aidocs/gates/ledger-driven-reentry.md
- .aitask-scripts/aitask_resource_admission.sh
- .aitask-scripts/lib/gate_verifier_lib.sh
- .aitask-scripts/settings/settings_app.py
- .claude/settings.local.json
- .claude/skills/task-workflow/plan-approved-stop.md
- .claude/skills/task-workflow-remote-/plan-approved-stop.md
- .claude/skills/task-workflow-remote-/resource-admission.md
- .claude/skills/task-workflow-remote-/SKILL.md
- .claude/skills/task-workflow/resource-admission.md
- .claude/skills/task-workflow/SKILL.md
- .codex/rules/default.rules
- .opencode/skills/task-workflow-remote-/plan-approved-stop.md
- .opencode/skills/task-workflow-remote-/resource-admission.md
- .opencode/skills/task-workflow-remote-/SKILL.md
- seed/claude_settings.local.json
- seed/codex_rules.default.rules
- seed/opencode_config.seed.json
- seed/project_config.yaml
- tests/golden/procs/task-workflow/plan-approved-stop-default.md
- tests/golden/procs/task-workflow/plan-approved-stop-fast.md
- tests/golden/procs/task-workflow/plan-approved-stop-remote.md
- tests/golden/procs/task-workflow/resource-admission-default.md
- tests/golden/procs/task-workflow/SKILL-default.md
- tests/golden/procs/task-workflow/SKILL-fast.md
- tests/golden/procs/task-workflow/SKILL-remote.md
- tests/test_gate_verifiers.sh
- tests/test_plan_approved_marker_contract.sh
- tests/test_resource_admission.sh
- tests/test_resource_admission_stop.sh
- tests/test_skill_render_task_workflow.sh
- website/content/docs/skills/aitask-pick/build-verification.md
- website/content/docs/skills/aitask-pick/_index.md
- website/content/docs/skills/aitask-pick/resource-admission.md

### Next steps

Reproduce the failure locally (see the commits and files above, and the origin archived plan for implementation context), identify the offending change, and fix. This task was auto-generated from a manual-verification failure in t1670 item #7.
