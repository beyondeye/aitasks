---
Task: t884_2_risk_evaluation_profile_key.md
Parent Task: aitasks/t884_add_task_risk_evaluation_in_planning.md
Sibling Tasks: aitasks/t884/t884_*.md
Archived Sibling Plans: aiplans/archived/p884/p884_*_*.md
Worktree: aiwork/t884_2_risk_evaluation_profile_key
Branch: aitask/t884_2_risk_evaluation_profile_key
Base branch: main
---

# Plan: t884_2 — `risk_evaluation` execution-profile key (data layer)

> Parent architecture & decisions: `aiplans/p884_add_task_risk_evaluation_in_planning.md`.

## Goal

Register the single bool toggle `risk_evaluation` that gates the whole risk
feature. **Data layer only** — no Jinja consumption here (t884_3/t884_4 own that).
**Absent ⇒ disabled**; never seed it `true`.

## Steps

1. **`.aitask-scripts/lib/profile_editor.py`** — add `risk_evaluation`:
   - `PROFILE_SCHEMA` (~46): `"risk_evaluation": ("bool", None)`.
   - `PROFILE_FIELD_INFO` (~99): short ("Enable risk evaluation during planning") + long help (assesses code-health + goal-achievement risk at end of planning; gates the eval step and the mitigation offer; opt-in).
   - `PROFILE_FIELD_GROUPS` (~300): add to the **"Planning"** group.
   The settings TUI auto-discovers the key from these three structures.
2. **`.claude/skills/task-workflow/profiles.md`** — add a schema-table row: `risk_evaluation | bool | (off) | gates the risk-evaluation step + mitigation offer (planning §6.1 / Step 7 / Step 8d)`.
3. **Profile YAMLs** — leave `aitasks/metadata/profiles/{default,fast,remote}.yaml` and `seed/profiles/*` unchanged (absent = off).

## Verification

- `ait settings` → Profiles tab: key renders under Planning, cycles, saves, round-trips.
- `python -c "import ast,sys; ast.parse(open('.aitask-scripts/lib/profile_editor.py').read())"`; run profile_editor tests if present.

## Notes for sibling tasks

t884_3/t884_4 add the `{% if profile.risk_evaluation %}` gates and regenerate goldens. No goldens change here (no skill/closure edits).
