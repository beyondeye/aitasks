---
priority: medium
effort: medium
depends: [1]
issue_type: feature
status: Done
labels: [ait_settings, execution_profiles]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-22 10:21
updated_at: 2026-03-22 12:26
completed_at: 2026-03-22 12:26
---

Ensure default_profiles renders and edits correctly in Project Config tab of settings TUI. Validate keys are valid skill names, values are strings (profile names). The existing _format_yaml_value() + ConfigRow approach handles dict display.
