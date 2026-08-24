---
Task: t1544_4_cli_backlog_sections_and_csv.md
Parent Task: aitasks/t1544_stats_backlog_and_net_flow_by_category.md
Sibling Tasks: aitasks/t1544/t1544_5_stats_tui_backlog_panes.md, aitasks/t1544/t1544_6_backlog_stats_documentation.md, aitasks/t1544/t1544_7_manual_verification_stats_backlog.md, aitasks/t1544/t1544_8_backlog_stats_retrospective.md
Archived Sibling Plans: aiplans/archived/p1544/p1544_1_session_discovery_dedupe.md, aiplans/archived/p1544/p1544_2_task_category_axis_module.md, aiplans/archived/p1544/p1544_3_backlog_flow_collection.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-24 13:23
---

# p1544_4 — CLI backlog sections and CSV

## Context

`ait stats` answers "how much did we complete?" but cannot answer "how much is
outstanding, of what kind, and is it growing faster than we burn it down?".
t1544_3 landed the data layer for that: two weekly flows over the whole task
corpus plus the helper that derives the open-task level from them. Nothing
renders it yet.

This child is a **pure rendering** of what t1544_3 stored — two new `###`
sections in the text report, a horizon flag, and two CSV surfaces. It adds no
collection logic. Sibling t1544_5 renders the same data in the stats TUI and is
independent of this task.

Verified against current source (t1544_3 = `3fca2c8c7`, t1577 = `8726ddbc1`).
The pre-existing plan holds except where **Corrections** says otherwise.

## What t1544_3 gives us (read-only contract)

`.aitask-scripts/lib/stats_data.py`:

| name | shape |
|---|---|
| `backlog_arrivals` / `backlog_departures` | `Counter[(category_key, week_offset)]`, unclamped full history |
| `backlog_scope_arrivals` / `backlog_scope_departures` | `Counter[("parent"\|"child", week_offset)]` |
| `backlog_excluded` | `Counter[reason]` — 7 task reasons + `negative_level` (an **output-cell** count) |
| `backlog_levels(arrivals, departures, out_offsets, excluded=None)` | `Counter[(key, offset)]`; `out_offsets` selects **columns only**; emits explicit **zero cells** |
| `backlog_week_offsets(weeks)` | `[weeks-1 … 1, 0]` |
| `week_end_for_offset(today, dow, offset)` | `date` |
| `BACKLOG_WEEKS_DEFAULT` | `8` — the single horizon default, shared with the TUI pane |

`.aitask-scripts/lib/task_category.py`: keys are namespaced `kind:<k>` /
`type:<t>`; `category_display_name` yields **lowercase** labels for `kind:` and
**Title Case** for `type:` (the case difference is the intended visual separator
— do not normalize it); `is_followup_category(cat)` splits the two halves.

## Corrections to the pre-existing plan (found during verification)

1. **`main()`'s archive guard cannot simply be "relaxed"** — it sits at
   `aitask_stats.py:499`, *before* `collect_stats`, so there is no `data` to
   consult. It must **move below** `collect_stats`. Verified safe: the archive
   iterators guard on `.exists()` (`lib/archive_iter.py:117`; `Path.glob` on a
   missing dir yields nothing), and every section of `render_text_report`
   already handles an all-zero `StatsData` without crashing.

2. **The fact table's `category` column collides with t1544_3's contract.**
   `tests/test_stats_multistage.py:485,497` pin that
   `collect_stats(with_backlog=False)` calls `resolve_category` **zero** times
   and leaves `csv_rows` identical. **User decision: keep both columns.**
   `created_at` is free and unconditional; `category` is populated only under
   `with_backlog`, and the sibling assertion is **narrowed to the 10
   pre-existing columns** — exactly what its own docstring claims ("every
   pre-existing field") — with a new assertion pinning the empty-when-off
   semantic.

3. **The `excluded=` sink is per-call and per-output-cell**, so routing all
   three axes into `data.backlog_excluded` would multiply-book `negative_level`
   and make `render_text_report` non-idempotent. Each axis gets its own scratch
   `Counter`, reported as *cells*, kept distinct from the seven task reasons.

4. **`backlog_levels` emits explicit zero cells**, so "suppress all-zero rows"
   must test values, not key absence.

5. **The plan named three `StatsData` fields; there are five** — the
   parents/children split has its own flow pair and reuses `backlog_levels`.

6. **The net-flow table must not reuse the level table's row membership.**
   Measured live: `kind:docs_gap` has 3 arrivals and 3 departures inside the
   8-week window and a level of 0 at every offset — an all-zero-*level* test
   suppresses exactly the row a flow table exists to show.

## Implementation

All in `.aitask-scripts/aitask_stats.py` unless stated.

### Pre-phase (risk mitigations)

1. `[capture_stats_baseline]` Before editing any source file, at the current
   HEAD: `find . -name __pycache__ -prune -exec rm -rf {} +` to defeat the
   stale-`.pyc` trap t1544_3 recorded, then capture
   `./ait stats > <scratch>/stats_before.txt` and
   `./ait stats --csv <scratch>/tasks_before.csv` into the session scratchpad
   (**outside the repo**, so no working-tree state depends on it). Record the
   `git rev-parse HEAD` the capture was taken at in the same directory. Every
   later "existing sections byte-identical" claim compares against this file
   with the `Generated:` line stripped — and the comparison run must clear
   `__pycache__` too.

### 1. Shared axis helper

Private `_build_backlog_axis(data, week_offsets)` returning a small dataclass:

- `levels` — `backlog_levels(data.backlog_arrivals, data.backlog_departures,
  week_offsets, excluded=<scratch>)`;
- `scope_levels` — same over `backlog_scope_*`, own scratch counter;
- `total_levels` — over a **re-keyed all-tasks axis**, own scratch counter. This
  is what `TOTAL OPEN` renders. Deriving it independently rather than summing
  the clamped category rows keeps `TOTAL OPEN` equal to `parents + children`
  even if a clamp ever fires — a clamp then disagrees only with the category
  rows, and the footnote explains it. Verified today: all three agree at every
  offset (436 at `Now`), and **0 clamps over full history**.

  **The re-key must accumulate, not comprehend.** A dict comprehension
  (`Counter({("all", o): n for (c, o), n in arrivals.items()})`) keeps only the
  **last** value written for each `("all", o)` key, so every category arriving
  in the same week silently overwrites the previous one — demonstrated: three
  categories totalling 14 at one offset re-key to **2**. `TOTAL OPEN` would then
  be one arbitrary category's level, and would disagree with the parent/child
  partition — destroying the exact invariant this independent axis exists to
  protect. Build both aggregates by summation:

  ```python
  agg_arrivals, agg_departures = Counter(), Counter()
  for (_cat, off), n in data.backlog_arrivals.items():
      agg_arrivals[("all", off)] += n
  for (_cat, off), n in data.backlog_departures.items():
      agg_departures[("all", off)] += n
  ```

  The same rule applies to any future re-key of these flows;
- the ordered follow-up / genuine row blocks, each sorted
  `key=lambda c: (-levels[(c, 0)], category_display_name(c))` — the explicit
  tie-break matters because sorting a `Counter` keyset on `-level` alone is
  insertion-order dependent.

Called **once** from `render_text_report`. Kept private to `aitask_stats.py`:
promoting it to `lib/backlog_view.py` for t1544_5 was considered and rejected —
t1544_5's plan specifies its own row-cap/`Other`-bucket shape, so a shared seam
now would be designed for a consumer that does not want it. Note the option in
the Final Implementation Notes instead.

### 2. `render_backlog_level(...)`

Shaped like `render_pipeline_timing` (`:226`): heading first, then an empty-state
branch (see **The empty state** below — it is *not* a bare early return here),
then header / separator / rows, then a trailing blank line.

```
### Backlog Level (Open Tasks) - Weekly (Last 8 Weeks)
| Category             |  Now |  W-7 |  W-6 |  W-5 |  W-4 |  W-3 |  W-2 |  W-1 |
|----------------------|------|------|------|------|------|------|------|------|
| manual verification  |   71 |   23 |   24 |   25 |   39 |   47 |   55 |   64 |
| -- follow-ups        |  211 |  ... |
| Features             |  115 |  ... |
| -- genuine           |  225 |  ... |
| TOTAL OPEN           |  436 |  ... |
| of which parents     |  309 |  ... |
| of which children    |  127 |  ... |
```

**Label cell:** `f"| {label:<20.20} |"`. The **truncating** precision is
deliberate — the widest live label, `verification failure`, is exactly 20
chars, and `resolve_category`'s `type:` fallback applies no vocabulary clamp,
so a hand-edited `issue_type` could otherwise silently misalign the table.

**Numeric cells are width-adaptive, not fixed at 4.** `f"{v:>4}"` does **not**
truncate — a five-digit value silently widens that one row and breaks the
layout, and the `[1, 99]` horizon cap bounds only the *header* label, never the
values. So compute `cell_w = max(4, <widest formatted value in this table>)` in
a pre-pass over the already-built axis and apply it uniformly to the header, the
separator and every row. Alignment is the hard invariant; 80 characters is the
soft one.

The guarantee is therefore precise: **exactly 80 characters at the default
horizon while every rendered value fits 4 characters** (`24 + 7N`; ≤ 9999 in the
level table, ≤ ±999 in the net-flow table). Beyond that the table widens
uniformly and stays internally aligned rather than ragged. Both tables size
independently — the net-flow table measures its **formatted signed** strings,
since `-1000` is five characters where `1000` is four.

Column order is `Now` (offset 0) first — the headline role the existing tables
give `Total` — then `W-(n-1) … W-1`. Rows: follow-up categories, `-- follow-ups`,
issue-type categories, `-- genuine`, `TOTAL OPEN`, then the scope partition.
`--` marks a **subtotal of the rows above**; `of which` marks a **partition of
the row above** — two different operations must not share one glyph. All-zero
rows are suppressed (3 of 17 categories today).

Footnotes below the table, in the italic style of the existing
`_In flight (implementation done, awaiting gates): N_` line (`:274`):

- the `backlog_excluded` tally, summing the **seven task reasons only** and
  naming each reason with its count;
- clamped **cells** (`negative_level`) on their own line, only when non-zero,
  never added to the task total;
- Postponed counts as open, Folded is excluded;
- `bug` is net of `upstream defect` here and gross in `### By Task Type`;
- the two completion clocks — backlog uses `completed_at` (falling back to
  `updated_at` for Done); other sections prefer gate-ledger stamps. Same set of
  completed tasks, different week for ~0.3%.

**The empty state must still print the exclusion tally — it is not a footnote
of the table, it is the explanation for the table's absence.** Follow
`render_pipeline_timing`'s *shape*, not its body: a bare early return would
break the very case `main()`'s new `has_backlog` predicate exists to admit. A
repo whose open tasks all lack `created_at` has empty `backlog_arrivals` and a
populated `backlog_excluded`; it now bypasses `"No completed tasks found."` and
would then render nothing but `No open tasks found.`, hiding the several hundred
tasks and the reason they were dropped. That is capturing a diagnostic without
surfacing it, and it would pass a bare "the section renders" assertion.

So factor the tally into a helper (`_render_backlog_exclusions(data, out)`)
called on **both** paths, and make the empty-state line name the situation
rather than assert absence:

- no arrivals **and** no exclusions → `No open tasks found.`
- no arrivals **but** exclusions present → `No open tasks could be placed in the
  backlog series.` followed immediately by the tally, so the reason/count is
  visible with no table above it.

The same rule governs `render_backlog_netflow`'s empty state, except that the
tally is printed **once**, by the level section, so the flow section's empty
state only names the situation.

### 3. `render_backlog_netflow(...)`

Own row membership — `any(arrivals[(c, o)] or departures[(c, o)] for o in
offsets)` — sharing only the *ordering* rule. Signed per-week nets per
category; `ARRIVALS` / `DEPARTURES` (unsigned counts) and `NET` (signed)
summary rows.

**Columns run chronologically with `Now*` last** (user decision). Offset 0 is a
partial week by construction — measured today, every category has 0 arrivals and
0 departures there — so the unreliable cell sits at the visual edge instead of
the headline position. The level table is unaffected and keeps its pinned
`Now`-first shape: its offset 0 is a *stock*, correct as-of-now, because
`backlog_levels` cumulates everything created up to `today`.

`(partial)` cannot fit a 4-char cell, so the header reads `Now*` and a footnote
gives the covered range: `_Now* covers <week_start>..<today> (partial week)._`
— a **range**, since a flow describes a span, not an "as of" instant.

Measured live, every cell fits 4 characters today: max weekly arrivals 144, max
weekly departures 106, max |net| 82, max |per-category net| 20 — so this table
also renders at exactly 80 chars at the default horizon, and widens uniformly
via the same `cell_w` pre-pass if it ever stops fitting.

### 4. `--backlog-weeks N`

`parse_args` gains the flag with `default=BACKLOG_WEEKS_DEFAULT` (**the
constant, never a literal `8`** — the TUI pane reads the same constant, and a
literal is how two surfaces drift into different windows for one metric) and a
validator in the style of `parse_days_arg` (`:131`).

Bounds **[1, 99]**, derived rather than taste: the header cell is 4 chars, so
`W-99` fits and `W-100` silently misaligns. `0` must be rejected —
`backlog_week_offsets(0)` returns `[]`, i.e. a header row with no data columns.
Help text states the table widens by 7 characters per week (8→80, 26→206).
No wrapping and no width guard: it is an opt-in flag.

`render_text_report` gains `backlog_weeks: int = BACKLOG_WEEKS_DEFAULT`
appended — safe, because the only production caller (`:511`) and both test
callers pass everything after `data` by keyword.

### 5. `main()` guard restructuring

Move the archive check below `collect_stats`, and gate both on one **positive**
predicate rather than `not data.backlog_arrivals` (which would silently revert
to the old behaviour under `with_backlog=False`, and would print "No completed
tasks found." on a repo whose 400 open tasks all lack `created_at` — the case
where the excluded tally is the actionable output):

```python
    week_start_dow = resolve_week_start(args.week_start)
    today = date.today()
    data = collect_stats(today=today, week_start_dow=week_start_dow)
    has_backlog = bool(data.backlog_arrivals or data.backlog_excluded)

    if not ARCHIVE_DIR.exists() and not has_backlog:
        print(f"No archived tasks found in {ARCHIVE_DIR}")
        return 0

    if data.total_tasks == 0 and not has_backlog:
        print("No completed tasks found.")
        return 0
```

Both messages stay verbatim for the cases that already produced them. **Neither
is currently covered by any test** (grepped `tests/`; `test_stats_data.sh:85` is
an exit-0 smoke test only) — this task adds the first.

### 6. Section placement

Both sections are emitted immediately after the `### Summary` block's in-flight
footnote (`:275`) and before `### Daily Completions` (`:277`), so the
standing-state question the feature exists to answer is not buried under the
~450 lines of label tables. Every existing section's own text is unchanged; only
its offset in the report moves — so the byte-identity check compares section
*bodies*, not offsets.

### 7. CSV — both surfaces

**Fact table (10 → 12 columns).** Append `created_at` and `category`; the
existing ten keep their positions and the row set is unchanged. The header in
`write_csv` (`:478`) and the producer in `lib/stats_data.py` (`~:1380`) are two
halves of one contract — edit them in lockstep. In the archived loop only:

```python
        created = _parse_frontmatter_date(frontmatter.get("created_at", ""))
        category = resolve_category(frontmatter, body, filename) if with_backlog else ""
        ...
            created.isoformat() if created else "",
            category,
```

This is a **second classification pass** over the archived tree — measured
**+62 ms on a 248 ms baseline (+25%)**, paid on every `ait stats` and every
stats-TUI load. Accepted deliberately: it keeps the change inside this task's
stated scope (`stats_data.py` = the row producer only), gives every exported row
a real category regardless of backlog exclusion, and 62 ms is imperceptible for
a report command. The alternative — memoizing the category `_accumulate_backlog`
already resolves at `:1206` — needs a signature change to t1544_3's helper and
yields an empty category for backlog-excluded rows (0 of 1845 today, but
structurally reachable). Record it in the Final Implementation Notes as the
known optimization.

*Recorded caveat:* open tasks are not rows in this table, so the backlog level
is **not** reproducible from it — `created_at` here buys lead-time analysis, not
backlog.

**`write_backlog_csv(path, data, axis, week_offsets, today, week_start_dow)`**
behind `--csv-backlog [FILE]`, mirroring `--csv`'s shape (`:163`) with a
**distinct, explicitly named** const:

```python
    parser.add_argument(
        "--csv-backlog",
        nargs="?",
        const="aitask_backlog.csv",
        default=None,
        metavar="FILE",
        help="Export the weekly backlog series to CSV (default: aitask_backlog.csv)",
    )
```

Both halves of that const matter. **Omitting `const` is a silent no-op** —
verified: with `nargs="?"` and no `const`, a bare `--csv-backlog` parses to
`None`, which is byte-identical to not passing the flag at all, so the user gets
a successful exit and no file. **Copying `--csv`'s `aitask_stats.csv` is worse**
— bare `--csv --csv-backlog` would then resolve to one path, and the new
collision guard would reject a perfectly reasonable invocation. The const must
be `aitask_backlog.csv`, named in the help text exactly as `--csv` names its
own.

It emits exactly the six specified columns
`week_ending, category, open, arrived, departed, net`:

- `category` is the **raw namespaced key** (`type:feature`) — display names are
  lossy and non-uniformly cased, so they are not safe join keys;
- **real categories only** — no `-- follow-ups` / `TOTAL OPEN` pseudo-rows, which
  a naive pivot `SUM()` would double-count;
- zero cells **are** emitted, so the grid is dense and plottable;
- `week_ending` is the **canonical unclamped** week end — clamping to `today`
  would export the same calendar week under two different dates on two
  different days, silently breaking joins;
- the horizon honours `--backlog-weeks`;
- week columns are emitted **oldest-first** (`backlog_week_offsets` order), so
  the row order is a stable, documented series.

**Collision guard — preflight, resolved, and before any file is opened.** The
check lives in `parse_args`, raising `parser.error(...)`, so it fires before
`collect_stats` and before either handle is opened; `write_csv` is currently the
last statement in `main()`, so a check placed near the writers would let the
fact table be written and only then reject. Compare `Path(a).resolve() ==
Path(b).resolve()`, **not** the raw argument strings: `out.csv` and `./out.csv`
are different strings, and only `resolve()` also collapses `$PWD/out.csv`,
`a/../out.csv` and symlink aliases. (`Path.resolve()` is non-strict, so it works
on paths that do not exist yet.) The test pre-creates both files with sentinel
content, invokes the colliding form, and asserts a non-zero exit **and that
neither file's bytes changed**.

Document the invariant `open[w] - open[w+1] == net[w]`, which holds only when no
clamp fired (`open` is clamped at 0, `net` is not) and only for pairs inside the
horizon — `backlog_levels` emits no cell for the offset just past the oldest
rendered week, so the identity is checkable for every offset except that one.

### Post-phase (risk mitigations)

1. `[negative_control_row_membership]` After the suite is green, mutate
   `render_backlog_netflow`'s row-membership predicate to reuse the level
   table's all-zero-**level** suppression (the "unification" a future reader
   would plausibly make). Clear `__pycache__`, re-run
   `tests/test_aitask_stats_py.py`, and confirm the named
   zero-level-with-flow test **fails** while no unrelated assertion does.
   Record the failing test id in the Final Implementation Notes, then revert the
   mutation and re-run to green. A negative control that passes is a broken
   control, not a clean bill of health.

## Files

- `.aitask-scripts/aitask_stats.py` — axis helper, two renderers, the
  `render_text_report` signature and call sites, `write_csv` header,
  `write_backlog_csv`, `parse_args`, the two `main()` guards
- `.aitask-scripts/lib/stats_data.py` — the `csv_rows.append([...])` producer
  **only**; all other collection work belongs to t1544_3
- `tests/test_aitask_stats_py.py` — rendering, flag and CSV assertions
- `tests/test_stats_multistage.py` — narrow the one `csv_rows` assertion

## Verification

Existing assertions that pin the old shape and must change in the same commit:

- `test_aitask_stats_py.py:218` — `len(data.csv_rows[0])` `10` → `12`
- `test_aitask_stats_py.py:338-357` — the exact header list and the exact-row
  `assertIn` (the fixture carries no `created_at`, so the new cells are `""` and
  the resolved category)
- `test_stats_multistage.py:497` — `csv_rows unaffected` narrowed to the 10
  pre-existing columns, **plus** a new assertion that the `category` cell is
  empty under `with_backlog=False` and non-empty under `True`, so the new
  semantic is pinned rather than merely permitted. `:485` (`off_calls == 0`)
  must keep passing **unedited** — if it fails, the `with_backlog` guard on the
  new call was dropped.

New coverage — a dedicated `TestBacklogSections` with its **own** fixture
(archived tasks *with* `created_at`, plus live open tasks), leaving the six
existing `TestCollection` tests untouched. Same idioms: real markdown in a
tempdir, globals patched on **both** `stats` and `stats_data_mod`, sections
sliced with `report.split("### <Header>")[1].split("\n###")[0]`. Assert:

- both `###` headings render;
- the category axis carries a `kind:` row (lowercase) and a `type:` row (Title
  Case via the display map — a bare `.capitalize()` here regresses t1577);
- `-- follow-ups` + `-- genuine` == `TOTAL OPEN` == `of which parents` +
  `of which children` — on a fixture where **at least two categories arrive in
  the same week**, which is the discriminating case for the all-tasks re-key: a
  dict comprehension keeps only the last category per offset, and with one
  category per week the wrong and right forms agree, so a single-category
  fixture pins nothing;
- an all-zero-level category is suppressed from the level table but a
  zero-level category **with flow** still appears in the net-flow table — the
  discriminating case for Correction 6;
- `Now*` is the **last** net-flow column and the partial-week footnote names a
  range;
- the excluded footnote reports the task reasons and omits `negative_level`
  from that total;
- `parse_args([]).backlog_weeks is stats_data.BACKLOG_WEEKS_DEFAULT` — against
  the **constant**, not the literal `8` — plus rejection of `0`, a negative,
  and `100`;
- a 21-char category label is truncated to 20 and the row stays 80 chars;
- **width adaptation**: a fixture with a five-digit level renders a table whose
  heading-row, separator and every data row have **equal length** (and that
  length is no longer 80) — the assertion is uniformity, not a magic number,
  because `f"{v:>4}"` widens instead of truncating;
- **`write_backlog_csv` is proven as a serializer, not just a header.** A
  header-plus-one-row test passes under reversed week ordering, swapped
  `arrived`/`departed`, dropped zero rows, display labels in place of raw keys,
  and an inverted `net` sign — so assert instead, on a fixture with ≥3
  categories spanning ≥3 offsets including the partial current week:
  - the full expected row set as a set of tuples (catches dropped zero rows and
    display-vs-raw labels in one comparison),
  - `week_ending` strictly increasing in emission order (catches reversal), and
    equal to `week_end_for_offset` unclamped for the current week,
  - a category whose `arrived != departed` in some week (catches the swap) and
    one with a **negative** net (catches the sign inversion),
  - `open[w] - open[w+1] == net[w]` for every offset except the oldest rendered
    one, on a clamp-free fixture — proving the *exported* contract rather than
    re-testing the data layer;
- `--csv` and `--csv-backlog` resolving to the same path is refused with a
  non-zero exit, including the `out.csv` vs `./out.csv` alias, and **neither
  pre-existing file's bytes change**;
- **the bare, no-file form of each flag.** `parse_args(["--csv-backlog"]).csv_backlog
  == "aitask_backlog.csv"` — asserted against the const, and explicitly
  `is not None`, because a dropped `const` makes the bare flag parse exactly
  like an omitted one and silently exports nothing. Then through `main()`:
  bare `--csv --csv-backlog` together writes **two** files at the two distinct
  default names and does **not** trip the collision guard;
- through `main()`: open tasks + **empty archive** renders the backlog section
  instead of `"No completed tasks found."`, and a repo with neither still
  prints both original messages verbatim;
- **the all-excluded repo — the discriminating case for the `has_backlog`
  predicate.** A fixture whose only tasks are live and *all* excluded (no
  `created_at`), with an empty archive: `main()` must not print
  `"No completed tasks found."`, and the rendered report must name the reason
  and its count (`no_created_at: N`). Assert on the reason string and the
  number, not merely on the section heading — a bare "the section renders"
  assertion passes against an early-returning empty state that hides the tally,
  which is precisely the defect this case exists to catch.

Fixture values only — **never assert live-corpus numbers**; they move daily (the
parent plan's pinned mock already reads 418 where the corpus now says 436).
Data-layer arithmetic is pinned by `tests/test_stats_multistage.py`
(`_check_backlog_levels`, `_check_backlog`, `_check_backlog_merge`,
`_check_with_backlog_off`) — do not re-verify it here.

Suite and live checks:

```bash
bash tests/run_all_python_tests.sh --test-dir tests   # read the LAST line only
./ait stats
./ait stats --backlog-weeks 26
./ait stats --csv /tmp/tasks.csv --csv-backlog /tmp/backlog.csv
head -1 /tmp/tasks.csv && head -3 /tmp/backlog.csv
```

- Every pre-existing section body byte-identical to a pre-change capture,
  ignoring the `Generated:` line.
- The backlog table is exactly 80 characters wide at the default horizon.

Do **not** pipe `ait stats` through `tail` when checking exit status — the pipe
discards it. Use `set -o pipefail` or `${PIPESTATUS[0]}`.

## Out of scope (flagged, not fixed)

`.claude/skills/aitask-stats/SKILL.md` documents 7 CSV columns against the 10
actually emitted, omits `-w/--week-start`, and lists only 7 report sections; the
`.opencode/` and `.agents/` copies have diverged from it. This task is gated on
`risk_evaluated` only, and t1544_6 owns the documentation for this feature —
these belong there, plus a separate task for the pre-existing drift.

Step 9 (Post-Implementation) handles cleanup, archival and merge.

## Risk

### Code-health risk: medium

- Narrowing `tests/test_stats_multistage.py:497` (`csv_rows unaffected`) weakens a guard a sibling task wrote deliberately; a future reader sees a scoped assertion without the reason. · severity: medium · → mitigation: covered — the narrowing is paired with a new assertion pinning the empty-when-off semantic in both directions, and `:485` (`off_calls == 0`) must keep passing unedited
- The `category` column costs a second `resolve_category` pass over the archived tree — measured +62 ms on a 248 ms baseline (+25%), paid on every `ait stats` and every stats-TUI load, for a column that only materializes with `--csv`. · severity: medium · → mitigation: memoize_backlog_category
- `main()`'s new `has_backlog` predicate admits a repo whose tasks are all *excluded* from the series, but both renderers early-return on empty axis data and carry the exclusion tally below the table — so the exact case the predicate exists to admit could render as an empty section that hides the tally, while still passing a "section renders" assertion. · severity: medium · → mitigation: covered — the tally is factored into a helper called on both the populated and empty paths, and pinned by an all-excluded fixture asserting the reason string and count
- `main()`'s archive-missing path now runs a full `collect_stats` — including a live-tree walk — where it previously returned immediately, and **neither** degenerate message has any test today. · severity: medium · → mitigation: covered — this task adds the first tests of both messages, asserted verbatim
- ~150 lines of render logic (three level axes, per-axis scratch clamp counters, two different row-membership rules) land in `aitask_stats.py`, and t1544_5 will want a subset of the same ordering/subtotal logic for its panes. · severity: low · → mitigation: extract_backlog_view_helper
- The all-tasks axis feeding `TOTAL OPEN` is a re-key of the category flows, and the obvious dict-comprehension form silently keeps only the last category per offset — making `TOTAL OPEN` one arbitrary category's level and breaking the very `parents + children` invariant the independent axis exists to protect. · severity: medium · → mitigation: covered — the plan pins the accumulating form explicitly, and the equality is asserted on a fixture with ≥2 categories sharing an offset, where the broken form gives a different answer
- The `write_csv` header and the `lib/stats_data.py` row producer are two halves of one contract in two files; editing one alone is silently wrong. · severity: low · → mitigation: covered — the exact-header assertion and the column-count assertion each fail on a half-edit
- Two sections are inserted into `render_text_report` and both `main()` guards move, so a slip silently changes existing report output — and the only check is a byte-comparison against a capture taken by the same session that made the change. t1544_3 recorded a real trap here: an in-place mutation and its restore landed in the same second at identical size, so CPython kept the stale `.pyc` and every capture was meaningless. · severity: low (residual — addressed by inline pre-phase capture_stats_baseline) · → mitigation: inline pre-phase capture_stats_baseline
- The net-flow table's row membership differs from the level table's by design (a zero-level category with real flow must still appear); a later reader "unifying" them would silently delete rows. · severity: low (residual — addressed by inline post-phase negative_control_row_membership) · → mitigation: inline post-phase negative_control_row_membership

### Goal-achievement risk: low

- The net-flow section's summary-row shape and signed-cell formatting were designed in this plan rather than pinned by the parent plan. · severity: low · → mitigation: covered — the user reviewed the rendered shape when choosing the column order
- The 80-character layout depends on the widest category label being ≤ 20 chars (true today by exactly one character) **and** on every value fitting 4 characters — and `f"{v:>4}"` widens rather than truncating, so a five-digit level or weekly count would silently break the row. · severity: low · → mitigation: covered — the label cell truncates at `{:<20.20}` and the numeric cells are width-adaptive, so alignment holds at any magnitude; pinned by a 21-char-label test and a five-digit equal-row-length test
- `--csv` and `--csv-backlog` both write caller-supplied paths, and `write_csv` is the last statement in `main()` — a collision detected at the writers would destroy the requested task CSV before being noticed. · severity: medium · → mitigation: covered — the guard is a `parse_args`-time `Path.resolve()` comparison that fires before `collect_stats` and before any handle is opened, tested for path aliases and for both files being byte-unchanged
- `--csv-backlog` copies `--csv`'s `nargs="?"` shape, where a missing `const` makes the bare flag parse identically to an omitted one (exits 0, writes nothing) and a copied `const` makes bare `--csv --csv-backlog` collide on one path. · severity: medium · → mitigation: covered — the const is pinned to `aitask_backlog.csv` in the plan and in `--help`, and tested both for the bare-form value and for the two bare flags together producing two files
- `write_backlog_csv` serializes several coupled axes at once, so a header-plus-one-row test would pass under reversed weeks, swapped arrived/departed, dropped zero rows, display-vs-raw labels, or an inverted net sign. · severity: medium · → mitigation: covered — the export is pinned by a full row-set comparison plus discriminating fixtures for each of those five failure modes and the `open[w] - open[w+1] == net[w]` identity


### Planned mitigations
- timing: pre-phase | name: capture_stats_baseline | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — inserting sections and moving the main() guards can silently change existing output | desc: Capture ./ait stats and --csv output at HEAD with __pycache__ cleared, outside the repo, as the byte-identity ground truth
- timing: post-phase | name: negative_control_row_membership | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — the net-flow table's deliberate row-membership divergence could be silently "unified" later | desc: Mutate the net-flow predicate to the level table's all-zero-level suppression, confirm the named zero-level-with-flow test reddens and no unrelated one does, then revert
- timing: after | name: memoize_backlog_category | type: performance | priority: low | effort: low | inline_risk: medium | added_complexity: medium | addresses: code-health — the CSV category column costs a second resolve_category pass, +62 ms / +25% on every ait stats and stats-TUI load | desc: Have _accumulate_backlog expose the category it already resolves so the archived tree is classified once, keeping off_calls at zero
- timing: after | name: extract_backlog_view_helper | type: refactor | priority: low | effort: medium | inline_risk: medium | added_complexity: medium | addresses: code-health — ~150 lines of axis/ordering/subtotal logic locked inside aitask_stats.py that t1544_5 will partly duplicate | desc: Extract the backlog view logic to a pure lib/backlog_view.py once the TUI panes exist; must depend on t1544_5 so it is designed against a real second consumer
