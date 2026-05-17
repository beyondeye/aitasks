---
priority: medium
effort: medium
depends: [t777_10]
issue_type: refactor
status: Ready
labels: [aitask_pick]
created_at: 2026-05-17 12:00
updated_at: 2026-05-17 12:00
---

## Context

Depends on t777_6 (pilot) and t777_7. Converts `aitask-qa` SKILL.md to templated pattern across all 4 agents. Same procedure as t777_6/t777_8.

Profile keys consumed by qa: `qa_mode` (ask|create_task|implement|plan_only), `qa_run_tests`, `qa_tier` (q|s|e).

## Key Files to Modify

- `.claude/skills/aitask-qa/SKILL.md.j2` (new) — template
- `.claude/skills/aitask-qa/SKILL.md` (replace) — Claude stub (per `stub-skill-pattern.md` §3b)
- `.agents/skills/aitask-qa/SKILL.md` (replace) — Codex stub (per `stub-skill-pattern.md` §3b)
- `.gemini/commands/aitask-qa.toml` (replace) — Gemini stub in `prompt` field (per `stub-skill-pattern.md` §3c)
- `.opencode/commands/aitask-qa.md` (replace) — OpenCode stub in body (per `stub-skill-pattern.md` §3d)

NOTE: per t777_3 design, Gemini/OpenCode stubs live in the command-wrapper files, NOT in `<agent_root>/skills/aitask-qa/SKILL.md`. Rendered variants land at `.gemini/skills/aitask-qa-<profile>-/SKILL.md` and `.opencode/skills/aitask-qa-<profile>-/SKILL.md` (trailing-hyphen convention, gitignored) and are reached via the stub's Read-and-follow instruction.

## Implementation Plan

1. Convert each "Profile check:" block (qa_mode, qa_run_tests, qa_tier) to `{% if profile.<key> %}…{% else %}…{% endif %}` with straight-line text in branches.
2. For enum keys (qa_mode, qa_tier), use `{% if profile.qa_mode == "ask" %}…{% elif profile.qa_mode == "create_task" %}…{% endif %}` pattern.
3. Agent-specific branches as needed.
4. Wrap literal `{{`/`{%` in `{% raw %}`.
5. Frontmatter `name: aitask-qa-{{ profile.name }}`.
6. Author 4 stubs.

## Verification Steps

1. `ait skill verify` passes.
2. Render for each `qa_mode` value across all 4 agents — confirm only the relevant branch appears in rendered output.
3. Stub-dispatch end-to-end.
