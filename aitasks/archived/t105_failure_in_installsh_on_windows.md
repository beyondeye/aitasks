---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Done
labels: [aitasks, install_scripts]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-13 00:30
updated_at: 2026-02-13 00:42
completed_at: 2026-02-13 00:42
---

when running the curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh | bash on windows, the installation fails silently when the script ask if Install these Claude Code permissions? [Y/n]. can you help me debug the issue?

What is strange is that when I run ait setup in the same directory, it asks me the same question but does not fails immediately.
