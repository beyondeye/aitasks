---
Task: t227_2_create_aitaskwebmerge_skill_for_merging_claude_web_branches.md
Parent Task: aitasks/t227_aitask_own_failure_in_cluade_web.md
Sibling Tasks: aitasks/t227/t227_1_*.md, aitasks/t227/t227_3_*.md, aitasks/t227/t227_4_*.md, aitasks/t227/t227_5_*.md, aitasks/t227/t227_6_*.md
Worktree: (none - current branch)
Branch: main
Base branch: main
---

# Plan: t227_2 — Create aitask-web-merge skill

## Context

After `aitask-pickweb` completes on Claude Web, the implementation exists on a remote branch with `.aitask-data-updated/` containing plan and completion marker. This skill runs locally to merge code to main and archive task data to aitask-data.

## Implementation Steps

### Step 1: Create helper script `aiscripts/aitask_web_merge.sh`
- Scans remote branches for `.aitask-data-updated/completed_*.json`
- Outputs structured list of candidate branches with metadata
- Uses `git ls-tree` and `git show` to read markers without checkout

### Step 2: Create skill SKILL.md
- `.claude/skills/aitask-web-merge/SKILL.md`
- Interactive skill (uses AskUserQuestion)
- Workflow: scan → select → merge → archive → push → cleanup

### Step 3: Detailed merge procedure
1. `git fetch --all --prune`
2. Run helper script to detect branches
3. AskUserQuestion with pagination for branch selection
4. For selected branch:
   - `git merge <branch> --no-ff`
   - `git rm -rf .aitask-data-updated/ && git commit --amend --no-edit`
   - Read plan from branch via `git show`
   - Copy plan to aitask-data
   - Run `aitask_archive.sh`
   - Push main + aitask-data
   - Delete remote branch

### Step 4: Register skill
- Update `.claude/settings.local.json`

## Key Files
- **Create:** `.claude/skills/aitask-web-merge/SKILL.md`, `aiscripts/aitask_web_merge.sh`
- **Modify:** `.claude/settings.local.json`
- **Reference:** `aiscripts/aitask_archive.sh`, `aiscripts/lib/task_utils.sh`

## Verification
- Test branch detection with mock branch containing `.aitask-data-updated/completed_*.json`
- Verify archive handles parent and child tasks
- Verify no `.aitask-data-updated/` artifacts on main after merge

## Post-Implementation (Step 9)
Archive this child task.
