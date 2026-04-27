---
priority: high
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-27 10:37
updated_at: 2026-04-27 10:39
---

`ait brainstorm delete <N>` does not actually delete the `crew-brainstorm-<N>` git branch when a stale worktree registration exists from a prior aborted init.

## Root cause

In `.aitask-scripts/aitask_brainstorm_delete.sh:101-117` the cleanup fallback runs:

```bash
git branch -D "crew-${CREW_ID}" 2>/dev/null || true
git push origin --delete "crew-${CREW_ID}" 2>/dev/null || true
git worktree prune 2>/dev/null || true
```

Because `delete_session` (Python) `shutil.rmtree`s the worktree directory but does **not** clear the git worktree registration in `.git/worktrees/`, the branch is still considered "checked out at <stale path>" by git. `git branch -D` therefore refuses, but the silent `2>/dev/null || true` swallows the failure — leaving the branch behind.

## Fix

Reorder so `git worktree prune` runs FIRST, then `git branch -D`. Also consider dropping the `2>/dev/null` suppression for the branch-delete so failures surface, and printing a one-line note when cleanup happens (e.g. `Cleaned: stale crew-brainstorm-<N> branch removed`).

## Repro

1. `ait brainstorm <N>` → "Initialize Blank" → wait for crew creation
2. Cancel/abort somewhere mid-session, then `ait brainstorm delete <N>`
3. `git branch --list 'crew-brainstorm-<N>'` — branch still present.

## Why now

This bug surfaced as the underlying cause of t660 (brainstorm TUI silently quitting on plan import for t635). t660 added an InitFailureModal with a 'Delete branch & retry' affordance that recovers from the stale branch — but the right fix is to never leave the branch behind in the first place.

## Verification

- Test: aitask delete after partial init leaves no crew-brainstorm-N branch (and git worktree list is clean).
- Re-run the t660 repro: ait brainstorm N -> init -> cancel -> ait brainstorm delete N -> ait brainstorm N again should succeed without falling into the InitFailureModal.
