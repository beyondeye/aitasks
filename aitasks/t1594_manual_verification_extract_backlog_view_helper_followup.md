---
priority: medium
effort: medium
depends: [1586]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1586]
anchor: 1544
followup_kind: manual_verification
created_at: 2026-08-24 23:13
updated_at: 2026-08-24 23:13
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1586

## Verification Checklist

- [ ] Open `ait stats-tui` and select the Backlog level pane: the DataTable renders with columns W-7 .. W-1, Now (current week LAST), the follow-up block above the genuine block, and the `-- follow-ups` / `-- genuine` / `TOTAL OPEN` / `of which parents` / `of which children` rows all present and reconciling.
- [ ] In the same pane, the `Other` bucket appears only when a block exceeds the 6-row cap, and `shown + Other == subtotal` holds for every column.
- [ ] Switch to the Net flow pane: the multiple_bar chart renders its category series, the ARRIVALS / DEPARTURES / NET totals strip sits above it, and chart + strip fit `#content` without a scrollbar.
- [ ] Data-quality lines (`Excluded from the backlog series: ...` / `Clamped negative level cells: ...`) still render below the level table when the repo has excluded tasks.
- [ ] Switch away from and back to the Backlog panes several times: the clamped negative-level count does NOT grow. This exercises the per-call scratch Counter that moved into `lib/backlog_view.py::build_backlog_axis` (t1586) -- a shared sink would accumulate for the life of the session.
- [ ] Run `ait stats` in a real terminal: the Backlog Level and Backlog Net Flow tables are visually aligned column for column when read stacked.
