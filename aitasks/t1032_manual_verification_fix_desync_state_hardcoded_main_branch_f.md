---
priority: medium
effort: medium
depends: [1027]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [1027]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-18 15:35
updated_at: 2026-06-21 09:56
boardidx: 60
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1027

## Verification Checklist

- [x] [t1027] In a master-default repo (e.g. aitasks_mobile), run `python3 .aitask-scripts/lib/desync_state.py snapshot --format text` and confirm the main row reads `up to date`/`behind/ahead` — PASS 2026-06-21 09:56 auto: scratch master-default repo at /tmp/aitask_t1032_jKttVn/master/project reported 'main: up to date' and no missing remote ref
- [x] [t1027] In a master-default repo, open the syncer TUI; confirm the `main` row shows ok/clean status (not missing_remote). — PASS 2026-06-21 09:56 auto: tmux-captured './ait syncer --no-fetch --interval 999' in scratch master repo showed main row status ok, not missing_remote
- [x] [t1027] In a master-default repo with the worktree checked out on master, trigger syncer Pull; confirm it does NOT warn "Switch to main to pull" and actually performs the pull. — PASS 2026-06-21 09:56 auto: syncer Pull in scratch master repo logged git pull --ff-only, did not warn 'Switch to main to pull', and local master advanced to 'remote master change'
- [x] [t1027] In a master-default repo, trigger syncer Push; confirm the command shown/run is `git push origin master:master` (not `main:main`) and it succeeds. — PASS 2026-06-21 09:56 auto: syncer Push in scratch master repo logged 'git push origin master:master', not main:main, and origin/master advanced to 'local master change'
- [x] [t1027] Regression: in a main-default repo, confirm the syncer row and Pull/Push still target `main` exactly as before. — PASS 2026-06-21 09:56 auto: scratch main-default repo still showed main row ok; syncer Pull used git pull --ff-only and Push logged 'git push origin main:main', not master:master
