---
Task: t777_10_convert_aitask_fold.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_*_*.md
Parent Plan: aiplans/p777_modular_pick_skill.md
Base branch: main
---

# Plan: t777_10 — Convert `aitask-fold` across all 4 agents

## Scope

Mirror of t777_6 (pilot) for `aitask-fold`. Follow the canonical stub pattern from t777_3 and patterns from t777_6's Final Implementation Notes.

## Step Order

1. Author `.claude/skills/aitask-fold/SKILL.md.j2`.
2. Replace `<each-agent>/skills/aitask-fold/SKILL.md` with stubs.
3. Render + verify across all 4 agents.

## Critical Files

- `.claude/skills/aitask-fold/SKILL.md.j2` (new)
- 4 × `<agent>/skills/aitask-fold/SKILL.md` (replace with stubs)

## Verification

`ait skill verify` passes; stub-dispatch end-to-end on all 4 agents.
