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

### Step 1: Create helper script `aiscripts/aitask_web_merge.sh` [DONE]
- Scans remote branches for `.aitask-data-updated/completed_*.json`
- Outputs structured `COMPLETED:<branch>:<marker_filename>` lines (or `NONE`)
- Uses `git ls-tree` and `git branch -r` to detect markers without checkout
- Does NOT parse JSON — reports branch+filename; SKILL.md reads full JSON via `git show`
- ~110 lines, follows project shell conventions

### Step 2: Create skill SKILL.md [DONE]
- `.claude/skills/aitask-web-merge/SKILL.md` (~180 lines)
- Interactive skill (uses AskUserQuestion)
- Workflow: scan → select → pull (--ff-only) → merge (--no-ff --no-commit) → remove .aitask-data-updated → commit → copy plan → archive → push → cleanup
- Includes Issue Update Procedure (matches task-workflow pattern)
- Multi-branch processing loop with "Process all" option

### Step 3: Detailed merge procedure (in SKILL.md)
1. `git pull --ff-only` to ensure main is up-to-date
2. `git merge origin/<branch> --no-ff --no-commit` (stage without committing)
3. `git rm -rf .aitask-data-updated/` (exclude metadata from merge)
4. `git commit -m "<issue_type>: <description> (t<task_id>)"` (clean merge commit)
5. Read plan from branch via `git show origin/<branch>:.aitask-data-updated/plan_t<task_id>.md`
6. Write plan to aitask-data at correct path (derive filename by replacing `t` with `p` in task basename)
7. `./ait git add` + `./ait git commit` the plan
8. Run `aitask_archive.sh <task_id>`, parse structured output
9. Push main + aitask-data
10. Delete remote branch: `git push origin --delete <branch>`

### Step 4: Register skill [DONE]
- Added `Bash(./aiscripts/aitask_web_merge.sh:*)` to `.claude/settings.local.json`

### Step 5: Create automated tests [DONE]
- `tests/test_web_merge.sh` (~170 lines, 7 test cases)
- Uses paired repos (bare remote + local clone) with fake web branches
- Test cases: no branches, single branch, multiple branches, plain branch ignored, known branches skipped, --fetch flag, child task marker
- All 10 assertions pass

## Key Files
- **Created:** `aiscripts/aitask_web_merge.sh`, `.claude/skills/aitask-web-merge/SKILL.md`, `tests/test_web_merge.sh`
- **Modified:** `.claude/settings.local.json`
- **Reference:** `aiscripts/aitask_archive.sh`, `aiscripts/lib/task_utils.sh`, `.claude/skills/aitask-pickweb/SKILL.md`

## Verification
- `shellcheck aiscripts/aitask_web_merge.sh` — only SC1091 info (expected)
- `bash tests/test_web_merge.sh` — 10/10 assertions pass
- SKILL.md reviewed for: merge/archive/push flow, parent/child handling, Issue Update Procedure, merge conflict handling

## Final Implementation Notes
- **Actual work done:** Created all 3 files as planned: helper script (~110 lines), SKILL.md (~180 lines), test file (~170 lines). Updated settings.local.json with 1 permission line.
- **Deviations from original plan:** Replaced `--amend` approach with cleaner `--no-ff --no-commit` + `git rm` + `git commit` flow (no amending). Added `git pull --ff-only` before merge (per user feedback). Helper script does not parse JSON (simpler design — just detects branch+filename, SKILL.md reads full JSON).
- **Issues encountered:** Tests initially failed because `git checkout main` didn't work in temp repos where default branch wasn't explicitly set to `main`. Fixed by using `git init --bare -b main` in test setup.
- **Key decisions:** Helper script is detection-only (~70 lines of logic); all merge/archive orchestration is in SKILL.md. Plan filename derivation: replace leading `t` with `p` in task filename basename. Multi-branch loop: after processing one branch, offers to continue with remaining.
- **Notes for sibling tasks:** The SKILL.md is now auto-discovered by Claude Code (visible in skill list). The `aitask_web_merge.sh` script can be used independently for branch detection. The completion marker contract with pickweb is: `.aitask-data-updated/completed_t<task_id>.json` (JSON with task_id, task_file, plan_file, is_child, parent_id, issue_type, completed_at, branch).

## Post-Implementation (Step 9)
Archive this child task.
