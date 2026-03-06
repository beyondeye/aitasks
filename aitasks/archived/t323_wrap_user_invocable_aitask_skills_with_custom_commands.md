---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Done
labels: [claudeskills, opencode, codexcli, geminicli]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-06 11:40
updated_at: 2026-03-06 12:59
completed_at: 2026-03-06 12:59
---

Add custom command wrappers (for opencode) for existing aitask skills that are marked user-invocable in corresponding Claude skill frontmatter. Build or refresh command files for supported CLIs and skip non-invocable skills. Include a mapping checklist and acceptance checks that no command is generated for user-invocable:false skills.
