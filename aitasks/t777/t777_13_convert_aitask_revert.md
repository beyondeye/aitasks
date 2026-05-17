---
priority: medium
effort: medium
depends: [t777_12]
issue_type: refactor
status: Ready
labels: [aitask_pick]
created_at: 2026-05-17 12:00
updated_at: 2026-05-17 12:00
---

## Context

Depends on t777_6 (pilot) and t777_7. Converts `aitask-revert` SKILL.md to templated pattern across all 4 agents.

## Key Files to Modify

- `.claude/skills/aitask-revert/SKILL.md.j2` (new)
- `.claude/skills/aitask-revert/SKILL.md` (replace) — stub
- `.agents/skills/aitask-revert/SKILL.md` (replace) — stub
- `.gemini/skills/aitask-revert/SKILL.md` (replace) — stub
- `.opencode/skills/aitask-revert/SKILL.md` (replace) — stub

## Implementation Plan

Same procedure as t777_8/t777_10/t777_11:
1. Grep SKILL.md for "Profile check:" blocks.
2. Convert each to `{% if profile.<key> %}…{% else %}…{% endif %}`.
3. Wrap literal `{{`/`{%` in `{% raw %}`.
4. Frontmatter `name: aitask-revert-{{ profile.name }}`.
5. Author 4 stubs per `task-workflow/stub-skill-pattern.md`.

## Verification Steps

1. `ait skill verify` passes.
2. `ait skill render revert --profile fast --agent claude` produces expected output.
3. Stub-dispatch end-to-end on all 4 agents.
