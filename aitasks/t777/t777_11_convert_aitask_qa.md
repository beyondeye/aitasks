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
- `.claude/skills/aitask-qa/SKILL.md` (replace) — stub
- `.agents/skills/aitask-qa/SKILL.md` (replace) — stub
- `.gemini/skills/aitask-qa/SKILL.md` (replace) — stub
- `.opencode/skills/aitask-qa/SKILL.md` (replace) — stub

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
