---
Task: t777_15_convert_aitask_pickweb.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_*_*.md
Parent Plan: aiplans/p777_modular_pick_skill.md
Base branch: main
---

# Plan: t777_15 — Convert `aitask-pickweb` across all 4 agents

## Scope

Mirror of t777_14 (pickrem). Likely shares many remote profile keys + may have web-specific keys.

## Step Order

1. Audit `aitask-pickweb/SKILL.md` for profile-key references.
2. Author `.claude/skills/aitask-pickweb/SKILL.md.j2`.
3. Replace `<each-agent>/skills/aitask-pickweb/SKILL.md` with stubs.
4. Render with `remote` profile and verify across all 4 agents.

## Critical Files

- `.claude/skills/aitask-pickweb/SKILL.md.j2` (new)
- 4 × `<agent>/skills/aitask-pickweb/SKILL.md` (replace with stubs)

## Verification

`ait skill verify` passes; stub-dispatch end-to-end.
