---
Task: t1544_4_cli_backlog_sections_and_csv.md
Parent Task: aitasks/t1544_stats_backlog_and_net_flow_by_category.md
Sibling Tasks: aitasks/t1544/t1544_1_*.md, aitasks/t1544/t1544_2_*.md, aitasks/t1544/t1544_3_*.md, aitasks/t1544/t1544_5_*.md, aitasks/t1544/t1544_6_*.md, aitasks/t1544/t1544_7_*.md, aitasks/t1544/t1544_8_*.md
Archived Sibling Plans: aiplans/archived/p1544/p1544_*_*.md
Base branch: main
Output branch: main
---

# p1544_4 — CLI backlog sections and CSV

## Goal

Render t1544_3's two series in `ait stats`: a weekly backlog-level section and a
weekly net-flow section, both split by the category axis, plus the CSV surfaces.
No new collection logic — this child reads `backlog_arrivals`,
`backlog_departures`, `backlog_excluded` and `backlog_levels()`.

Read t1544_3's Final Implementation Notes first for the exact helper signature,
field names and `backlog_excluded` reason strings.

## Implementation steps

1. **Two section functions** in `.aitask-scripts/aitask_stats.py`, shaped like
   the existing `render_pipeline_timing` — own `###` heading, early-return empty
   state, then header / separator / rows — called from `render_text_report`.
   Copy the f-string padding idiom from the `### By Code Agent - Weekly Trend`
   block, which is the closest existing category-axis × weekly-buckets table.

2. **Row axis, shared by both sections.** Follow-up categories first
   (`is_followup_category`, lowercase display names), then issue types (Title
   Case) — the case difference is the visual separator, so do not normalize it.
   Each block sorted by **current** level descending. Suppress all-zero rows so a
   young repo's table stays narrow. Then `-- follow-ups`, `-- genuine`, and
   `TOTAL OPEN` with t1544_3's `(parents / children)` split.

   Target shape, verified against the real corpus at **exactly 80 characters**:

   ```
   ### Backlog Level (Open Tasks) - Weekly (Last 8 Weeks)
   | Category             |  Now |  W-7 |  W-6 |  W-5 |  W-4 |  W-3 |  W-2 |  W-1 |
   |----------------------|------|------|------|------|------|------|------|------|
   | risk mitigation      |   66 |    8 |   10 |   12 |   23 |   43 |   58 |   65 |
   | -- follow-ups        |  197 |   40 |   44 |   46 |   78 |  126 |  166 |  192 |
   | Features             |  112 |   74 |   73 |   84 |   97 |  109 |  107 |  110 |
   | -- genuine           |  221 |  126 |  126 |  145 |  168 |  202 |  214 |  219 |
   | TOTAL OPEN           |  418 |  166 |  170 |  191 |  246 |  328 |  380 |  411 |
   ```

   The net-flow section uses the same rows with signed per-week nets and an
   arrivals / departures / net total block.

3. **The `Now` column is a partial week.** `week_end_for_offset(today, dow, 0)`
   is up to six days in the future. The *level* under it is correct-as-of-now,
   but its arrival/departure cells cover a partial week and would read as a
   volume collapse next to seven complete ones. Label it
   `min(week_end, today)` with a `(partial)` suffix.

4. **Three footnotes**, in the italic style of the existing
   `_In flight (implementation done, awaiting gates): N_` line:
   - the `backlog_excluded` tally, broken down by reason — never drop excluded
     tasks silently;
   - `bug` appears **twice** in one report with different numbers — gross in
     `### By Task Type`, net of `upstream_defect` here;
   - two completion clocks (backlog uses `completed_at`, the other sections use
     the ledger-preferring resolver — same set of completed tasks, different week
     for ~0.3%), plus: Postponed counts as open, Folded is excluded.

5. **`--backlog-weeks N`.** Its argparse default **must be**
   `stats_data.BACKLOG_WEEKS_DEFAULT`, not a literal `8` — the TUI pane reads the
   same constant, and a literal here is precisely how the two surfaces drift into
   showing different windows for one metric. Validate positive with a sane upper
   bound. `render_text_report` gains
   `backlog_weeks: int = BACKLOG_WEEKS_DEFAULT`; appending is safe because the
   only production caller and the only test caller both use keyword arguments.

6. **The empty-archive early return.** `main()` returns early when `ARCHIVE_DIR`
   is missing, and again when `data.total_tasks == 0` (printing "No completed
   tasks found."). But `total_tasks` counts **archived** tasks only, so a young
   repo with hundreds of open tasks and no archive — the repo that most needs a
   backlog report — prints that and exits. Relax both guards to also consider
   `data.backlog_arrivals`, and let the archive-missing branch fall through to
   the live-only path.

7. **CSV, both surfaces.**
   - Append `created_at` and `category` to the existing per-task fact table.
     Existing columns keep their positions and the **row set is unchanged**. The
     header list in `write_csv` and the `csv_rows.append([...])` producer in
     `lib/stats_data.py` are two halves of one contract — change them in
     lockstep. 10 → 12 columns.
   - Add `write_backlog_csv()` emitting
     `week_ending, category, open, arrived, departed, net`, behind a new
     `--csv-backlog FILE` flag.

   Record in the notes that open tasks are not rows in the fact table, so the
   backlog level is not reproducible from it — `created_at` there buys lead-time
   analysis, not backlog.

## Files

- `.aitask-scripts/aitask_stats.py`
- `.aitask-scripts/lib/stats_data.py` — the `csv_rows.append([...])` producer
  **only**; all other collection work belongs to t1544_3
- `tests/test_aitask_stats_py.py`

## Verification

```bash
bash tests/run_all_python_tests.sh --test-dir tests
./ait stats
./ait stats --backlog-weeks 26
./ait stats --csv /tmp/tasks.csv --csv-backlog /tmp/backlog.csv
head -1 /tmp/tasks.csv && head -3 /tmp/backlog.csv
```

- Both new sections render, each split by the category axis.
- The backlog table is ≤ 80 characters wide at the default horizon.
- Every pre-existing section is byte-identical to a pre-change capture (ignore
  the `Generated:` line).
- A fixture repo with open tasks and an **empty archive** renders the backlog
  section instead of "No completed tasks found."
- The per-task CSV has 12 columns with the original 10 unmoved; the backlog CSV
  carries the six documented columns.
- `--backlog-weeks`'s default resolves to `BACKLOG_WEEKS_DEFAULT` (assert on the
  parsed args, not on the literal).

Extend `tests/test_aitask_stats_py.py`, whose `TestCollection` builds real
markdown plus a real zstd bundle in a tempdir and patches module globals on
**both** `stats` and `stats_data`;
`test_write_csv_includes_implementation_columns` is the exact CSV-header
assertion to extend.

Do **not** pipe `ait stats` through `tail` when checking exit status — the pipe
discards it. Use `set -o pipefail` or `${PIPESTATUS[0]}`.
