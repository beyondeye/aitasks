---
Task: t303_5_feedback_in_standalone_skills.md
Parent Task: aitasks/t303_automatic_update_of_model_verified_score.md
Sibling Tasks: aitasks/t303/t303_1_*.md, aitasks/t303/t303_2_*.md, aitasks/t303/t303_3_*.md, aitasks/t303/t303_4_*.md
Worktree: (current directory)
Branch: (current branch)
Base branch: main
---

# Plan: t303_5 — Feedback in Standalone Skills

## Steps

### Add Satisfaction Feedback Procedure call to each skill

For each skill, add a final step referencing the procedure with the appropriate `skill_name`:

1. **aitask-explain** → `skill_name: "explain"` — after user selects "Done"
2. **aitask-changelog** → `skill_name: "changelog"` — after commit
3. **aitask-refresh-code-models** → `skill_name: "refresh-code-models"` — after commit
4. **aitask-reviewguide-classify** → `skill_name: "reviewguide-classify"` — after completion (once at end, not per-file in batch)
5. **aitask-reviewguide-merge** → `skill_name: "reviewguide-merge"` — after completion
6. **aitask-reviewguide-import** → `skill_name: "reviewguide-import"` — after completion

## Files to modify (6 total)

- `.claude/skills/aitask-explain/SKILL.md`
- `.claude/skills/aitask-changelog/SKILL.md`
- `.claude/skills/aitask-refresh-code-models/SKILL.md`
- `.claude/skills/aitask-reviewguide-classify/SKILL.md`
- `.claude/skills/aitask-reviewguide-merge/SKILL.md`
- `.claude/skills/aitask-reviewguide-import/SKILL.md`

## Verification

- Each skill has feedback step in correct position
- Batch-mode skills ask once at end, not per-item

## Step 9 Reference
Post-implementation: archive via task-workflow Step 9.
