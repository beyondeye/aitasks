---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: [t986_4]
issue_type: chore
status: Implementing
labels: [claudeskills, codeagent]
assigned_to: dario-e@beyond-eye.com
implemented_with: codex/gpt5_5
created_at: 2026-06-14 22:55
updated_at: 2026-06-15 10:37
---

Port the `/aitask-shadow` user-invocable command to OpenCode.

t986_4 landed `/aitask-shadow` as a user-invocable, static command in the Claude Code source (`.claude/skills/aitask-shadow/`: SKILL.md dispatcher + 4 sub-procedure files). It is spawned by the t986_5 launcher as `/aitask-shadow <followed_pane_id> [<task_id>]` (OpenCode: `--prompt`) and captures the followed pane on demand via `aitask_shadow_capture.sh`.

This task creates the OpenCode surfaces: `.opencode/commands/aitask-shadow.md` (command entry) and `.opencode/skills/aitask-shadow/SKILL.md` (wrapper), per the established pattern. Adapt from the Claude source (agent-agnostic body). Verify discoverability/invocation in OpenCode and that the capture + context helpers resolve. See `aidocs/framework/skill_authoring_conventions.md` and `aidocs/framework/adding_a_new_codeagent.md`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-15T07:37:29Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-15T07:37:29Z status=pass attempt=1 type=machine

> **✅ gate:review_approved** run=2026-06-15T07:43:51Z status=pass attempt=1 type=human
