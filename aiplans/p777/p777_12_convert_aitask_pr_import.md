---
Task: t777_12_convert_aitask_pr_import.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_*_*.md
Parent Plan: aiplans/p777_modular_pick_skill.md
Base branch: main
---

# Plan: t777_12 — Convert `aitask-pr-import` across all 4 agents

## Scope

Mirror of t777_6 (pilot) for `aitask-pr-import`. Profile keys: identify by grep at impl time.

## Step Order

1. Author `.claude/skills/aitask-pr-import/SKILL.md.j2`.
2. Replace `<each-agent>/skills/aitask-pr-import/SKILL.md` with stubs.
3. Render + verify across all 4 agents.

## Critical Files

- `.claude/skills/aitask-pr-import/SKILL.md.j2` (new)
- 4 × `<agent>/skills/aitask-pr-import/SKILL.md` (replace with stubs)

## Verification

`ait skill verify` passes; stub-dispatch end-to-end.
