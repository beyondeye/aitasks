---
priority: medium
effort: medium
depends: [t777_8]
issue_type: refactor
status: Ready
labels: [aitask_pick]
created_at: 2026-05-17 12:00
updated_at: 2026-05-17 12:00
---

## Context

Depends on t777_6 (pilot) and t777_7. Converts `aitask-review` SKILL.md to templated pattern across all 4 agents. Follows same procedure as t777_6/t777_8.

Profile keys consumed by review: identify by grep at impl time (likely `review_action` from remote profile, plus shared keys via task-workflow).

## Key Files to Modify

- `.claude/skills/aitask-review/SKILL.md.j2` (new) — template
- `.claude/skills/aitask-review/SKILL.md` (replace) — stub
- `.agents/skills/aitask-review/SKILL.md` (replace) — stub
- `.gemini/skills/aitask-review/SKILL.md` (replace) — stub
- `.opencode/skills/aitask-review/SKILL.md` (replace) — stub

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
