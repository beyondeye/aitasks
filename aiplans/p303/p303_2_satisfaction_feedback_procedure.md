---
Task: t303_2_satisfaction_feedback_procedure.md
Parent Task: aitasks/t303_automatic_update_of_model_verified_score.md
Sibling Tasks: aitasks/t303/t303_1_*.md, aitasks/t303/t303_3_*.md, aitasks/t303/t303_4_*.md, aitasks/t303/t303_5_*.md
Worktree: (current directory)
Branch: (current branch)
Base branch: main
---

# Plan: t303_2 — Satisfaction Feedback Procedure

## Steps

### 1. Add Model Self-Detection Sub-Procedure to procedures.md

Extract detection logic from current Agent Attribution Procedure into standalone sub-procedure. Input: none. Output: agent string.

### 2. Refactor Agent Attribution Procedure

Replace inline detection with: "Execute Model Self-Detection Sub-Procedure to get agent_string."

### 3. Add Satisfaction Feedback Procedure

New section in procedures.md with:
- Profile check (`skip_satisfaction_feedback`)
- Call Model Self-Detection
- AskUserQuestion with 4 options (5/4/3/1-2 stars)
- Call `aitask_verified_update.sh` with result
- Display updated score

### 4. Update SKILL.md procedures list

Add the two new procedures to the reference list.

## Verification

- procedures.md is internally consistent
- Agent Attribution still works after refactor
- New procedure references correct script paths

## Step 9 Reference
Post-implementation: archive via task-workflow Step 9.
