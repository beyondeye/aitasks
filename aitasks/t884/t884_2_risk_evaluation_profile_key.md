---
priority: high
effort: low
depends: [t884_1]
issue_type: enhancement
status: Implementing
labels: [task_workflow, execution_profiles, ait_settings]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-01 00:30
updated_at: 2026-06-01 12:14
---

## Context

Child of t884 (see `aiplans/p884_add_task_risk_evaluation_in_planning.md`). Adds the **single** execution-profile toggle `risk_evaluation` (bool) that gates the whole risk feature — both the risk-evaluation planning step (t884_3) and the mitigation offer (t884_4). This child is the **data layer only**: register the key in the schema + settings editor + profile YAMLs. The Jinja consumption that actually branches on it lives in t884_3/t884_4.

**Blast radius: absent ⇒ feature OFF.** Do NOT seed `risk_evaluation: true` in any profile. `{% if profile.risk_evaluation %}` is Jinja-falsy on undefined, so existing users see zero change until they opt in.

## Key Files to Modify

- `.claude/skills/task-workflow/profiles.md` — add a schema-table row documenting `risk_evaluation` (bool; default absent ⇒ disabled; gates the risk-evaluation step + mitigation offer at planning §6.1 / Step 7 / Step 8d).
- `.aitask-scripts/lib/profile_editor.py` — add `risk_evaluation` to `PROFILE_SCHEMA` (~line 46, `("bool", None)`), `PROFILE_FIELD_INFO` (~99, short + long help), and `PROFILE_FIELD_GROUPS` (~300, insert into the "Planning" group). The settings TUI auto-discovers it from these three structures — no other editor code change.
- Runtime profile YAMLs `aitasks/metadata/profiles/{default,fast,remote}.yaml` and seed copies `seed/profiles/{default,fast,remote}.yaml` — **do NOT add the key** (leaving it absent = disabled). Touch these only if a future decision wants it on for a specific profile; default is off everywhere.

## Reference Files for Patterns

- An existing bool key, e.g. `qa_run_tests` or `explore_auto_continue`, shows the `PROFILE_SCHEMA`/`PROFILE_FIELD_INFO`/`PROFILE_FIELD_GROUPS` triple and the profiles.md row format.
- `manual_verification_followup_mode` is the closest semantic analog (a profile key gating a follow-up offer).

## Implementation Plan

1. Add the `("bool", None)` schema entry, help text, and group placement in `profile_editor.py`.
2. Add the profiles.md documentation row.
3. Leave all profile YAMLs unchanged (absent = off). Confirm the settings TUI renders/saves the new key.

## Verification Steps

- `ait settings` → Profiles tab → confirm `risk_evaluation` appears under Planning, cycles true/false/(unset), and saves to YAML; reload round-trips.
- Edit a profile to set `risk_evaluation: true`, save, reopen → value persists. Remove it → renders as unset.
- `python -c "import ast; ast.parse(open('.aitask-scripts/lib/profile_editor.py').read())"` (syntax) and run any profile_editor unit tests.

## Notes for sibling tasks

t884_3 and t884_4 consume this key via `{% if profile.risk_evaluation %}` at their dispatch sites and must regenerate goldens. This child does NOT add Jinja anywhere.
