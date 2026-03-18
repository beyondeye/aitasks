---
Task: t418_organize_aidocs_subdirectories.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

The `aidocs/` directory has grown flat with mixed-topic documents. Two brainstorming docs are untracked and two agentcrew docs should be grouped. This task organizes them into subdirectories.

## Plan

### 1. Create subdirectories and move files

**Brainstorming docs** (untracked — use `mv` + `git add`):
- `aidocs/aitask_redesign_spec.md` → `aidocs/brainstorming/aitask_redesign_spec.md`
- `aidocs/building_an_iterative_ai_design_system.md` → `aidocs/brainstorming/building_an_iterative_ai_design_system.md`

**Agentcrew docs** (tracked — use `git mv`):
- `aidocs/agentcrew_architecture.md` → `aidocs/agentcrew/agentcrew_architecture.md`
- `aidocs/agentcrew_work2do_guide.md` → `aidocs/agentcrew/agentcrew_work2do_guide.md`

### 2. Update references to moved files

Active task files that reference the old paths:
- `aitasks/t399_aitaskredesign.md` — update `agentcrew_architecture.md and agentcrew_work2do_guide.md in aidocs` to new paths
- `aitasks/t399/t399_1_redesign_workflow_spec.md` — update `aidocs/agentcrew_architecture.md` and `aidocs/agentcrew_work2do_guide.md`

Archived references (`aitasks/archived/t386/t386_6_*`) left as-is (historical).

### 3. Commit

- Code commit: `git add` + `git commit` for `aidocs/` changes
- Task file commit: `./ait git add` + `./ait git commit` for `aitasks/` reference updates

## Verification

- `ls aidocs/brainstorming/` shows 2 files
- `ls aidocs/agentcrew/` shows 2 files
- Old paths no longer exist
- `grep -r "aidocs/agentcrew_" aitasks/*.md aitasks/t399/` returns no matches

## Final Implementation Notes
- **Actual work done:** Moved 4 files into 2 new subdirectories as planned. Updated all references in active task and plan files (t399, t399_1, t399_2, plus plan files p399, p399_1, p399_2).
- **Deviations from plan:** Additional references found in t399_2 and all three p399 plan files — updated those too.
- **Issues encountered:** None.
- **Key decisions:** Left archived references (t386_6) untouched as historical records.

## Post-Implementation

Step 9: archive task t418, push.
