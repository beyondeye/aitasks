---
priority: medium
effort: low
depends: []
issue_type: documentation
status: Done
labels: [claudeskills]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-22 14:45
updated_at: 2026-02-23 08:50
completed_at: 2026-02-23 08:50
---

all aitasks skill are designed to run from the git repo root directory as the current directory. if we run one of the skill not from the root directory it will start to ask a million confirmation requests, because all custom preconfigured claude code permissions in ./claude/settings.local.json are defined for path relative to the root directory. there should be a warning when running of the aitasks skills (like pick) not from project root directory
