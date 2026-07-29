---
priority: medium
effort: medium
depends: [1302]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1302]
created_at: 2026-07-29 09:54
updated_at: 2026-07-29 09:54
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1302

## Verification Checklist

- [ ] Open `ait board` in a real tmux pane and confirm it loads, renders every column, and shows git-modified markers on task cards — the changed `refresh_git_status` runs on every refresh, so a mistake here breaks the board on startup.
- [ ] Move a task card between columns and to a different position within a column, then re-open the board and confirm the card stayed where it was put (exercises the `serialize_frontmatter` save path end-to-end through the real TUI, not just the unit tests).
- [ ] After the move above, run `git diff` on the moved task file and confirm the ONLY changed lines are `boardcol` / `boardidx` / `updated_at` — no frontmatter key was reordered or reformatted by the re-serialization.
- [ ] Pick a task file whose frontmatter ends `boardidx` then `boardcol` (36 exist; e.g. `aitasks/t1129_manual_verification_slack_live_smoke.md`), move it on the board, and confirm the two keys kept that order rather than being flipped to `boardcol, boardidx`.
- [ ] Verify the board degrades instead of crashing when git is unavailable: with the board open, make the git binary unreachable (e.g. run the board with a PATH lacking git, or chmod-000 a git dir it reads) and trigger a refresh — expect cards with no git-status markers, not a traceback.
- [ ] Verify `ait board` lock display still works: lock/unlock a task via the board and confirm the lock indicator updates (guards `refresh_lock_map`, which shares the parametrized degrade test with `refresh_git_status`).
