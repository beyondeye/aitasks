---
Task: t129_1_extract_shared_workflow.md
Parent Task: aitasks/t129_dynamic_task_skill.md
Sibling Tasks: aitasks/t129/t129_2_*.md, aitasks/t129/t129_3_*.md, aitasks/t129/t129_4_*.md, aitasks/t129/t129_5_*.md, aitasks/t129/t129_6_*.md
Worktree: N/A (working on current branch)
Branch: main
Base branch: main
---

# Plan: Extract Shared Workflow from aitask-pick (t129_1)

## Context

The `aitask-pick` SKILL.md is a monolithic 872-line file. To enable new skills (`aitask-explore`, `aitask-review`) to reuse the implementation pipeline (Steps 3-9) without duplication, we extract the shared workflow into an internal `task-workflow` skill. The calling skill handles task selection (Steps 0-2), then hands off to the shared workflow.

## Files to Create/Modify

1. **Create** `.claude/skills/task-workflow/SKILL.md` (~570 lines)
2. **Modify** `.claude/skills/aitask-pick/SKILL.md` (reduce to ~250 lines)

## Implementation Steps

### Step 1: Create `.claude/skills/task-workflow/SKILL.md`

- [x] Create directory and file
- [x] YAML frontmatter with `user-invocable: false`
- [x] Context Requirements section (8 variables table)
- [x] Copy Steps 3-9 verbatim from aitask-pick
- [x] Copy Task Abort, Issue Update, Lock Release procedures
- [x] Shared notes section
- [x] Execution Profiles schema + customization guide

### Step 2: Update `.claude/skills/aitask-pick/SKILL.md`

- [x] Keep Steps 0a-2 unchanged (lines 1-209)
- [x] Replace Steps 3-9 with handoff section
- [x] Trimmed Notes with pick-specific items only
- [x] Pointer to task-workflow for full schema

### Step 3: Verify

- [x] Read both files, confirm no content lost
- [x] Check cross-references are self-consistent
- [x] Count lines in both files

## Key Design Decisions

- Keep original step numbering (3-9) in task-workflow
- Profile schema lives entirely in task-workflow
- "Read and follow" handoff — markdown instruction to read the other skill file

## Final Implementation Notes
- **Actual work done:** Created `.claude/skills/task-workflow/SKILL.md` (681 lines) as an internal skill with `user-invocable: false`. Extracted Steps 3-9, all three procedures (Task Abort, Issue Update, Lock Release), shared notes, and the full Execution Profiles section. Updated `.claude/skills/aitask-pick/SKILL.md` (232 lines, down from 872) to keep Steps 0-2 and add a handoff section with 8 context variables.
- **Deviations from plan:** The task-workflow file came out at 681 lines instead of the estimated ~570 — the Context Requirements section and careful formatting added some lines. The aitask-pick file is 232 lines instead of ~250, slightly smaller than estimated.
- **Issues encountered:** The `.gitignore` has a `skills/` rule that ignores `.claude/skills/` for new files. Existing skills were tracked before the rule was added. Used `git add -f` to force-add the new task-workflow skill file past the gitignore. Also needed minor fix for a missing blank line between Step 2d and the new Step 3 handoff.
- **Key decisions:** (1) Kept original step numbering (3-9) in task-workflow to avoid breaking cross-references in profile schema, within-document references, and user familiarity. (2) Placed the full Execution Profiles schema in task-workflow since most keys are consumed in Steps 4-6; aitask-pick just has a pointer. (3) One small wording change in Step 4: "return to **Step 2** (task selection)" became "return to the calling skill's task selection" since the shared workflow doesn't have a Step 2.
- **Notes for sibling tasks:** The task-workflow skill is now at `.claude/skills/task-workflow/SKILL.md` with `user-invocable: false`. Future skills (t129_2 aitask-explore, t129_4 aitask-review) should follow the same handoff pattern as aitask-pick: set the 8 context variables, then instruct the executor to "read and follow `.claude/skills/task-workflow/SKILL.md` starting from Step 3." The `.gitignore` `skills/` rule means new skill files need `git add -f` to be tracked.
