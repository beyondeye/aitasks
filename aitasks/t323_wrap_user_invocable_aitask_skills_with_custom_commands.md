---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [claudeskills, opencode, codexcli, geminicli]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-06 11:40
updated_at: 2026-03-06 12:49
---

Add custom command wrappers (for opencode) for existing aitask skills that are marked user-invocable in corresponding Claude skill frontmatter. Build or refresh command files for supported CLIs and skip non-invocable skills. Include a mapping checklist and acceptance checks that no command is generated for user-invocable:false skills.
