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

Placement details:
- `aitask-wrap`: add Step 6 after the wrap summary so feedback covers the full wrap flow
- `aitask-web-merge`: add Step 7 after the push/cleanup section so feedback is asked once per merge run, not once per processed branch

### 4. pickrem/pickweb scope note

Do not modify `aitask-pickrem` or `aitask-pickweb` in this task. They are already explicitly excluded as non-interactive in sibling task `t303_5`, so this child stays focused on task-workflow handoff skills plus `wrap` and `web-merge`.

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
- `aitask-wrap` and `aitask-web-merge` call the shared procedure from their new final steps

## Step 9 Reference
Post-implementation: archive via task-workflow Step 9.

## Final Implementation Notes

- **Actual work done:** Added `skill_name` to the task-workflow context requirements, inserted Step 9b so shared-workflow skills can trigger Satisfaction Feedback after archival push, and updated the five shared-workflow callers (`aitask-pick`, `aitask-explore`, `aitask-pr-import`, `aitask-fold`, `aitask-review`) to pass their feedback skill keys. Also added final feedback steps to `aitask-wrap` and `aitask-web-merge` that point to the shared procedure in `.claude/skills/task-workflow/procedures.md`.
- **Deviations from plan:** Kept `aitask-pickrem` and `aitask-pickweb` unchanged here because sibling task `t303_5` already documents them as explicitly excluded non-interactive skills. No note was added in this child task to avoid duplicating that sibling scope.
- **Issues encountered:** None during the documentation-only edits.
- **Key decisions:** Placed `aitask-wrap` feedback after the wrap summary and `aitask-web-merge` feedback after the cleanup stage so each skill asks once per completed run rather than during intermediate branch-processing steps.
- **Notes for sibling tasks:** The shared workflow now expects a `skill_name` context variable whenever a caller wants automatic post-archival feedback. Later standalone-skill work should continue to reuse `.claude/skills/task-workflow/procedures.md` directly instead of duplicating the feedback instructions.
