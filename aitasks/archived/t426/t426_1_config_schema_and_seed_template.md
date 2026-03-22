---
priority: medium
effort: low
depends: []
issue_type: feature
status: Done
labels: [ait_settings, execution_profiles]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-22 10:21
updated_at: 2026-03-22 10:49
completed_at: 2026-03-22 10:49
---

Add default_profiles config key to seed/project_config.yaml (commented example block) and PROJECT_CONFIG_SCHEMA in settings_app.py. Schema: flat dict mapping skill names (pick, fold, review, pr-import, revert, explore, pickrem, pickweb, qa) to profile names (without .yaml). Both project_config.yaml (team) and userconfig.yaml (personal) support the key; userconfig overrides project_config per-skill.
