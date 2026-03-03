---
priority: low
effort: high
depends: []
issue_type: feature
status: Ready
labels: [install_scripts]
created_at: 2026-03-03 17:01
updated_at: 2026-03-03 17:01
---

Explore the feasibility of a global or partial-global installation mode for aitasks. Currently, aitasks must be installed per-project at the git repo root, with all scripts, skills, and configuration committed to the repository. A global install would need to handle: (1) skill definitions that code agents expect in per-project paths like .claude/skills/, (2) version management when different projects need different aitasks versions, (3) the ait dispatcher finding shared scripts vs project-local overrides, (4) keeping task data per-project while sharing the framework. Consider a hybrid approach where only the ait dispatcher and aiscripts/ are global, with per-project symlinks or a discovery mechanism. Document trade-offs and recommend an approach or explain why full per-project installation remains the best design.
