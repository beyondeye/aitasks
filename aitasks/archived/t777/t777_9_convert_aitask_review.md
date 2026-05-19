---
priority: medium
effort: medium
depends: [t777_8, t777_7, t777_22, t777_26]
issue_type: refactor
status: Done
labels: [aitask_pick]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-05-17 12:00
updated_at: 2026-05-19 17:13
completed_at: 2026-05-19 17:13
---

## Context

Depends on t777_6 (pilot) and t777_7. Converts `aitask-review` SKILL.md to templated pattern across all 4 agents. Follows same procedure as t777_6/t777_8.

Profile keys consumed by review: identify by grep at impl time (likely `review_action` from remote profile, plus shared keys via task-workflow).

## Key Files to Modify

- `.claude/skills/aitask-review/SKILL.md.j2` (new) — template
- `.claude/skills/aitask-review/SKILL.md` (replace) — Claude stub (per `stub-skill-pattern.md` §3b)
- `.agents/skills/aitask-review/SKILL.md` (replace) — Codex stub (per `stub-skill-pattern.md` §3b)
- `.gemini/commands/aitask-review.toml` (replace) — Gemini stub in `prompt` field (per `stub-skill-pattern.md` §3c)
- `.opencode/commands/aitask-review.md` (replace) — OpenCode stub in body (per `stub-skill-pattern.md` §3d)

NOTE: per t777_3 design, Gemini/OpenCode stubs live in the command-wrapper files, NOT in `<agent_root>/skills/aitask-review/SKILL.md`. Rendered variants land at `.gemini/skills/aitask-review-<profile>-/SKILL.md` and `.opencode/skills/aitask-review-<profile>-/SKILL.md` (trailing-hyphen convention, gitignored) and are reached via the stub's Read-and-follow instruction.

## Reference Files for Patterns

- `t777_6` implementation, `task-workflow/stub-skill-pattern.md`

## Implementation Plan

1. Grep SKILL.md for "Profile check:" blocks and profile key references.
2. Convert each to `{% if profile.<key> %}…{% else %}…{% endif %}`.
3. Agent-specific branches as needed.
4. Wrap literal `{{`/`{%` in `{% raw %}`.
5. Frontmatter `name: aitask-review-{{ profile.name }}`.
6. Author 4 stubs.

## Verification Steps

1. `ait skill verify` passes.
2. `ait skill render review --profile <relevant> --agent claude` produces expected output for each agent.
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
