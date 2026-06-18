---
priority: medium
effort: medium
depends: [1027]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1027]
created_at: 2026-06-18 15:35
updated_at: 2026-06-18 15:35
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1027

## Verification Checklist

- [ ] [t1027] In a master-default repo (e.g. aitasks_mobile), run `python3 .aitask-scripts/lib/desync_state.py snapshot --format text` and confirm the main row reads `up to date`/`behind/ahead` — NOT `missing remote ref`.
- [ ] [t1027] In a master-default repo, open the syncer TUI; confirm the `main` row shows ok/clean status (not missing_remote).
- [ ] [t1027] In a master-default repo with the worktree checked out on master, trigger syncer Pull; confirm it does NOT warn "Switch to main to pull" and actually performs the pull.
- [ ] [t1027] In a master-default repo, trigger syncer Push; confirm the command shown/run is `git push origin master:master` (not `main:main`) and it succeeds.
- [ ] [t1027] Regression: in a main-default repo, confirm the syncer row and Pull/Push still target `main` exactly as before.
