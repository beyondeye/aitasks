---
priority: medium
effort: medium
depends: [t777_14]
issue_type: refactor
status: Ready
labels: [aitask_pick]
created_at: 2026-05-17 12:01
updated_at: 2026-05-17 12:01
---

## Context

Depends on t777_6 (pilot) and t777_7. Converts `aitask-pickweb` (Claude Code Web variant) SKILL.md to templated pattern across all 4 agents.

Likely shares many remote profile keys with pickrem (t777_14). May have additional web-specific keys — verify by grep.

## Key Files to Modify

- `.claude/skills/aitask-pickweb/SKILL.md.j2` (new)
- `.claude/skills/aitask-pickweb/SKILL.md` (replace) — Claude stub (per `stub-skill-pattern.md` §3b)
- `.agents/skills/aitask-pickweb/SKILL.md` (replace) — Codex stub (per `stub-skill-pattern.md` §3b)
- `.gemini/commands/aitask-pickweb.toml` (replace) — Gemini stub in `prompt` field (per `stub-skill-pattern.md` §3c)
- `.opencode/commands/aitask-pickweb.md` (replace) — OpenCode stub in body (per `stub-skill-pattern.md` §3d)

NOTE: per t777_3 design, Gemini/OpenCode stubs live in the command-wrapper files, NOT in `<agent_root>/skills/aitask-pickweb/SKILL.md`. Rendered variants land at `.gemini/skills/aitask-pickweb-<profile>-/SKILL.md` and `.opencode/skills/aitask-pickweb-<profile>-/SKILL.md` (trailing-hyphen convention, gitignored) and are reached via the stub's Read-and-follow instruction.

## Implementation Plan

Same procedure as t777_14:
1. Grep SKILL.md for "Profile check:" blocks.
2. Convert each to `{% if profile.<key> %}…{% else %}…{% endif %}`.
3. Agent-specific branches as needed.
4. Wrap literal `{{`/`{%` in `{% raw %}`.
5. Frontmatter `name: aitask-pickweb-{{ profile.name }}`.
6. Author 4 stubs.

## Verification Steps

1. `ait skill verify` passes.
2. `ait skill render pickweb --profile remote --agent claude` produces expected output.
3. Stub-dispatch end-to-end on all 4 agents.
