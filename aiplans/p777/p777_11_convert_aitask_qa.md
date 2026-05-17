---
Task: t777_11_convert_aitask_qa.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_*_*.md
Parent Plan: aiplans/p777_modular_pick_skill.md
Base branch: main
---

# Plan: t777_11 — Convert `aitask-qa` across all 4 agents

## Scope

Mirror of t777_6 (pilot) for `aitask-qa`. Profile keys: `qa_mode` (enum: ask|create_task|implement|plan_only), `qa_run_tests` (bool), `qa_tier` (enum: q|s|e). Uses `{% if … == "X" %}/{% elif … == "Y" %}` for enums.

## Step Order

1. Author `.claude/skills/aitask-qa/SKILL.md.j2` — convert each enum-driven block to multi-branch `{% if %}/{% elif %}`.
2. Replace `<each-agent>/skills/aitask-qa/SKILL.md` with stubs.
3. Render + verify across all 4 agents — confirm only the relevant branch appears per profile.

## Critical Files

- `.claude/skills/aitask-qa/SKILL.md.j2` (new)
- 4 × `<agent>/skills/aitask-qa/SKILL.md` (replace with stubs)

## Verification

`ait skill verify` passes; render-per-`qa_mode` produces only the relevant branch; stub-dispatch end-to-end.
