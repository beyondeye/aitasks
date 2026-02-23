---
priority: medium
effort: medium
depends: []
issue_type: documentation
status: Ready
labels: [website, documentation]
created_at: 2026-02-23 09:04
updated_at: 2026-02-23 09:04
---

Add a new Remote Development workflow page in the workflows section of the website. Explain how to use aitask-pick-remote for remote/web-based development sessions that require less user interaction. Cover: 1) When to use remote mode vs standard aitask-pick (Claude Code Web, reduced interaction needs). 2) How the workflow differs: task ID required as argument, profile-driven decisions, no worktree management, auto-commit after implementation. 3) The planning step is still fully supported (EnterPlanMode/ExitPlanMode work). 4) Testing emphasis for code changes since there is no user review step. 5) How to set up and customize the remote execution profile. 6) Example invocation: /aitask-pick-remote 42. Reference: .claude/skills/aitask-pick-remote/SKILL.md and aitasks/metadata/profiles/remote.yaml.
