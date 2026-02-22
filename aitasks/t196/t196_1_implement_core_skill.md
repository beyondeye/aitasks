---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: []
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-22 11:33
updated_at: 2026-02-22 11:37
---

Implement the core aitask-wrap skill: create SKILL.md in .claude/skills/aitask-wrap/, implement the workflow that (1) detects uncommitted changes via git diff, (2) analyzes the diff to generate a brief aitask summary and a detailed aiplan with probable user intent, (3) presents the analysis to the user for confirmation/adjustment, (4) creates the actual task and plan files using aitask_create.sh batch mode, (5) optionally stages and commits.
