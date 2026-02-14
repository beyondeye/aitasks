---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [aitasks, bash]
created_at: 2026-02-14 22:01
updated_at: 2026-02-14 22:01
---

currently in order to install aitasks in a project, there are two steps 1) run the install command, after curl (see the README.md) 2) run ait step. the ait is currently a "shim" to the current directory ait.sh. It would be nice if, once, aitasks is installed in some project directory, to make it possible running ait setup in a new project directory, it will also be initialized automatically. what changes would be required to support such feature? what are the possible options? ask me questions if you need clarifications.
