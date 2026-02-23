---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [install_scripts]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-23 14:48
updated_at: 2026-02-23 14:50
---

currently calls to ait git are not whitelisted in seed/claude_settings.local.json. there are skill that call this commands, and should be included in the default list of whitelisted commands when ait setup is run
