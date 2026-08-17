---
priority: high
effort: medium
depends: [t1544_3]
issue_type: feature
status: Ready
labels: [reporting, metrics, backlog]
gates: [risk_evaluated]
anchor: 1544
created_at: 2026-08-17 22:06
updated_at: 2026-08-17 22:09
---

## Context

Fourth child of t1544 (backlog level + net flow by category in `ait stats`).
Parent plan: `aiplans/p1544_stats_backlog_and_net_flow_by_category.md`.
Depends on **t1544_3**, which owns the data layer; this child is a pure
rendering of `StatsData.backlog_arrivals` / `backlog_departures` /
`backlog_excluded` plus the `backlog_levels()` helper. It adds **no** new
collection logic.

Read t1544_3's Final Implementation Notes first — they record the final helper
signature, the exact `backlog_excluded` reason strings, and the field names.

## Deliverable 1 — two new `###` sections in the text report

Two `render_*(data, out, …)` functions shaped like the existing
`render_pipeline_timing` in `.aitask-scripts/aitask_stats.py` (its own `###`
heading, an early-return empty state, then header / separator / rows), called
from `render_text_report`.

**Table shape — user-chosen during planning, rendered against the real corpus at
exactly 80 characters.** Categories are rows, weeks are columns:

```
### Backlog Level (Open Tasks) - Weekly (Last 8 Weeks)
| Category             |  Now |  W-7 |  W-6 |  W-5 |  W-4 |  W-3 |  W-2 |  W-1 |
|----------------------|------|------|------|------|------|------|------|------|
| risk mitigation      |   66 |    8 |   10 |   12 |   23 |   43 |   58 |   65 |
| manual verification  |   65 |   22 |   23 |   24 |   38 |   46 |   54 |   63 |
| upstream defect      |   47 |    4 |    5 |    4 |   11 |   27 |   42 |   47 |
| carry-over           |    8 |    5 |    5 |    5 |    5 |    7 |    7 |    8 |
| review finding       |    6 |    1 |    1 |    1 |    1 |    1 |    1 |    4 |
| verification failure |    5 |    0 |    0 |    0 |    0 |    2 |    4 |    5 |
| -- follow-ups        |  197 |   40 |   44 |   46 |   78 |  126 |  166 |  192 |
| Features             |  112 |   74 |   73 |   84 |   97 |  109 |  107 |  110 |
| Documentation        |   29 |   15 |   14 |   16 |   20 |   21 |   29 |   29 |
| -- genuine           |  221 |  126 |  126 |  145 |  168 |  202 |  214 |  219 |
| TOTAL OPEN           |  418 |  166 |  170 |  191 |  246 |  328 |  380 |  411 |
```

- Follow-up kinds first (lowercase display names from
  `task_category.category_display_name`), then issue types (Title Case) — the
  case difference is the visual separator between the two halves of the axis.
- Each block sorted by **current** level descending.
- `-- follow-ups`, `-- genuine` and `TOTAL OPEN` summary rows.
- `TOTAL OPEN` also carries the `(parents / children)` split t1544_3 provides.
- Suppress all-zero category rows so the table stays narrow in a young repo.

The net-flow section uses the same row axis with signed net values per week, and
an arrivals / departures / net total block.

## Deliverable 2 — three details that are easy to get wrong

1. **The current column is a partial week.**
   `week_end_for_offset(today, dow, 0)` is up to six days in the **future**. The
   *level* under it is correct-as-of-now, but its arrival/departure cells cover a
   partial week and will read as a volume collapse next to seven complete ones.
   Label it `min(week_end, today)` with a `(partial)` suffix — the same spirit as
   the existing tables' `This Week` header.

2. **`bug` will appear twice in one report with different numbers.** The existing
   `### By Task Type` section shows it **gross**; the new sections show it net of
   `upstream_defect` (148 archived tasks reclassified out of `bug`). Add a
   one-line footnote under the backlog table saying so.

3. **Two completion clocks.** The backlog sections use `completed_at` (falling
   back to `updated_at` for `Done`); the existing sections use
   `resolve_completion_date`, which prefers ledger stamps. They never disagree on
   *whether* a task completed, only on which week, for ~0.3% of tasks. Footnote
   it. Also footnote that **Postponed** tasks count as open and **Folded** tasks
   are excluded.

Add the `backlog_excluded` tally as an italic note in the same style as the
existing `_In flight (implementation done, awaiting gates): N_` line — never
drop excluded tasks silently.

## Deliverable 3 — the empty-archive early return

`aitask_stats.py` currently returns early when `ARCHIVE_DIR` is missing, and
again when `data.total_tasks == 0` (printing "No completed tasks found."). But
`total_tasks` counts **archived** tasks only — so a young repo with 400 open
tasks and zero archives, precisely the repo that most needs a backlog report,
prints that message and exits before the new sections.

Relax both guards to also consider `data.backlog_arrivals`, and let the
archive-missing branch fall through to the live-only path. Test it with a
fixture that has open tasks and an empty archive.

## Deliverable 4 — `--backlog-weeks N`

New argparse flag. Its default **must be**
`stats_data.BACKLOG_WEEKS_DEFAULT` (8), not a literal — the TUI pane reads the
same constant, and a literal here is how the two surfaces drift into showing
different windows for the same metric. Add a test asserting the default resolves
to the constant.

Validate the value (positive, and a sane upper bound). `render_text_report`
gains `backlog_weeks: int = BACKLOG_WEEKS_DEFAULT` — safe to append, since the
only production caller and the only test caller both use keyword arguments.

## Deliverable 5 — CSV, both surfaces

**User-chosen during planning: do both.**

1. **Append two columns to the existing per-task fact table**: `created_at` and
   `category`. Existing columns keep their positions and the **row set is
   unchanged**. The header list in `aitask_stats.py::write_csv` and the row
   producer in `lib/stats_data.py` (the `csv_rows.append([...])` inside the
   archived loop) are two halves of one contract — change them **in lockstep**.
   10 columns becomes 12.

   *Recorded caveat:* open tasks are not rows in this table, so the backlog level
   is **not** reproducible from it. `created_at` here buys lead-time analysis,
   not backlog.

2. **New `write_backlog_csv()`** emitting
   `week_ending, category, open, arrived, departed, net`, reachable via a new
   `--csv-backlog FILE` flag. This is where the series actually lives.

## Key files to modify

- `.aitask-scripts/aitask_stats.py` — two render functions, the
  `render_text_report` call sites, `get_type_display_name` already delegates
  (t1544_2), `write_csv` header, `write_backlog_csv`, `parse_args`, the two
  early-return guards in `main`
- `.aitask-scripts/lib/stats_data.py` — the `csv_rows.append([...])` row producer
  only (all other collection work belongs to t1544_3)
- `tests/test_aitask_stats_py.py` — section + CSV + flag assertions

## Reference files for patterns

- `.aitask-scripts/aitask_stats.py` — `render_pipeline_timing` (the
  section-as-a-function template, with its empty state), and the
  `### By Code Agent - Weekly Trend` block (the closest existing
  category-axis x weekly-buckets pipe table; copy its f-string padding idiom)
- `.aitask-scripts/lib/task_category.py` — `category_display_name`,
  `is_followup_category` (t1544_2)
- `.aitask-scripts/lib/stats_data.py` — `backlog_levels`,
  `backlog_week_offsets`, `week_end_for_offset`, `BACKLOG_WEEKS_DEFAULT`
  (t1544_3)
- `tests/test_aitask_stats_py.py` — `TestCollection` builds real markdown and a
  real zstd bundle in a tempdir and **patches module globals** (`TASK_DIR` /
  `ARCHIVE_DIR` / `TASK_TYPES_FILE`) on **both** `stats` and `stats_data`;
  `test_write_csv_includes_implementation_columns` is the exact CSV-header
  assertion to extend

## Verification steps

```bash
bash tests/run_all_python_tests.sh --test-dir tests
./ait stats                                    # both new sections render
./ait stats --backlog-weeks 26                 # long horizon
./ait stats --csv /tmp/tasks.csv --csv-backlog /tmp/backlog.csv
head -1 /tmp/tasks.csv                         # 12 columns, first 10 unmoved
head -3 /tmp/backlog.csv
```

- Confirm every **existing** section is byte-identical to a pre-change capture
  (ignore the `Generated:` line).
- Confirm the backlog table is <= 80 characters wide at the default horizon.
- Confirm a fixture repo with open tasks and an **empty archive** still renders
  the backlog section instead of "No completed tasks found."

**Do not** pipe `ait stats` through `tail` when checking exit status — the pipe
discards it; use `set -o pipefail` or `${PIPESTATUS[0]}`.
