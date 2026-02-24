---
Task: t227_aitask_own_failure_in_cluade_web.md
Worktree: (none - current branch)
Branch: main
Base branch: main
---

# Plan: t227 — Fix aitask_own.sh locking failures in Claude Code Web

## Context

When running `aitask-pickrem` on Claude Code Web, the environment is sandboxed to a single branch with no push access to `aitask-locks`, `aitask-data`, or `main`. This breaks ALL task lifecycle operations: locking, status updates, plan storage, and archival.

## Approach

Split into 6 child tasks:
1. **t227_1**: Create `aitask-pickweb` skill (stripped-down, no cross-branch ops)
2. **t227_2**: Create `aitask-web-merge` skill (local merge-back procedure)
3. **t227_3**: Add lock/unlock controls to board TUI
4. **t227_4**: Make `aitask-pick` lock-aware
5. **t227_5**: Introduce per-user config (`userconfig.yaml`)
6. **t227_6**: Documentation

## Dependency Order

t227_5 (userconfig) should be first — other tasks depend on it.
t227_1 (pickweb) before t227_2 (web-merge) — defines the `.task-data-updated/` marker format.
t227_3, t227_4 are independent.
t227_6 (docs) is last — needs all implementations done.

## Key Decisions

- Keep `aitask-pickrem` for environments with broader access
- New `aitask-pickweb` for Claude Web (zero cross-branch ops)
- `.task-data-updated/` directory stores plans and completion markers on working branch
- `aitask-web-merge` handles post-completion integration locally
- Locking becomes a separate pre-pick operation (via board)
- `aitask-pick` warns when task is already locked by someone else
- `userconfig.yaml` replaces broken "first email from emails.txt" pattern

## Verification (t220)

Task t220 was verified as complete: structured exit codes, force-unlock, diagnostics, archival-based cleanup. No TTL-based expiry (not in scope). No further work needed.
