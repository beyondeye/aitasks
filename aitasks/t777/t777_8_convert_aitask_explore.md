---
priority: medium
effort: medium
depends: [t777_7]
issue_type: refactor
status: Ready
labels: [aitask_pick]
created_at: 2026-05-17 12:00
updated_at: 2026-05-17 12:00
---

## Context

Depends on t777_6 (pilot pattern) and t777_7 (shared task-workflow templates). Converts `aitask-explore` SKILL.md to the templated pattern across all 4 agents.

Follow the exact same procedure as t777_6 but for `aitask-explore`. Profile keys consumed by explore: `explore_auto_continue` (see `aitasks/metadata/profiles/fast.yaml`). Also relies on shared task-workflow procs (already templated by t777_7).

## Key Files to Modify

- `.claude/skills/aitask-explore/SKILL.md.j2` (new) — template (Claude path source of truth)
- `.claude/skills/aitask-explore/SKILL.md` (replace) — Claude stub (per `stub-skill-pattern.md` §3b)
- `.agents/skills/aitask-explore/SKILL.md` (replace) — Codex stub (per `stub-skill-pattern.md` §3b)
- `.gemini/commands/aitask-explore.toml` (replace) — Gemini stub in `prompt` field (per `stub-skill-pattern.md` §3c)
- `.opencode/commands/aitask-explore.md` (replace) — OpenCode stub in body (per `stub-skill-pattern.md` §3d)

NOTE: per t777_3 design, Gemini/OpenCode stubs live in the command-wrapper files, NOT in `<agent_root>/skills/aitask-explore/SKILL.md`. Rendered variants land at `.gemini/skills/aitask-explore-<profile>-/SKILL.md` and `.opencode/skills/aitask-explore-<profile>-/SKILL.md` (trailing-hyphen convention, gitignored) and are reached via the stub's Read-and-follow instruction.

## Reference Files for Patterns

- `t777_6` implementation (aitask-pick pilot) — same pattern, smaller surface
- `.claude/skills/task-workflow/stub-skill-pattern.md` from t777_3

## Implementation Plan

1. Grep `.claude/skills/aitask-explore/SKILL.md` for "Profile check:" blocks. Convert each to `{% if profile.<key> %}…{% else %}…{% endif %}`.
2. Add `{% if agent == "..." %}` branches for tool mappings if relevant.
3. Scan for literal `{{`/`{%` and wrap in `{% raw %}`.
4. Frontmatter: `name: aitask-explore-{{ profile.name }}-` in the template (trailing hyphen matches the rendered dir name per t777_3 D2).
5. Replace each per-agent stub surface (4 surfaces) per `task-workflow/stub-skill-pattern.md` §3b–§3d. The Gemini stub goes in the command TOML `prompt` field; the OpenCode stub in the command MD body; the Claude/Codex stubs in their SKILL.md files. Stubs use Read-and-follow (§3e) — NO slash-dispatch.

## Verification Steps

1. `ait skill verify` passes.
2. `ait skillrun explore --profile fast --dry-run` shows the render + launch commands.
3. `ait skill render explore --profile fast --agent claude` produces `.claude/skills/aitask-explore-fast-/SKILL.md` with explore_auto_continue branch inline.
4. Stub-dispatch test: `/aitask-explore` inside claude session triggers rendering and dispatches.
5. Repeat (3) and (4) for codex/gemini/opencode.
