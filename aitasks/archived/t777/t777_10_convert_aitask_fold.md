---
priority: medium
effort: medium
depends: [t777_9, t777_7, t777_22, t777_26]
issue_type: refactor
status: Done
labels: [aitask_pick]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-05-17 12:00
updated_at: 2026-05-19 23:50
completed_at: 2026-05-19 23:50
---

## Context

Depends on t777_6 (pilot) and t777_7. Converts `aitask-fold` SKILL.md to templated pattern across all 4 agents. Same procedure as t777_6/t777_8/t777_9.

## Key Files to Modify

- `.claude/skills/aitask-fold/SKILL.md.j2` (new) — template
- `.claude/skills/aitask-fold/SKILL.md` (replace) — Claude stub (per `stub-skill-pattern.md` §3b)
- `.agents/skills/aitask-fold/SKILL.md` (replace) — Codex stub (per `stub-skill-pattern.md` §3b)
- `.gemini/commands/aitask-fold.toml` (replace) — Gemini stub in `prompt` field (per `stub-skill-pattern.md` §3c)
- `.opencode/commands/aitask-fold.md` (replace) — OpenCode stub in body (per `stub-skill-pattern.md` §3d)

NOTE: per t777_3 design, Gemini/OpenCode stubs live in the command-wrapper files, NOT in `<agent_root>/skills/aitask-fold/SKILL.md`. Rendered variants land at `.gemini/skills/aitask-fold-<profile>-/SKILL.md` and `.opencode/skills/aitask-fold-<profile>-/SKILL.md` (trailing-hyphen convention, gitignored) and are reached via the stub's Read-and-follow instruction.

## Implementation Plan

1. Grep SKILL.md for "Profile check:" blocks and profile key references.
2. Convert each to `{% if profile.<key> %}…{% else %}…{% endif %}`.
3. Wrap literal `{{`/`{%` in `{% raw %}`.
4. Frontmatter `name: aitask-fold-{{ profile.name }}`.
5. Author 4 stubs per `task-workflow/stub-skill-pattern.md` (t777_3).

## Verification Steps

1. `ait skill verify` passes.
2. `ait skill render fold --profile fast --agent claude` produces expected output.
3. Stub-dispatch end-to-end on all 4 agents.

## Jinja Comment Conventions

When wrapping profile checks in `{% if/elif/else/endif %}` blocks, follow the
**Jinja comment conventions for profile-aware templates** documented in
`aidocs/skill_authoring_conventions.md`. In short:

- Separator `{# ---------- <label> ---------- #}` on the **same line** as
  `{% if %}` (placing it on its own line adds a blank line to the rendered
  output; `{#- -#}` stripping over-consumes the existing blank line above).
- Inline `{# <label>: when this branch fires #}` on the **same line** as
  every `{% elif %}` / `{% else %}`.
- Inline `{# ---------- end <label> ---------- #}` on the **same line** as
  every `{% endif %}`.

`<label>` is the profile key under test (`default_email`, `create_worktree`,
…); nested ifs get their own labels. After wrapping, render the template
against every committed profile and diff against the matching golden — the
diff MUST be empty (the convention is engineered to be render-neutral).
