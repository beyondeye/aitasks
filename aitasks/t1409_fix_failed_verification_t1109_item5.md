---
priority: medium
effort: medium
depends: [635_15]
issue_type: bug
status: Ready
labels: [verification, bug]
anchor: 635
created_at: 2026-08-04 13:08
updated_at: 2026-08-04 13:08
---

## Failed verification item from t635_15

> **Stale signature re-pends.** Change a **code** file — not anything under

### Source

- **Manual-verification task:** `aitasks/t1109_async_human_gate_live_verify.md` (item #5)
- **Origin feature task:** t635_15
- **Origin archived plan:** `aiplans/archived/p635/p635_15_async_human_gates.md`

### Commits that introduced the failing behavior

- b4df1ea3f feature: Async human gates — ait gate pass + headless hybrid switch (t635_15)

### Files touched by those commits

- .agents/skills/aitask-pickrem-remote-codex-/SKILL.md
- aidocs/gates/aitask-gate-framework.md
- ait
- .aitask-scripts/aitask_gate_pass.sh
- .aitask-scripts/lib/gate_orchestrator.py
- .claude/skills/aitask-gate-template/SKILL.md
- .claude/skills/aitask-pickrem-remote-/SKILL.md
- .claude/skills/aitask-pickrem/SKILL.md.j2
- .claude/skills/task-workflow/gate-recording.md
- .codex/rules/default.rules
- .opencode/skills/aitask-pickrem-remote-/SKILL.md
- seed/claude_settings.local.json
- seed/codex_rules.default.rules
- seed/opencode_config.seed.json
- tests/golden/skills/aitask-pickrem/SKILL-remote-claude.md
- tests/test_gate_cli_wiring.sh
- tests/test_gate_orchestrator.sh
- tests/test_gate_pass.sh

### Next steps

Reproduce the failure locally (see the commits and files above, and the origin archived plan for implementation context), identify the offending change, and fix. This task was auto-generated from a manual-verification failure in t1109 item #5.
