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

## Final Implementation Notes

- **Actual work done:** Added a final Satisfaction Feedback step to `.claude/skills/aitask-explain/SKILL.md`, `.claude/skills/aitask-changelog/SKILL.md`, `.claude/skills/aitask-refresh-code-models/SKILL.md`, `.claude/skills/aitask-reviewguide-classify/SKILL.md`, `.claude/skills/aitask-reviewguide-merge/SKILL.md`, and `.claude/skills/aitask-reviewguide-import/SKILL.md`, each pointing at `.claude/skills/task-workflow/procedures.md` with the correct `skill_name`.
- **Deviations from plan:** For the three reviewguide skills, the feedback step was written as a single final workflow step that explicitly covers both single-item and batch endings, rather than duplicating separate instructions at both completion points.
- **Issues encountered:** No implementation issues; this was a documentation-only update.
- **Key decisions:** Kept `aitask-explain`, `aitask-changelog`, and `aitask-refresh-code-models` as simple next-numbered steps, while the reviewguide skills use wording that guarantees one feedback prompt after overall workflow completion and avoids per-item prompts in batch runs.
- **Notes for sibling tasks:** The shared Satisfaction Feedback Procedure can be reused by adding one final step near the true end of a skill's user-visible flow. For mixed single/batch workflows, it is clearer to describe one final step that references both end states than to duplicate feedback instructions in multiple branches.
