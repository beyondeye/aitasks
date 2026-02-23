---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Done
labels: []
created_at: 2026-02-22 11:32
updated_at: 2026-02-22 13:02
completed_at: 2026-02-22 13:02
---

New Claude Code skill: aitask-wrap. When the user has uncommitted changes in the repo, this skill analyzes the diff, creates a retroactive aitask (brief summary of the changes) and an aiplan (detailed description of changes and probable user intent), then asks the user to confirm or adjust Claude understanding. The goal is to enclose any ad-hoc changes into the aitasks framework for proper documentation and traceability, even when changes were initiated outside the framework.
