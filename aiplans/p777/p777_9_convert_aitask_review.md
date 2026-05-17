---
Task: t777_9_convert_aitask_review.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_*_*.md
Parent Plan: aiplans/p777_modular_pick_skill.md
Base branch: main
---

# Plan: t777_9 — Convert `aitask-review` across all 4 agents

## Scope

Mirror of t777_6 (pilot) for `aitask-review`. Follow the canonical stub pattern from `task-workflow/stub-skill-pattern.md` (t777_3) and any patterns documented in t777_6's Final Implementation Notes. Identify profile keys by grep at impl time.

## Step Order

1. Author `.claude/skills/aitask-review/SKILL.md.j2`.
2. Replace `<each-agent>/skills/aitask-review/SKILL.md` with stubs.
3. Render + verify across all 4 agents.

## Critical Files

- `.claude/skills/aitask-review/SKILL.md.j2` (new)
- 4 × `<agent>/skills/aitask-review/SKILL.md` (replace with stubs)

## Verification

`ait skill verify` passes; render produces expected content; stub-dispatch end-to-end on all 4 agents.
