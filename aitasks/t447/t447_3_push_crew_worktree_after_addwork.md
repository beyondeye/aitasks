---
priority: medium
effort: low
depends: []
issue_type: feature
status: Implementing
labels: [agentcrew]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-23 23:09
updated_at: 2026-03-24 09:46
---

## Summary

Push the crew worktree branch after `ait crew addwork` commits agent files, enabling cross-machine runner support.

## Context

The agentcrew system was designed to support running the runner on a different machine from where work is submitted. The runner does `git_pull` each iteration and `git_commit_push_if_changes` after each iteration. However, `ait crew addwork` (`.aitask-scripts/aitask_crew_addwork.sh`) only commits locally — it never pushes. This means agents registered via the brainstorm TUI (or any caller) are invisible to a remote runner until something else pushes the branch.

The brainstorm TUI calls `brainstorm_crew.py:_run_addwork()` → `ait crew addwork` → commits in crew worktree (lines 274-282 of `aitask_crew_addwork.sh`) but never pushes.

## Key Files to Modify

Choose ONE approach:

**Option A (recommended): Modify `ait crew addwork` script**
- `.aitask-scripts/aitask_crew_addwork.sh` — Add `git push` after the commit (line 282)
- Benefits all callers (brainstorm TUI, crew dashboard, CLI)
- Simple change: add `git push --quiet 2>/dev/null || true` after the commit block

**Option B: Modify brainstorm layer only**
- `.aitask-scripts/brainstorm/brainstorm_crew.py` — Add push in `_run_addwork()` after the subprocess call
- More targeted, only affects brainstorm TUI

## Reference Files for Patterns

- `.aitask-scripts/agentcrew/agentcrew_runner.py` lines 130-139 — `git_commit_push_if_changes()` pattern used by the runner
- `.aitask-scripts/aitask_crew_addwork.sh` lines 274-282 — current commit-only block

## Implementation Plan

### Option A (recommended):

After the git commit in `aitask_crew_addwork.sh` (line 282), add:
```bash
    git push --quiet 2>/dev/null || warn "git push failed (offline?)"
```

This is best-effort — if push fails (no remote, offline), it warns but doesn't block.

### Option B (alternative):

In `brainstorm_crew.py:_run_addwork()`, after the subprocess call, add a push:
```python
subprocess.run(
    ["git", "-C", str(session_path), "push", "--quiet"],
    capture_output=True, timeout=30,
)
```

## Verification Steps

1. Register an agent via brainstorm TUI (or `ait crew addwork`)
2. Check crew worktree: `git -C .aitask-crews/crew-<id> log --oneline -1` shows the commit
3. Check push status: `git -C .aitask-crews/crew-<id> status` shows "Your branch is up to date"
