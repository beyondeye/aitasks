---
Task: t303_3_feedback_in_task_workflow_skills.md
Parent Task: aitasks/t303_automatic_update_of_model_verified_score.md
Sibling Tasks: aitasks/t303/t303_1_*.md, aitasks/t303/t303_2_*.md, aitasks/t303/t303_4_*.md, aitasks/t303/t303_5_*.md
Worktree: (current directory)
Branch: (current branch)
Base branch: main
---

# Plan: t303_3 — Feedback in Task-Workflow Skills

## Steps

### 1. Update task-workflow SKILL.md

- Add `skill_name` to context variables table
- Add Step 9b (Satisfaction Feedback) after archival push

### 2. Update calling skills' handoff sections

Add `skill_name` context variable to each skill's handoff:
- aitask-pick → `"pick"`
- aitask-explore → `"explore"`
- aitask-pr-import → `"pr-import"`
- aitask-fold → `"fold"`
- aitask-review → `"review"`

### 3. Add feedback to aitask-wrap and aitask-web-merge

Add new final step referencing Satisfaction Feedback Procedure.

### 4. Note on pickrem/pickweb

Add note that feedback is skipped (non-interactive).

## Files to modify (8 total)

- `.claude/skills/task-workflow/SKILL.md`
- `.claude/skills/aitask-pick/SKILL.md`
- `.claude/skills/aitask-explore/SKILL.md`
- `.claude/skills/aitask-pr-import/SKILL.md`
- `.claude/skills/aitask-fold/SKILL.md`
- `.claude/skills/aitask-review/SKILL.md`
- `.claude/skills/aitask-wrap/SKILL.md`
- `.claude/skills/aitask-web-merge/SKILL.md`

## Verification

- Walk through aitask-pick flow: feedback appears after archival
- skill_name is set correctly in all 5 calling skills

## Step 9 Reference
Post-implementation: archive via task-workflow Step 9.
