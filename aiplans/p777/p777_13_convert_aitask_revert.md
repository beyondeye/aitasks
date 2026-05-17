---
Task: t777_13_convert_aitask_revert.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_*_*.md
Parent Plan: aiplans/p777_modular_pick_skill.md
Base branch: main
---

# Plan: t777_13 — Convert `aitask-revert` across all 4 agents

## Scope

Mirror of t777_6 (pilot) for `aitask-revert`. Profile keys: identify by grep at impl time.

## Step Order

1. Author `.claude/skills/aitask-revert/SKILL.md.j2`.
2. Replace `<each-agent>/skills/aitask-revert/SKILL.md` with stubs.
3. Render + verify across all 4 agents.

## Critical Files

- `.claude/skills/aitask-revert/SKILL.md.j2` (new)
- 4 × `<agent>/skills/aitask-revert/SKILL.md` (replace with stubs)

## Verification

`ait skill verify` passes; stub-dispatch end-to-end.
