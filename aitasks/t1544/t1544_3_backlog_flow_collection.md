---
priority: high
effort: high
depends: [t1544_1, t1544_2]
issue_type: feature
status: Ready
labels: [reporting, metrics, backlog]
gates: [risk_evaluated]
anchor: 1544
created_at: 2026-08-17 22:06
updated_at: 2026-08-17 22:09
---

## Context

Third child of t1544 (backlog level + net flow by category in `ait stats`).
Parent plan: `aiplans/p1544_stats_backlog_and_net_flow_by_category.md`.
Depends on **t1544_1** (session-discovery dedupe — without it the
no-double-count test below is meaningless) and **t1544_2** (the category axis
and `split_frontmatter`).

This is the data layer: two weekly series over the whole task corpus, stored on
`StatsData` so the CLI (t1544_4) and the TUI (t1544_5) are pure renderings of
it. It reads `created_at`, which **nothing in the stats feature reads today**,
and it scans the **live** tree, which today only `collect_inflight` does.

## Deliverable 1 — three new `StatsData` fields

- `backlog_arrivals: Counter` keyed `(category, week_offset)`
- `backlog_departures: Counter` keyed `(category, week_offset)`
- `backlog_excluded: Counter` keyed by reason string

**`field` is not currently imported.** `lib/stats_data.py` has
`from dataclasses import dataclass`; a bare `= Counter()` default is a
mutable-default `ValueError` at class-definition time and **the module will not
import**. Add `field` and use `field(default_factory=Counter)`. Note `csv_rows`
is not the last field — `session_breakdown`, `inflight`, `phase_timings` follow
it — so place the new defaulted fields anywhere in the defaulted tail.

**Three lockstep edit sites** (missing the third silently drops the series from
multi-project aggregation):

1. the `StatsData` dataclass,
2. `_empty_stats_data()`,
3. `merge_stats_data()` — plain additive `Counter.update`, exactly like every
   other counter there.

## Deliverable 2 — store flows only; derive the stock at render time

Do **not** store a backlog level. Store only arrivals and departures and derive
the level. This is deliberate: the parent task flags summing a *stock* across
projects as a hazard, and storing flows removes it structurally — a stock
derived from summed flows equals the sum of the stocks, so every merge stays the
additive `Counter.update` that already exists and there is no new merge semantic
to get wrong. Verified during planning: flows-cumulation and a direct
`created <= end AND (dep is None or dep > end)` stock agree to the unit at every
week-end over the full corpus.

### The one contract that must not be got wrong

```python
def backlog_levels(arrivals, departures, out_offsets):
    """Open-task level per (category, week_offset).

    `out_offsets` selects OUTPUT COLUMNS ONLY. The cumulation always runs over
    every key present in `arrivals` / `departures`, however old.
    """
```

Level at offset `w` = `Σ arrivals at offsets >= w  -  Σ departures at offsets >= w`
(larger offset = older week).

Cumulating over `out_offsets` instead of the full keyspace drops every task
created before the horizon. Measured: **1318 arrivals sit at offset >= 12**, so
a 12-week horizon would render 0 -> 287 instead of 126 -> 414 — a fabricated
hockey stick, with the negative that proves it wrong hidden by the clamp.

Implement as a single suffix-scan per category over the distinct offsets sorted
descending — O(k), not O(k x weeks).

**Pin it with a test:** an arrival at offset 40 with `out_offsets=[3,2,1,0]`
must give level **1** at offset 3, not 0.

### The clamp is not silent

```python
if raw < 0:
    excluded["negative_level"] += 1
raw = max(0, raw)
```

It never fires on today's data (0 anomalies measured) — which is exactly why a
silent clamp would mask a future regression instead of reporting it.

## Deliverable 3 — one event clock, one population rule

> **A task has departed iff `parse_completed_date(frontmatter)` returns a date:
> `completed_at`, falling back to `updated_at` when `status` is `Done` /
> `Completed`. The identical rule applies to archived and live files.**

This is the parent task's stated definition, operationalized with the existing
frontmatter-only helper in `lib/stats_data.py`. **User-approved during planning**
after being shown the alternative.

- **Arrivals** scan both trees (`iter_archived_markdown_files`,
  `iter_active_markdown_files`) from `created_at`.
- **Departures** scan both trees from `parse_completed_date`.
- **No archived-vs-live special case.**

**Do NOT use `resolve_completion_date()` here.** It prefers the
`merge_approved` / `review_approved` ledger stamps, and on a *live* file those
mean "in flight", not "gone". Verified on real data:
`t1180_codex_default_mode_live_verification.md` is `status: Ready` with no
`completed_at` and a passing `review_approved` marker, and
`resolve_completion_date` returns `2026-07-20` for it — booking a departure five
weeks ago for a task sitting open on the board. `parse_completed_date` returns
`None`, so the uniform rule gets it right with no carve-out.

Measured coverage — the clock is total, nothing falls through it:

| | count |
|---|---|
| archived with `completed_at` | 1818 |
| archived using the `Done` + `updated_at` fallback | 9 |
| archived with **neither** | **0** |
| live departing under this clock | 1 (a `Done`-but-unarchived task) |

**Documented consequence:** the report will carry two completion clocks — the
existing sections keep `resolve_completion_date`, the backlog sections use
`completed_at`. They never disagree on *whether* a task completed (0 archived
tasks resolve under one and not the other) and disagree on *which week* for
**26 of ~1828 by a day, 6 by a week bucket** (0.3%). t1544_4 footnotes it and
t1544_6 documents it; this child pins it with a boundary test.

### Exclusions — skip entirely, never half-count, always tally

A task excluded on one axis must be excluded on **both**, or the level goes
wrong (an arrival with a dropped departure stays open forever). Reasons:

- `no_frontmatter` — 3 real archived tasks (`t20`, `t21`, `t22`) have none at all
- `no_created_at` — missing or unparseable
- `future_created_at` — `week_offset_for` returns `-1` for a future week; a
  negative key would poison the cumulation. None exist today; the guard is cheap
- `archived_no_completed_at` — an archived task with no departure date would be
  permanently open. 0 today, and a genuine data-quality signal if it ever fires
- `invalid_followup_kind` — from t1544_2's tally
- `negative_level` — see above

### Folded tasks are excluded from both flows and tallied

They never get a `completed_at`, so they would count as open forever — and worse,
the file is **deleted** when the primary archives (`aitask_archive.sh` emits
`FOLDED_DELETED:`), so the historical series would not be reproducible:
re-running next month would give different numbers for the *same past week*.
Measured: **5 live, 0 archived** — confirming the deletion, and confirming the
exclusion costs no history. Detect via `status: Folded` **or** a `folded_into:`
field (either alone is sufficient).

### Postponed tasks are counted as open

They are outstanding work by the stated definition. 9 live, ~2% of the total.
t1544_4 calls this out in the section footnote; whether parking should be netted
out is a question for the retrospective child, not a silent default.

### Parents and children are both counted

A parent stays open until all its children archive, so a coordination shell and
its children all count. That is defensible but must be **visible**: the
`TOTAL OPEN` row carries a `(parents / children)` split via the existing
`is_child_task()`. Roughly 300 parents + 116 children today, ~29 of the parents
being shells with pending `children_to_implement`.

## Deliverable 4 — week bucketing and the shared horizon

Reuse the existing `week_offset_for()` / `week_start_for()` with the
`0 <= week_offset <= 3` clamp simply **not applied**, so the new counters carry
full history (~30 weeks today). Add two helpers, both derived from
`week_start_for` so there is exactly one week-boundary definition:

- `backlog_week_offsets(weeks) -> [weeks-1 … 1, 0]`
- `week_end_for_offset(today, week_start_dow, offset) -> date`
  (`week_start_for(today, dow) - 7*offset + 6 days`)

Add `BACKLOG_WEEKS_DEFAULT = 8` here. It is the **single** horizon default: the
CLI's `--backlog-weeks` argparse default and the TUI pane both read it, so the
two surfaces cannot show different windows for the same metric. The horizon is
render-time only — stored flows are unclamped — so changing it never invalidates
data.

**Do not touch** the existing 4-week sites: `range(4)` in
`stats_data.sorted_weekly_keys`, the `<= 3` guards in `collect_stats`, the four
`range(4)` sites in `aitask_stats.py`, `panes/labels.py::_HEATMAP_WEEKS`,
`panes/velocity.py`'s `weeks`. Every existing table and chart must be unchanged.

## Deliverable 5 — one live walk, and the opt-out

`collect_stats` **already** walks the live tree once via `collect_inflight`.
Fold the backlog live scan into that same pass rather than adding a second walk,
and reuse the archived loop's already-parsed frontmatter rather than re-parsing.
Also prune `aitasks/new/` (it exists, is empty today, and a draft dropped there
would become a phantom arrival).

Add `collect_stats(..., with_backlog: bool = True)` and **edit the one caller
that should opt out**: `lib/work_report_gather.py` calls
`collect_stats(now, 1, project_root=None)` purely to read `daily_counts`; change
it to pass `with_backlog=False`. A default of `True` alone changes nothing for it.

**Assert the real cost contract, not a stronger one.** The flag **cannot**
eliminate a live-tree walk — `collect_inflight` runs regardless, and the arrival
scan is folded into it. What it eliminates is the per-file classification and
bookkeeping on ~2250 files (measured 0.15s, roughly doubling `collect_stats`).
The three tests are therefore:

1. `backlog_arrivals` / `backlog_departures` / `backlog_excluded` are empty;
2. `resolve_category` is invoked **zero** times (monkeypatch a call counter) —
   this is the measurable contract;
3. every pre-existing field — `daily_counts`, `total_tasks`, `inflight`,
   `phase_timings` — is identical to a `with_backlog=True` run, i.e. the flag is
   purely subtractive.

A genuine no-live-walk opt-out would additionally have to gate
`collect_inflight`. That is **out of scope** — pre-existing cost this task does
not introduce, and gating it changes the meaning of a field other callers read.

## Key files to modify

- `.aitask-scripts/lib/stats_data.py` — the three fields (+ `field` import), the
  three lockstep sites, `backlog_levels`, `backlog_week_offsets`,
  `week_end_for_offset`, `BACKLOG_WEEKS_DEFAULT`, the collection changes, the
  `with_backlog` parameter
- `.aitask-scripts/lib/work_report_gather.py` — pass `with_backlog=False`
- `tests/test_stats_multistage.py` — new `_check_backlog(tmp)`

## Reference files for patterns

- `.aitask-scripts/lib/stats_data.py` — `collect_stats`, `collect_inflight`,
  `iter_active_markdown_files`, `parse_completed_date`, `week_offset_for`,
  `week_start_for`, `is_child_task`, `chart_totals`, `merge_stats_data`,
  `_empty_stats_data`
- `tests/test_stats_multistage.py` — **the style to follow**: script-style
  `_check_*(tmp)` functions with `assert_eq` counters, `_task()` / `_marker()` /
  `_ledger()` / `_write()` fixture builders, `main()` returning 1 on failure,
  wrapped by `ScriptChecksTest`. It passes `project_root=tmp` and patches **no**
  globals — which is what this child needs, since the new code walks **both**
  trees. (`tests/test_aitask_stats_py.py` uses the other style, patching module
  globals on both `stats` and `stats_data`; do not mix them.)

## Verification steps

```bash
bash tests/run_all_python_tests.sh --test-dir tests
./ait stats > /tmp/after.txt   # existing sections byte-identical vs a
                               # pre-change capture, ignoring `Generated:`
```

`_check_backlog(tmp)` must cover, at minimum:

- a task **open across a week boundary**
- a task **completed mid-series**
- a **follow-up whose kind is only derivable by the classifier** (prose rule, no
  `followup_kind:` field)
- a task with a **missing `created_at`** (excluded from both flows, tallied)
- a **pre-horizon arrival** (offset far outside `out_offsets`) — pins the
  `backlog_levels` contract
- a **live task with a passing `review_approved` marker and no `completed_at`**
  -> stays **open**
- a task whose **ledger week differs from its `completed_at` week** -> departs in
  the **`completed_at`** week
- a **live `Done` task** -> departs
- an **archived task with no `completed_at`** -> excluded from both flows
- a **Folded** task -> excluded from both flows
- both reconciliation identities (below)
- **merge / no-double-count** across two `project_root`s

### The two reconciliation identities

Assert these on **synthetic fixtures**, not the live corpus — during planning
both briefly read off-by-one purely because a concurrent session archived a task
mid-measurement:

- `TOTAL OPEN` at `Now` == live files − live-folded − live-departed − live-excluded
- `Σ departures over all history` == `data.total_tasks` + live-departed

The second holds because every archived task resolves a date under *both* clocks
(0 ledger-only, 0 `completed_at`-less). If that stops being true,
`archived_no_completed_at` is the counter that says so.

**Careful with `find`:** counting live files with
`find -L aitasks -name 't*.md' -not -path '*metadata*'` is **wrong** — it also
excludes three real task files whose *filenames* contain "metadata". Use
`iter_active_markdown_files`.

**Path resolution:** the stats data layer resolves paths from the process cwd; a
probe run from the wrong directory silently scans nothing and reports all-zero.
Pass `project_root=` in tests.

## Notes for sibling tasks

Record the final shape of `backlog_levels`, the exact `backlog_excluded` reason
strings, and the `StatsData` field names in the Final Implementation Notes —
t1544_4 and t1544_5 render directly from them.
