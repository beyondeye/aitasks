---
priority: medium
effort: medium
depends: [1]
issue_type: feature
status: Ready
labels: [ait_settings, execution_profiles]
created_at: 2026-03-22 10:21
updated_at: 2026-03-22 10:21
---

Ensure default_profiles renders and edits correctly in Project Config tab of settings TUI. Validate keys are valid skill names, values are strings (profile names). The existing _format_yaml_value() + ConfigRow approach handles dict display.
