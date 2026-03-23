---
Task: t445_crew_init_orphan_branches.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: t445 — Crew Init Orphan Branches

## Context

AgentCrew branch initialization creates regular branches from HEAD, causing the full repository source code to be checked out in crew worktrees. Crew branches should be orphan branches containing only crew/brainstorm data files. Additionally, `agentcrew_runner.py` launches agents with `cwd=worktree` and `./ait` relative to that directory — both break when the worktree no longer contains source code.

## Changes

### 1. `aitask_crew_init.sh` — Orphan branch creation (lines 106-107)

Replaced `git branch HEAD` with the orphan branch pattern (same as `aitask_setup.sh:974-977`):
```bash
empty_tree_hash=$(printf '' | git mktree)
commit_hash=$(echo "crew: Initialize agentcrew '$CREW_ID'" | git commit-tree "$empty_tree_hash")
git update-ref "refs/heads/$BRANCH_NAME" "$commit_hash"
git worktree add "$WT_PATH" "$BRANCH_NAME" --quiet
```

### 2. `agentcrew_runner.py` — Resolve repo root, fix `ait` path and `cwd`

- Added `resolve_repo_root()` helper using `git rev-parse --show-toplevel`
- Cached `_repo_root` module global, set in `main()`
- Fixed `launch_agent()`: uses `os.path.join(_repo_root, "ait")` and `cwd=_repo_root`
- Fixed `graceful_shutdown()`: uses `os.path.join(_repo_root, "ait")`, removed worktree fallback

### 3. Migration — No changes needed

Existing crew worktrees work because the runner now resolves `ait` from repo root regardless.

## Final Implementation Notes

- **Actual work done:** Exactly as planned — orphan branch creation in init script, repo root resolution in runner
- **Deviations from plan:** None
- **Issues encountered:** None
- **Key decisions:** Used module-level `_repo_root` global with fallback to `"./ait"` / `"."` for safety, though in practice `main()` always sets it before any agent launch
