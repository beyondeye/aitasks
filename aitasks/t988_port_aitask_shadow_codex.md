---
priority: medium
effort: low
depends: [986_4]
issue_type: chore
status: Ready
labels: [claudeskills, codeagent]
created_at: 2026-06-14 22:55
updated_at: 2026-06-14 22:55
---

Port the `/aitask-shadow` user-invocable command to Codex CLI.

t986_4 landed `/aitask-shadow` as a user-invocable, static command in the Claude Code source (`.claude/skills/aitask-shadow/`: SKILL.md dispatcher + plan-explain.md / plan-challenge.md / plan-socratic.md / plan-assumptions.md). It is spawned by the t986_5 launcher via the `shadow` codeagent-op as `/aitask-shadow <followed_pane_id> [<task_id>]` on argv, and captures the followed pane on demand via `aitask_shadow_capture.sh`.

This task creates the Codex command surface under the shared `.agents/skills/` root so Codex CLI can be spawned as the shadow agent. Adapt from the Claude source; the skill body is agent-agnostic (no `{% if agent %}` gates) so it should largely render/port directly. Verify the command is discoverable/invocable in Codex and that the capture + context helpers resolve. See `aidocs/framework/skill_authoring_conventions.md` and `aidocs/framework/adding_a_new_codeagent.md`.
