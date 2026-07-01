---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: [t1071_2]
issue_type: enhancement
status: Done
labels: [shadow, claudeskills]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1071
implemented_with: claudecode/opus4_8
created_at: 2026-06-30 11:16
updated_at: 2026-07-01 21:56
completed_at: 2026-07-01 21:56
---

Make the skill-authoring-conventions source that `aitask-learn-skill/generate.md` applies
**configurable**, instead of a hard-coded path.

## Why (from t1071_2 Change Request 1)
A skill a user generates for themselves must follow GENERIC skill-authoring best practices,
never the aitasks-framework-internal `aidocs/framework/skill_authoring_conventions.md`
(stubs/profile/goldens). When aitasks is installed in another repo it must not default to
framework conventions. t1071_2 set the default to the installed generic reviewguide
`aireviewguides/aiagents/skill_authoring_best_practices.md` (installed from `seed/` by
`ait setup`); this task adds the configurability layer.

## Requested behavior
- A setting for the conventions file path, **defaulting** to
  `aireviewguides/aiagents/skill_authoring_best_practices.md`.
- A control in the `ait settings` TUI (`aitask_settings.sh` / `.aitask-scripts/settings/`)
  to view/change it; persist the chosen value (settings store / project_config as
  appropriate).
- `generate.md` reads the configured path (falling back to the default when unset/missing)
  instead of the hard-coded reference it has today.

## Key files
- `.claude/skills/aitask-learn-skill/generate.md` (read configured path).
- `aitask_settings.sh` + `.aitask-scripts/settings/` (new control).
- settings persistence (mirror how other settings are stored).

## Verification
- Setting the path in `ait settings` persists and is read back by `generate.md`.
- Unset/missing → falls back to the generic reviewguide default.
- In a fresh repo (`ait setup`), the default reviewguide is present and used.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-01T12:03:09Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-01T18:55:29Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-07-01T18:56:27Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:a12a83f4ea8019d1

> **✅ gate:risk_evaluated** run=2026-07-01T18:56:27Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1071_6/risk_evaluated_2026-07-01T18:56:27Z-risk_evaluated-a1.log`
