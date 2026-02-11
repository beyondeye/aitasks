---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Done
labels: [aitasks, claudeskills]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-11 16:26
updated_at: 2026-02-11 19:13
completed_at: 2026-02-11 19:13
---

aitask-pick cluade skill is a multistep feature that require to give assent to a lot of operations that calude do, this can be annoying, especially in the beginning when the user did not give assent for most comoon operations that are required to run the workflow. there soube a default ./claude/.settings.local.json that include the most common operations required by the aitask-pick workflow that when running the install.sh script should be merged with the current settings.local.json (or written if not existing) to give claude code this permission: at the time of installation the install script should ask permission from the user, and show the actual content of the settings.local.json that will be merged. need to update the git workflow that create the tarball for installation to include this file and need to store this file in a project dir lets say claaudecode_permissions

ask me questions if you need more clarificaitons
