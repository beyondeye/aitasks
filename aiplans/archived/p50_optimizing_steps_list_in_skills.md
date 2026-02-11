---
Task: t50_optimizing_steps_list_in_skills.md
Worktree: (current directory)
Branch: main
Base branch: main
---

# Plan: Remove Unnecessary Substep Numbering from aitask-pick Skill

## File to modify
- `.claude/skills/aitask-pick/SKILL.md`

## Changes
Convert all substep numbering (`X.Y.` format) to plain bullet points (`-`), keeping top-level Step numbers and sub-section labels (2a-2d) since those are cross-referenced.

## Post-Implementation
See Step 8 of aitask-pick workflow for cleanup, archival, and merge steps.
