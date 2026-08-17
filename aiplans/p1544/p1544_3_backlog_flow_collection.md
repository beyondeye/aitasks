---
Task: t1544_3_backlog_flow_collection.md
Parent Task: aitasks/t1544_stats_backlog_and_net_flow_by_category.md
Sibling Tasks: aitasks/t1544/t1544_1_*.md, aitasks/t1544/t1544_2_*.md, aitasks/t1544/t1544_4_*.md, aitasks/t1544/t1544_5_*.md, aitasks/t1544/t1544_6_*.md, aitasks/t1544/t1544_7_*.md, aitasks/t1544/t1544_8_*.md
Archived Sibling Plans: aiplans/archived/p1544/p1544_*_*.md
Base branch: main
Output branch: main
---

# p1544_3 — Backlog flow collection

## Goal

Two weekly series — arrivals and departures per category, over full history —
stored on `StatsData`, plus the shared helper that derives the open-task level
from them. The CLI (t1544_4) and TUI (t1544_5) become pure renderings of this.

Read t1544_1's and t1544_2's Final Implementation Notes first.

## Implementation steps

1. **Imports and constants** in `.aitask-scripts/lib/stats_data.py`:
   - `from dataclasses import dataclass, field` — **`field` is not currently
     imported**, and a bare `= Counter()` default is a mutable-default
     `ValueError` at class-definition time; the module would not import at all.
   - `BACKLOG_WEEKS_DEFAULT = 8` — the single horizon default, read by both the
     CLI flag and the TUI pane.

2. **Three new `StatsData` fields**, each
   `field(default_factory=Counter)`, placed anywhere in the defaulted tail
   (`csv_rows` is *not* last — `session_breakdown`, `inflight`, `phase_timings`
   follow it):
   - `backlog_arrivals` keyed `(category, week_offset)`
   - `backlog_departures` keyed `(category, week_offset)`
   - `backlog_excluded` keyed by reason string

3. **Three lockstep sites.** The dataclass, `_empty_stats_data()`, and
   `merge_stats_data()` — plain additive `Counter.update` in the merge, exactly
   like every other counter there. Missing the third silently drops the series
   from multi-project aggregation, which is why the merge assertion is in the
   test list below.

4. **Bucketing helpers**, both derived from the existing `week_start_for` so
   there is exactly one week-boundary definition:
   - `backlog_week_offsets(weeks) -> [weeks-1 … 1, 0]`
   - `week_end_for_offset(today, week_start_dow, offset) -> date`
     = `week_start_for(today, dow) - 7*offset + 6 days`

   Reuse `week_offset_for` unchanged, simply **without** applying the
   `0 <= week_offset <= 3` clamp, so the new counters carry full history
   (~30 weeks today). **Do not touch** any existing 4-week site:
   `sorted_weekly_keys`'s `range(4)`, the `<= 3` guards in `collect_stats`, the
   four `range(4)` sites in `aitask_stats.py`, `panes/labels.py`'s
   `_HEATMAP_WEEKS`, `panes/velocity.py`'s `weeks`.

5. **`backlog_levels(arrivals, departures, out_offsets)`** — the contract that
   must not be got wrong:

   ```python
   def backlog_levels(arrivals, departures, out_offsets):
       """Open-task level per (category, week_offset).

       `out_offsets` selects OUTPUT COLUMNS ONLY. The cumulation always runs
       over every key present in `arrivals` / `departures`, however old.
       """
   ```

   Level at offset `w` = `Σ arrivals at offsets >= w − Σ departures at offsets >= w`
   (larger offset = older). Implement as a single suffix-scan per category over
   the distinct offsets sorted descending — O(k), not O(k × weeks).

   Cumulating over `out_offsets` instead of the full keyspace drops every task
   created before the horizon: 1318 arrivals sit at offset ≥ 12, so a 12-week
   horizon would render 0 → 287 instead of 126 → 414.

   The clamp is **not** silent:
   ```python
   if raw < 0:
       excluded["negative_level"] += 1
   raw = max(0, raw)
   ```

6. **Collection — one clock, one rule.** A task has departed iff
   `parse_completed_date(frontmatter)` returns a date (`completed_at`, else
   `updated_at` when `status` is `Done`/`Completed`). The identical rule applies
   to archived and live files; there is **no** archived-vs-live special case.

   **Do not use `resolve_completion_date()` here** — it prefers the
   `merge_approved`/`review_approved` ledger stamps, and on a *live* file those
   mean "in flight", not "gone". A real example is a `status: Ready` task with a
   passing `review_approved` marker and no `completed_at`: the resolver dates it
   five weeks ago, `parse_completed_date` correctly returns `None`.

   Arrivals come from `created_at` on both trees. Departures come from
   `parse_completed_date` on both trees. Category comes from
   `task_category.resolve_category(metadata, body, filename, tally=excluded)`
   using `split_frontmatter` (both from t1544_2).

7. **Exclusions — skip entirely on *both* axes, never half-count, always tally.**
   An arrival kept with its departure dropped stays open forever. Reasons:
   `no_frontmatter`, `no_created_at`, `future_created_at` (`week_offset_for`
   returns `-1`; a negative key would poison the cumulation),
   `archived_no_completed_at`, `folded`, plus `invalid_followup_kind` from
   t1544_2 and `negative_level` from step 5.

   **Folded** = `status: Folded` **or** a `folded_into:` field (either alone
   suffices). They never get a `completed_at`, and the file is *deleted* when
   the primary archives, so counting them would make the historical series
   irreproducible. Measured 5 live / 0 archived — the exclusion costs no history.

   **Postponed counts as open** (outstanding work by the stated definition).
   **Parents and children both count**; expose a `(parents / children)` split via
   the existing `is_child_task()` so t1544_4 can put it on the `TOTAL OPEN` row.

8. **One live walk, and the opt-out.** `collect_stats` already walks the live
   tree once via `collect_inflight`; fold the arrival scan into that same pass
   rather than adding a second walk, and reuse the archived loop's
   already-parsed frontmatter. Prune `aitasks/new/` (it exists, is empty today,
   and a draft there would be a phantom arrival).

   Add `collect_stats(..., with_backlog: bool = True)` and **edit the caller**:
   `lib/work_report_gather.py` calls `collect_stats(now, 1, project_root=None)`
   only for `daily_counts` — pass `with_backlog=False` there. A default of `True`
   alone changes nothing for it.

   The flag **cannot** eliminate a live-tree walk (`collect_inflight` runs
   regardless). What it eliminates is the per-file classification and
   bookkeeping on ~2250 files. Assert that, not a stronger claim.

## Files

- `.aitask-scripts/lib/stats_data.py`
- `.aitask-scripts/lib/work_report_gather.py`
- `tests/test_stats_multistage.py` — new `_check_backlog(tmp)`

## Verification

Follow `tests/test_stats_multistage.py`'s style: script-style `_check_*(tmp)`
functions with `assert_eq` counters, the `_task()` / `_marker()` / `_ledger()` /
`_write()` fixture builders, `main()` returning 1 on failure, wrapped by
`ScriptChecksTest`. It passes `project_root=tmp` and patches **no** globals —
which is what this child needs, since the new code walks **both** trees. (Do not
mix in `tests/test_aitask_stats_py.py`'s global-patching style.)

`_check_backlog(tmp)` must cover:

- a task open across a week boundary;
- a task completed mid-series;
- a follow-up whose kind is only derivable by `classify()` (prose rule, no
  `followup_kind:` field);
- a task with a missing `created_at` → excluded from both flows, tallied;
- a **pre-horizon arrival** (offset far outside `out_offsets`) → pins step 5's
  contract: an arrival at offset 40 with `out_offsets=[3,2,1,0]` gives level 1 at
  offset 3, not 0;
- a **live task with a passing `review_approved` marker and no `completed_at`**
  → stays open;
- a task whose **ledger week differs from its `completed_at` week** → departs in
  the **`completed_at`** week;
- a **live `Done`** task → departs;
- an **archived task with no `completed_at`** → excluded from both flows;
- a **Folded** task → excluded from both flows;
- **merge / no-double-count** across two `project_root`s;
- both reconciliation identities:
  - `TOTAL OPEN` at `Now` == live files − live-folded − live-departed − live-excluded
  - `Σ departures` == `data.total_tasks` + live-departed
- `with_backlog=False`: the three counters are empty; `resolve_category` is
  invoked **zero** times (monkeypatch a call counter); every pre-existing field
  is identical to a `with_backlog=True` run.

Assert the identities on **synthetic fixtures**, never the live corpus — during
parent planning both briefly read off-by-one purely because a concurrent session
archived a task mid-measurement.

```bash
bash tests/run_all_python_tests.sh --test-dir tests
./ait stats > /tmp/after.txt   # existing sections byte-identical vs a
                               # pre-change capture, ignoring `Generated:`
```

Counting live files with `find -L aitasks -name 't*.md' -not -path '*metadata*'`
is **wrong** — it also excludes real task files whose filenames contain
"metadata". Use `iter_active_markdown_files`.

## Notes for sibling tasks

Record in the Final Implementation Notes: the final `backlog_levels` signature,
the exact `backlog_excluded` reason strings, the three `StatsData` field names,
the shape of the parents/children split, and the measured `collect_stats` cost
delta. t1544_4 and t1544_5 render directly from all of it.
