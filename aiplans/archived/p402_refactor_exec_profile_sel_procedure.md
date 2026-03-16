---
Task: t402_refactor_exec_profile_sel_procedure.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: Refactor Execution Profile Selection Procedure (t402)

## Context

The execution profile selection procedure was duplicated verbatim across 6 interactive skills and had a separate variant in 2 remote skills. This refactoring extracts each variant into its own shared file, following the same pattern used by other shared procedures (task-abort.md, issue-update.md, etc.).

## Steps

1. [x] Create `.claude/skills/task-workflow/execution-profile-selection.md` — interactive variant
2. [x] Create `.claude/skills/task-workflow/execution-profile-selection-auto.md` — auto-select variant
3. [x] Update 6 interactive skills to reference `execution-profile-selection.md`
4. [x] Update 2 remote skills to reference `execution-profile-selection-auto.md`
5. [x] Update task-workflow/SKILL.md Step 3b + Procedures section
6. [x] Verify: only the two new files contain `aitask_scan_profiles`

## Step 9: Post-Implementation

Archive task, push changes.

## Final Implementation Notes

- **Actual work done:** Created two shared procedure files and updated all 8 calling skills + task-workflow to reference them instead of duplicating the procedure inline.
- **Deviations from plan:** None — implemented exactly as planned.
- **Issues encountered:** None.
- **Key decisions:** Added `active_profile_filename` storage instruction to the interactive procedure — previously only explicit in aitask-revert but needed by all skills. Used `mode_label` input parameter in auto-select variant to customize display messages per calling skill.
