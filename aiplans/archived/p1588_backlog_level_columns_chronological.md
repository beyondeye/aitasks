---
Task: t1588_backlog_level_columns_chronological.md
Created by: aitask-wrap (retroactive documentation)
---

## Summary

The `ait stats` **Backlog Level** table now runs chronologically with the
current week last:

```
before: | Category | Now | W-7 | W-6 | W-5 | W-4 | W-3 | W-2 | W-1 |
after:  | Category | W-7 | W-6 | W-5 | W-4 | W-3 | W-2 | W-1 | Now |
```

The **Backlog Net Flow** table is unchanged in order — it already ended in
`Now*` — so the two tables now share one column layout and can be read stacked.

## Files Modified

### `.aitask-scripts/aitask_stats.py`

- Replaced `_backlog_week_labels(offsets)` with
  `_backlog_columns(offsets, now_label) -> (columns, headers)`, which returns
  both the offset order and the labels. This is now the **single** definition of
  the layout; previously each renderer built its own list, which is exactly how
  the two tables came to disagree.
- `render_backlog_level` and `render_backlog_netflow` both call it, passing only
  their own current-week label.
- Updated `render_backlog_level`'s docstring, which had documented the
  `Now`-first rationale.

### `tests/test_aitask_stats_py.py`

- Added `_table_headers(section)` and used it to replace three inline copies of
  the header-parsing expression.
- `test_totals_reconcile_across_all_three_axes` resolved `Now` by the hardcoded
  index `[0]`. It now resolves the column **by header name** — an index would
  silently read a different week after any reorder, which is precisely how this
  test broke.
- Added `test_level_table_runs_chronologically_with_now_last` and
  `test_both_tables_share_one_column_layout`.

## Probable User Intent

Direct user request during review of the t1544_4 output: "instead of showing the
columns now, w-7 … w-1, put now after w-1". The underlying motive is legibility
— the two backlog sections are adjacent and meant to be compared, and a table
whose first column is the newest datum while the rest run oldest-to-newest reads
backwards.

The extraction of `_backlog_columns` was not requested; it was added because the
duplication is what allowed the two tables to diverge, and re-flipping one list
would have left that hazard in place.

## Why `Now` carries no partial marker but `Now*` does

Both tables end on offset 0, but it means different things:

- **Level** is a *stock*. `backlog_levels` cumulates every arrival up to
  `today`, so the value is correct as-of-now and is not distorted by the week
  being incomplete. No marker.
- **Net flow** is a *flow* over the week. A partial week genuinely under-counts,
  so the column is labelled `Now*` and footnoted with the covered range.

Keeping both semantics visible in the same position is the reason `now_label` is
a parameter rather than a constant.

## Verification

- `tests/test_aitask_stats_py.py` 44/44 (was 42; +2 layout tests).
- `tests/test_stats_multistage.py` 80/80.
- `pyflakes` clean on both changed files.
- Both tables still render at **exactly 80 characters** at the default horizon.
- **Negative control:** restoring the old order in `_backlog_columns` reddens
  exactly `test_level_table_runs_chronologically_with_now_last`,
  `test_both_tables_share_one_column_layout` and
  `test_flow_table_puts_the_partial_week_last_and_marks_it`, and nothing else.

### Known failing tests elsewhere (not caused by a defect here)

`tests/test_stats_backlog_panes.py::TestCliParity` (two tests) fails while
t1544_5 is in flight. Its pane duplicates the CLI's old `Now`-first layout at
`.aitask-scripts/stats/panes/backlog.py:166`, and its parity test compares
surface against surface — so it correctly detected the CLI change. The t1544_5
session was messaged with the failing test names, the exact site, the stale
comment at `backlog.py:157`, and a recommendation to consume `_backlog_columns`
instead of re-hardcoding the order. Those files were deliberately **not** edited
here: they are untracked work being written by another live session.

## Scope note

Two other sessions had uncommitted work in this tree when the wrap ran
(t1544_5's stats panes, and a merge-broker change under
`.claude/skills/task-workflow/`). The commit was made with an explicit path list
covering only the two files above.
