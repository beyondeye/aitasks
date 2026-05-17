---
Task: t777_8_convert_aitask_explore.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_*_*.md
Parent Plan: aiplans/p777_modular_pick_skill.md
Base branch: main
---

# Plan: t777_8 — Convert `aitask-explore` across all 4 agents

## Scope

Mirror of t777_6 (pilot) for `aitask-explore`. Smaller surface — primary profile key: `explore_auto_continue`. Follow the canonical stub pattern from `task-workflow/stub-skill-pattern.md` (t777_3) and any patterns/gotchas documented in t777_6's Final Implementation Notes.

## Step Order

Same as t777_6 (abbreviated):
1. Author `.claude/skills/aitask-explore/SKILL.md.j2`.
2. Replace `<each-agent>/skills/aitask-explore/SKILL.md` with stubs.
3. Render + verify across all 4 agents.

## Critical Files

- `.claude/skills/aitask-explore/SKILL.md.j2` (new)
- 4 × `<agent>/skills/aitask-explore/SKILL.md` (replace with stubs)

## Verification

`ait skill verify` passes; `ait skill render explore --profile fast --agent claude` produces expected content; stub-dispatch end-to-end on all 4 agents.
