---
priority: medium
effort: medium
depends: [1235]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1235]
created_at: 2026-07-28 18:04
updated_at: 2026-07-28 18:04
boardidx: 490
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1235

## Verification Checklist

- [ ] Launch `ait stats-tui` in a real tmux pane and confirm the app starts (the panes are proven to import and register, but nobody has watched them draw)
- [ ] Cycle through every pane in `ait stats-tui` — overview, labels, agents, velocity, sessions, pipeline — and confirm each renders real data rather than its empty state
- [ ] In the agents pane, confirm the verified/usage ranking tables populate and that cycling the operation (cycle_op) redraws correctly
- [ ] Run `ait stats` and `ait stats --csv <file>`; eyeball the text report and the CSV against the TUI overview's totals — both paths now import stats_data from lib/
- [ ] Run the board's `w` work-report flow end-to-end (board -> `w` -> reviewed selection) and confirm the report generates; work_report_gather is the other consumer of collect_stats and lost its sys.path insert
- [ ] In `ait stats-tui`, switch to a different project/session via the group selector and confirm stats reload for that project root (collect_stats project_root path)
- [ ] Confirm the TUI switcher (`j`) still opens from stats-tui — stats/__init__.py now inserts lib/ on sys.path and stats_app.py imports lib.tui_switcher
