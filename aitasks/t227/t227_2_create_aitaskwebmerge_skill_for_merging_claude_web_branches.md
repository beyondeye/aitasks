---
priority: high
effort: high
depends: [t227_1]
issue_type: feature
status: Ready
labels: [aitakspickrem, remote]
created_at: 2026-02-24 16:52
updated_at: 2026-02-24 16:52
---

Create a local interactive skill at `.claude/skills/aitask-web-merge/SKILL.md` that detects branches with completed Claude Web task executions, separates code from task metadata, merges code to main, and archives task data to aitask-data.

## Context

After `aitask-pickweb` completes on Claude Web, the implementation exists on a remote branch with code changes and a `.task-data-updated/` directory containing the plan file and a completion marker JSON. This skill runs locally to:
1. Scan remote branches for `.task-data-updated/completed_*.json` markers
2. Let the user interactively select which branches to merge
3. Merge code to main (excluding `.task-data-updated/`)
4. Copy the plan to aitask-data and archive the task via `aitask_archive.sh`
5. Push both main and aitask-data branches
6. Clean up the merged remote branch

## Key Files to Create
- `.claude/skills/aitask-web-merge/SKILL.md` -- new skill definition
- `aiscripts/aitask_web_merge.sh` -- helper script for branch detection
- Update `.claude/settings.local.json` -- register the new skill

## Reference Files
- `aiscripts/aitask_archive.sh` -- archive workflow
- `aiscripts/lib/task_utils.sh` -- `task_git()` routing

## Workflow Summary

1. `git fetch --all --prune`, scan branches for `.task-data-updated/completed_*.json`
2. List completed branches, use `AskUserQuestion` with pagination for selection
3. Merge selected branch to main, remove `.task-data-updated/` from the merge
4. Read plan from branch via `git show`, copy to aitask-data, run `aitask_archive.sh`
5. Push main and aitask-data
6. Delete the remote branch

## Verification
- Test branch detection with a mock Claude Web branch
- Verify archive handles parent and child tasks
- Verify no `.task-data-updated/` artifacts on main after merge
