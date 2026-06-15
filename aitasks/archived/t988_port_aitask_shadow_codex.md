---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: [t986_4]
issue_type: chore
status: Done
labels: [claudeskills, codeagent]
assigned_to: dario-e@beyond-eye.com
implemented_with: codex/gpt5_5
created_at: 2026-06-14 22:55
updated_at: 2026-06-15 10:29
completed_at: 2026-06-15 10:29
---

Port the `/aitask-shadow` user-invocable command to Codex CLI.

t986_4 landed `/aitask-shadow` as a user-invocable, static command in the Claude Code source (`.claude/skills/aitask-shadow/`: SKILL.md dispatcher + plan-explain.md / plan-challenge.md / plan-socratic.md / plan-assumptions.md). It is spawned by the t986_5 launcher via the `shadow` codeagent-op as `/aitask-shadow <followed_pane_id> [<task_id>]` on argv, and captures the followed pane on demand via `aitask_shadow_capture.sh`.

This task creates the Codex command surface under the shared `.agents/skills/` root so Codex CLI can be spawned as the shadow agent. Adapt from the Claude source; the skill body is agent-agnostic (no `{% if agent %}` gates) so it should largely render/port directly. Verify the command is discoverable/invocable in Codex and that the capture + context helpers resolve. See `aidocs/framework/skill_authoring_conventions.md` and `aidocs/framework/adding_a_new_codeagent.md`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-15T07:09:56Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-06-15T07:26:08Z status=pass attempt=1 type=human
