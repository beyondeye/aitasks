---
priority: medium
effort: low
depends: []
issue_type: enhancement
status: Done
labels: [reporting, metrics, backlog]
implemented_with: claudecode/opus5
created_at: 2026-08-24 18:15
updated_at: 2026-08-24 18:16
completed_at: 2026-08-24 18:16
---

## Summary

Move the `Now` column of the `ait stats` **Backlog Level** table from first to
last, so the table runs chronologically (`W-7 … W-1, Now`) and aligns
column-for-column with the **Backlog Net Flow** table, which already ended in
`Now*`.

## Context

t1544_4 shipped the level table with `Now` first, reasoning that offset 0 played
the headline role the existing weekly tables give their `Total` column. In
practice the two backlog sections sit directly on top of each other and are read
stacked, so a reversed leading column made them awkward to compare.

The two tables each built their own column list, which is how they came to
disagree in the first place. This change replaces both with a single
`_backlog_columns(offsets, now_label)` definition, so a future reorder cannot
desynchronize them.

Only the current-week **label** differs between the tables, and that difference
is meaningful: `Now` for the level (a *stock* — correct as-of-now, so no partial
marker) versus `Now*` for the flow (a *flow* over a partial week genuinely is
incomplete).

## Known consequence

This breaks the CLI-parity test in the in-flight t1544_5 (stats TUI backlog
panes), whose pane duplicated the CLI's `Now`-first layout at
`.aitask-scripts/stats/panes/backlog.py:166`. That session was notified with the
failing test names and a pointer to consume `_backlog_columns` rather than
re-hardcode the order. t1586 (`extract_backlog_view_helper`, already gated on
t1544_5) is the task that removes the duplication properly.
