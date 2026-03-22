---
priority: medium
effort: medium
depends: [t426_1, 1]
issue_type: feature
status: Implementing
labels: [execution_profiles]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-22 10:21
updated_at: 2026-03-22 10:57
---

Modify execution-profile-selection.md and execution-profile-selection-auto.md to accept skill_name and profile_override parameters. Add resolution logic before existing scan/select: override -> default -> interactive/auto. Default lookup reads userconfig.yaml then project_config.yaml (userconfig wins per-skill). Display messages for override and default profile usage.
