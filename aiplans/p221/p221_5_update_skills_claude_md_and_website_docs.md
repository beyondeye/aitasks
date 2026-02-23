---
Task: t221_5_update_skills_claude_md_and_website_docs.md
Parent Task: aitasks/t221_move_aitasks_and_aiplans_to_separate_branch.md
Sibling Tasks: aitasks/t221/t221_6_*.md
Archived Sibling Plans: aiplans/archived/p221/p221_1_core_infrastructure_task_git_helper.md, aiplans/archived/p221/p221_2_update_write_scripts_to_use_task_git.md, aiplans/archived/p221/p221_3_setup_and_migration.md, aiplans/archived/p221/p221_4_update_python_board.md
Branch: main (no worktree)
---

# Plan: Update Skills, CLAUDE.md, and Website Docs (t221_5)

## Context

t221 moves task/plan data from `main` to an orphan `aitask-data` branch accessed via a permanent worktree at `.aitask-data/` with symlinks. Shell scripts (t221_1, t221_2) now use `task_git()` helpers. The Python board (t221_4) uses `_task_git_cmd()`. This task updates Claude Code skills that still have direct `git` commands on task/plan files, creates a safety-net skill, updates CLAUDE.md, and updates website docs.

## Steps

### Step 1: Update direct git commands in 5 skill files

- [x] 1a. `.claude/skills/task-workflow/SKILL.md` — 3 locations (child task creation, push after archival, abort procedure)
- [x] 1b. `.claude/skills/aitask-pickrem/SKILL.md` — abort workflow + push after archival
- [x] 1c. `.claude/skills/aitask-explore/SKILL.md` — amend commit
- [x] 1d. `.claude/skills/aitask-fold/SKILL.md` — fold commit
- [x] 1e. `.claude/skills/aitask-wrap/SKILL.md` — split mixed code+plan commit, add `./ait git push`

### Step 2: Create `.claude/skills/ait-git/SKILL.md`

- [x] Non-user-invocable safety net skill

### Step 3: Update CLAUDE.md

- [x] Add "Git Operations on Task/Plan Files" section after "Commit Message Format"

### Step 4: Update website documentation

- [x] 4a. `website/content/docs/board/reference.md` — Git Integration Details
- [x] 4b. `website/content/docs/development/_index.md` — Task Data Branch section
- [x] 4c. `website/content/docs/workflows/parallel-development.md` — mention aitask-data branch

### Step 5: Verify

- [x] Grep for remaining direct git on task/plan paths in skills
- [x] Hugo build

## Final Implementation Notes
- **Actual work done:** Updated 5 skill files (task-workflow, aitask-pickrem, aitask-explore, aitask-fold, aitask-wrap) to use `./ait git` instead of plain `git` for task/plan file operations. Created `ait-git` non-user-invocable safety net skill. Added "Git Operations on Task/Plan Files" section to CLAUDE.md. Updated 3 website docs (board reference, development, parallel-development) with branch mode documentation.
- **Deviations from plan:** Found 2 additional skills beyond the original 4 listed in the task: `aitask-pickrem` had a `git push` after archival, and `aitask-wrap` had a mixed code+plan `git add` that needed splitting into separate commits. Both were fixed.
- **Issues encountered:** The `aitask-wrap` skill had a `git add <selected_files> aiplans/...` that combined code and plan files in one commit — in branch mode these live on different branches. Fixed by splitting into separate `git` (code) and `./ait git` (plan) operations.
- **Key decisions:** Kept `git push` in `aitask-wrap` step 4e as plain `git` since it pushes code to main, and added `./ait git push` for task data. Review guides (`aireviewguides/`) and CHANGELOG.md correctly stay with plain `git` as they live on the code branch.
- **Notes for sibling tasks:** t221_6 (testing) should verify that all skill workflows work correctly in both legacy and branch modes. User identified that `aitask-pickrem` (Claude Code Web) needs a lightweight initialization step to checkout the aitask-data worktree + create symlinks when `ait setup` hasn't been run — this will be a separate task.
