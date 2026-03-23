---
priority: high
effort: medium
depends: []
issue_type: bug
status: Done
labels: [agentcrew, brainstorming]
folded_tasks: [438]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-23 19:02
updated_at: 2026-03-23 19:25
completed_at: 2026-03-23 19:25
---

## Problem

AgentCrew branch initialization (`aitask_crew_init.sh`) creates regular branches from HEAD, causing the full repository source code to be checked out in crew worktrees. Crew branches should be orphan branches containing only crew/brainstorm data files.

## Root Cause

In `.aitask-scripts/aitask_crew_init.sh` lines 106-107:
```bash
git branch "$BRANCH_NAME" HEAD
git worktree add "$WT_PATH" "$BRANCH_NAME" --quiet
```

This creates a regular branch from HEAD (full repo), then creates a worktree with all source files.

## Fix

### 1. `aitask_crew_init.sh` — Use orphan branch pattern

Replace the branch+worktree creation with the git plumbing pattern already used in `aitask_lock.sh:77-80` and `aitask_setup.sh:974-977`:

```bash
# Create orphan branch with empty tree
empty_tree_hash=$(printf '' | git mktree)
commit_hash=$(echo "crew: Initialize agentcrew '$CREW_ID'" | git commit-tree "$empty_tree_hash")
git update-ref "refs/heads/$BRANCH_NAME" "$commit_hash"

# Create worktree from the orphan branch
git worktree add "$WT_PATH" "$BRANCH_NAME" --quiet
```

### 2. `agentcrew_runner.py` — Use repo root path for `ait`

Three locations reference `./ait` from the worktree dir:
- Line 423: `cmd = ["./ait", "codeagent", ...]` — agent launch command
- Line 431: `cwd=worktree` — agent process working directory
- Lines 583-587: `ait_path = os.path.join(worktree, "ait")` — shutdown handler

Fix: resolve repo root (e.g., via `git -C worktree rev-parse --show-superproject-working-tree` or by navigating from worktree path since worktrees are at `.aitask-crews/crew-*/` relative to repo root). Use absolute path to `ait` and set `cwd` to repo root.

### 3. Migration — Existing crew branches

Existing crew branches (e.g. `crew-brainstorm-426`) are regular branches with full repo content. The fix should handle this gracefully — existing worktrees continue to work, only new crews get orphan branches.

## Files to Change

- `.aitask-scripts/aitask_crew_init.sh` — orphan branch creation
- `.aitask-scripts/agentcrew/agentcrew_runner.py` — repo root resolution, `ait` path, `cwd` for agents

## Merged from t438: troubleshoot agentcrew run

we have tried to run an ait brainstorm for task 427, (see ./aitask-crews/crew-brainstorm-427). from the brainstorm tui we have triggered an initial explorer agent (see explorer_001 yaml files. the explorer does not seem to be running, also it seems that the whole aitask repository has be cloned inside the brainstorm directory (see .git file) this was unexpected and not required, the crew-brainstorm-427 branch/directory is for files striclty related to the brainstorm and agentcrew management: can you investigate what happened? look also at how the explore operation is triggered in ait brainstorm code

## Folded Tasks

The following existing tasks have been folded into this task. Their requirements are incorporated in the description above. These references exist only for post-implementation cleanup.

- **t438** (`t438_troubleshoot_agentcrew_run.md`)
