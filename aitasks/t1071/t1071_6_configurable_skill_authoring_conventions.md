---
priority: medium
effort: medium
depends: [t1071_2]
issue_type: enhancement
status: Implementing
labels: [shadow, claudeskills]
assigned_to: dario-e@beyond-eye.com
anchor: 1071
created_at: 2026-06-30 11:16
updated_at: 2026-07-01 11:41
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
