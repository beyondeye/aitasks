---
Task: t1544_stats_backlog_and_net_flow_by_category.md
Branch: (current branch)
Base branch: main
Output branch: main
---

# t1544 — Backlog level and net flow by category in `ait stats`

### Pre-phase (risk mitigations)

Carried verbatim into `t1544_1`'s child plan, where it executes — this parent
decomposes, so its own implementation body is the decomposition itself.

1. `[characterize_session_discovery]` Before touching
   `_assemble_aitasks_sessions` in `lib/agent_launch_utils.py`, add a
   characterization test pinning its **current** output for the non-duplicate
   cases: a single live root; a live entry plus a registered entry with distinct
   names; a `STALE` registry row (dropped by `discover_stats_sessions`); and the
   `found.sort(key=lambda s: s.session)` ordering. Assert on the returned
   `AitasksSession` list — count, `project_name`, `project_root`, `is_live`,
   `is_stale`, order. The test must pass **unchanged** after the dedupe lands;
   only a new duplicate-input case may be added. Without this, "the dedupe
   changed only the duplicate case" is an assertion no one can check, and the
   helper feeds board, monitor, minimonitor, the switcher and stats.

## Context

`ait stats` today answers exactly one question: *how much did we complete?* Every
counter in `lib/stats_data.py` is keyed by a **completion** date and scans the
**archived** tree only — `created_at` is read nowhere in the stats feature, and
active tasks are touched only by `collect_inflight()`.

That leaves the operationally important question unanswerable: *how much is
outstanding, of what kind, and is it growing faster than we burn it down?* A
prototype run over the real corpus measured the backlog roughly doubling in five
weeks, with auto-spawned follow-ups going 46 → ~195 — now **~47% of the whole
backlog** — while genuine new work grew only 155 → ~221.

The intended outcome is a durable, ongoing view of that signal: a weekly
**backlog level** (a stock) and a weekly **net flow** (arrivals vs departures,
the flow that explains why the stock moves), both split by a single unified
category axis, on all three existing stats surfaces (CLI text, CSV, TUI).

## Decisions taken during planning

| Decision | Choice |
|---|---|
| CLI table shape | Categories as **rows**, weeks as **columns**; default horizon **8 weeks**, `--backlog-weeks N` to widen. Rendered against real data at **exactly 80 chars** — see below. |
| CSV | Append `created_at` + `category` to the existing per-task fact table **and** add `--csv-backlog FILE` for the weekly series |
| Task shape | **Decompose into children** — 6 implementation children + retrospective + manual-verification sibling |
| Category key | **Namespaced** `kind:<followup_kind>` / `type:<issue_type>`, not a flat string (see Design §1) |
| Storage shape | **Flows only**; the stock is derived at render time |
| Event clock | **One** clock, the task's own: departed iff `parse_completed_date()` returns a date (`completed_at`, else `updated_at` when `Done`), applied identically to both trees (see Design §2) |
| Horizon | One shared `BACKLOG_WEEKS_DEFAULT = 8` in `lib/stats_data.py`, read by both the CLI flag default and the TUI pane |
| Config files | **None modified.** `backlog` is added to `DEFAULT_PRESETS` only; the project-local JSON override surface is preserved and now tested |
| Week start | Stays Monday-only, **explicitly** (see Design §5) |

The chosen CLI shape, rendered from the live corpus during planning:

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
| ...                                                                          |
| -- genuine           |  221 |  126 |  126 |  145 |  168 |  202 |  214 |  219 |
| TOTAL OPEN           |  418 |  166 |  170 |  191 |  246 |  328 |  380 |  411 |
```

## Design

### 1. The category axis — new pure module `lib/task_category.py`

`resolve_category(metadata, body, filename) -> str` returns a **namespaced** key:

1. `kind:<k>` where `k` = `followup_kind` from frontmatter — `_unquote()`d, then
   clamped through `followup_kinds.followup_kind_field()`;
2. otherwise `kind:<k>` where `k` = `followup_backfill_classify.classify(...)["kind"]`
   when not `None` — the existing **pure** retro-classifier (no writes, no git,
   no subprocess);
3. otherwise `type:<issue_type>` — the task is genuine new work.

**Why namespaced and not a flat string.** `manual_verification` is a member of
*both* vocabularies. A flat axis would need the argument "classify() rule 5
guarantees an MV task never falls through to step 3" to stay true forever — but
`aitasks/metadata/task_types.txt` is **user-extensible**, so a user adding
`docs_gap` or `review_finding` as an issue type silently merges two categories.
Namespacing removes the whole class of ambiguity and makes display dispatch a
prefix check instead of a precedence rule.

It also protects existing output. `aitask_stats.py:212`'s map has no entry for
`manual_verification` or `enhancement`, so today `### By Task Type` renders
`Manual_verification` and `Enhancement` (verified). Had `get_type_display_name`
delegated to a kind-first resolver, those rows would silently become
`manual verification` — breaking "Existing stats output for the current
categories is unchanged". With namespacing, `type_display_name()` stays its own
function and `get_type_display_name` delegates to *that*, byte-identically.

Public surface: `resolve_category`, `category_display_name` (prefix dispatch →
`followup_kinds.label_for()` lowercase for kinds, `TYPE_DISPLAY_NAMES` Title
Case for types), `is_followup_category`, `type_display_name`.

`_unquote()` is a single private helper with a comment stating it exists **only**
to compensate for the flat frontmatter scanner and is deleted when t1304 lands.
It also `.strip()`s. When a present-but-`invalid` `followup_kind` falls through
to `classify()`, that is tallied as `invalid_followup_kind` rather than silently
swallowed — zero today, so it is a free tripwire.

**Nothing is written.** Classification happens at read time; this task does not
backfill or write `followup_kind` onto any task file.

### 2. Store flows only; derive the stock at render time

Three new `field(default_factory=Counter)` fields on `StatsData`
(**`field` is not currently imported** — `stats_data.py:20` is
`from dataclasses import dataclass`; a bare `= Counter()` is a mutable-default
`ValueError` at class-definition time and the module would not import):

- `backlog_arrivals: Counter` keyed `(category, week_offset)`
- `backlog_departures: Counter` keyed `(category, week_offset)`
- `backlog_excluded: Counter` keyed by reason

**Why flows, not the stock:** the task flags summing a *stock* across projects as
a hazard. Storing only flows removes it structurally — a stock derived from
summed flows equals the sum of the stocks, and every merge stays the additive
`Counter.update` that `merge_stats_data()` already does for every other field.
Verified arithmetically: flows-cumulation and a direct
`created <= end AND (dep is None or dep > end)` stock agree to the unit at every
week-end over the full 2246-file corpus.

**The one contract that must not be got wrong:**

```python
def backlog_levels(arrivals, departures, out_offsets):
    """Open-task level per (category, week_offset).

    `out_offsets` selects OUTPUT COLUMNS ONLY. The cumulation always runs over
    every key present in `arrivals` / `departures`, however old.
    """
```

Cumulating over `out_offsets` instead of the full keyspace drops every task
created before the horizon: 1318 arrivals sit at offset ≥ 12, and a 12-week
horizon would render 0 → 287 instead of 126 → 414 — a fabricated hockey stick,
with the negative that proves it wrong hidden by the clamp. A unit test pins it:
an arrival at offset 40 with `out_offsets=[3,2,1,0]` must give level 1 at
offset 3, not 0. Implementation is a single suffix-scan per category over the
distinct offsets sorted descending — O(k), not O(k·weeks).

**One event clock, one population rule — the task's stated definition.**

> **A task has departed iff `parse_completed_date(frontmatter)` returns a date:
> `completed_at`, falling back to `updated_at` when `status` is `Done` /
> `Completed`. The identical rule applies to archived and live files.**

This is the task's own definition ("`completed_at` absent or `> end(W)`"),
operationalized with the existing frontmatter-only helper (`stats_data.py:285`) —
**not** `resolve_completion_date()`, which prefers `merge_approved` /
`review_approved` ledger stamps and would deliver a different series than the one
specified. *User-approved during planning, having been shown the alternative and
its measured cost.*

- **Arrivals** scan both trees (`iter_archived_markdown_files`,
  `iter_active_markdown_files`) from `created_at`.
- **Departures** scan both trees from `parse_completed_date`.
- **No archived-vs-live special case.** One clock, one rule, applied uniformly —
  which is what lets the level, both flows, both CSVs and the boundary tests
  assert the same contract.

Measured coverage — the clock is total, so nothing falls through it:

| | count |
|---|---|
| archived with `completed_at` | 1818 |
| archived using the `Done` + `updated_at` fallback | 9 |
| archived with **neither** | **0** |
| live departing under this clock | **1** (`t1392`, `status: Done`, unarchived) |

The uniform rule also gets the in-flight case right for free.
`t1180_codex_default_mode_live_verification.md` is `status: Ready` with no
`completed_at` and a passing `review_approved` marker — `resolve_completion_date`
returns `2026-07-20` for it, which would have booked it as a departure five weeks
ago while it sits open on the board. `parse_completed_date` returns `None`, so it
is simply open. No live-file carve-out is needed to achieve that.

**The one documented consequence.** The report now carries two completion clocks:
the existing sections keep `resolve_completion_date`, the backlog sections use
`completed_at`. They agree on *whether* a task completed (measured: 0 archived
tasks resolve under one clock and not the other) and can disagree on *which week*
— **26 of 1828 by a day, 6 by a week bucket** (0.3%). Recorded in the section
footnote and in `commands/board-stats.md:78` (which already documents the
fallback chain), and pinned by a boundary test containing a task whose ledger
week and `completed_at` week straddle a week edge, asserting the backlog buckets
it by `completed_at`.

**Guard.** An *archived* task that resolves no departure date would become
permanently open, so it is excluded from **both** flows and tallied as
`archived_no_completed_at` — 0 today, and a genuine data-quality signal if it
ever fires (an archived task should always carry one).

- **Folded tasks are excluded from both flows** and tallied. They never get a
  `completed_at`, so they would count as open forever; worse, the file is
  *deleted* when the primary archives (`aitask_archive.sh` `FOLDED_DELETED:`), so
  the historical series would not be reproducible — re-running next month would
  give different numbers for the same past week. Measured: 5 live, **0 archived**
  — confirming the deletion, and confirming the exclusion has no effect on the
  historical departure series. Detected by `status: Folded` **or** a
  `folded_into:` field (either alone is sufficient).
- **Postponed tasks are counted as open** and called out in the section
  footnote. They are outstanding work by the task's own definition ("created,
  not yet completed"); 9 live, ~2% of the total. Whether parking should be
  netted out is a retrospective question, not a silent default.
- **Parents and children are both counted**, and the `TOTAL OPEN` row carries a
  `(parents / children)` split via the existing `is_child_task()` — roughly
  300 parents + 116 children today, of which ~29 parents are coordination shells
  with pending `children_to_implement`. Without the split the headline reads as
  "420 units of work" when a chunk of it is coordination, not work.
- A task with missing / unparseable `created_at`, no frontmatter at all, or a
  future-dated `created_at` (`week_offset_for` returns `-1`) is skipped
  **entirely** — never half-counted into departures only — and tallied under
  `no_created_at` / `no_frontmatter` / `future_created_at`.
- **The clamp is not silent.** `if raw < 0: excluded["negative_level"] += 1`
  before clamping to 0. It never fires on today's data (0 anomalies measured),
  which is exactly why a silent clamp would mask a future regression instead of
  reporting it.

**Week bucketing — one boundary definition, no widened constant.** The new
counters reuse the existing `week_offset_for()` / `week_start_for()` with the
`0 <= week_offset <= 3` clamp simply **not applied**, so they carry full history.
Two new helpers, both derived from `week_start_for`:
`backlog_week_offsets(weeks)` and `week_end_for_offset(today, dow, offset)`.

**One horizon default, shared by both surfaces.** `lib/stats_data.py` owns
`BACKLOG_WEEKS_DEFAULT = 8`. The CLI's `--backlog-weeks` uses it as its argparse
default and the TUI pane reads the same constant — neither declares its own
number, so the two surfaces cannot show different windows for the same metric.
(An earlier draft had the CLI at 8 and a pane-local `_BACKLOG_WEEKS = 12`; that
divergence is exactly what this constant exists to prevent.) A test asserts both
call sites resolve to the constant rather than a literal. The horizon is
render-time only — the stored flows are unclamped — so changing the default
never invalidates stored data. The TUI has no per-pane override in this task;
if one is added later it must be a *user* setting applied to both surfaces, not
a second default.
The existing `range(4)` sites (`stats_data.py:898`,
`aitask_stats.py:363/380/398/416`), the `<= 3` guards,
`labels.py:_HEATMAP_WEEKS` and `velocity.py:weeks` are **not touched**.

**Body for the classifier — extend the existing scanner, don't add a parallel
one.** `stats_data.parse_frontmatter` (:249) is the flat scanner and returns no
body. Add `split_frontmatter(content) -> Tuple[Dict[str,str], str]` sharing that
exact loop and returning the body at the `break`; `parse_frontmatter` becomes a
thin caller that discards the body. One boundary definition, zero behaviour
change for existing callers. This deliberately does **not** switch the stats path
to `task_yaml.parse_frontmatter` — that is t1304's benchmark-gated decision, and
the YAML parse costs 0.67s over 2237 files versus the flat scanner's near-zero.
Measured: `classify()` fed the flat parser's output vs the typed output produced
**0 disagreements** across the whole corpus.

**Single live walk.** `collect_stats` already walks the live tree once via
`collect_inflight` (:1129). Fold the backlog live scan into that one pass, and
reuse the archived loop's already-parsed frontmatter at :1040 rather than
re-parsing. Also prune `aitasks/new/` (it exists, is empty today, and a draft
dropped there would become a phantom arrival).

**Opt-out for callers that don't want it — and the caller must actually be
changed.** `collect_stats(..., with_backlog: bool = True)`. A default of `True`
alone changes nothing for `work_report_gather.py:394`, whose existing
`collect_stats(now, 1, project_root=None)` call would keep paying the new cost
just to read `daily_counts`. So that call site is **edited in the same child** to
`collect_stats(now, 1, project_root=None, with_backlog=False)`. The default stays
`True` so `ait stats` and the TUI get the series without opting in; `False` is
the explicit exception, taken by exactly one caller today.

**What the flag does and does not buy — the test asserts the real contract, not
a stronger one.** `collect_stats` **already** walks the live tree
unconditionally: it calls `collect_inflight` (:1129), whose
`iter_active_markdown_files` pass happens whatever this flag says. Since the
backlog arrival scan is folded into that same existing pass (above),
`with_backlog=False` cannot and does not eliminate a live-tree walk. What it
eliminates is the **per-file classification and bookkeeping** — the
`resolve_category()` call, the body slice and the date parses on every one of
~2250 archived + live files, which is the measured cost (0.15s, roughly doubling
`collect_stats`).

So the three tests assert exactly that, and nothing stronger:

1. `data.backlog_arrivals` / `backlog_departures` / `backlog_excluded` are empty;
2. `resolve_category` is invoked **zero** times (monkeypatch a call counter) —
   this is the measurable cost contract;
3. every pre-existing field — `daily_counts`, `total_tasks`, `inflight`,
   `phase_timings` — is identical to a `with_backlog=True` run, i.e. the flag is
   purely subtractive.

A genuine no-live-walk opt-out would additionally have to gate `collect_inflight`
(and `work_report_gather` reads neither `inflight` nor `phase_timings`, so it
would benefit). That is **out of scope**: it is pre-existing cost this task does
not introduce, and gating it changes the meaning of a field other callers do
read. Noted here so the omission is deliberate rather than overlooked.

### 3. CLI — two new sections plus two flags

Two `render_*(data, out, …)` functions shaped like `render_pipeline_timing`
(`aitask_stats.py:228`), called from `render_text_report`. `backlog_weeks: int = 8`
is appended to its signature — safe, since the only production caller (:513) and
the only test caller both use keyword arguments.

Rows are categories: follow-up kinds first, then issue types, each block sorted
by current level descending, with `-- follow-ups`, `-- genuine` and `TOTAL OPEN`
summary rows. Columns are `Now` plus the horizon weeks.

Three details the review caught:

- **The current column is a partial week.** `week_end_for_offset(today, dow, 0)`
  is up to six days in the future; its *level* is correct-as-of-now but its
  arrival/departure cells cover a partial week and would read as a volume
  collapse. Label it `min(week_end, today)` with a `(partial)` suffix, mirroring
  the existing tables' `This Week` header.
- **`bug` appears twice in one report with different values** — gross in
  `### By Task Type`, net of `upstream_defect` (148 archived tasks) in the new
  section. One-line footnote under the backlog table.
- **A repo with open tasks and no archive currently prints nothing.**
  `aitask_stats.py:501` returns early when `ARCHIVE_DIR` is missing and :509 when
  `total_tasks == 0` — and `total_tasks` counts archived tasks only. A young repo
  with 400 open tasks and zero archives, precisely the one that most needs a
  backlog report, prints "No completed tasks found." Relax both guards to also
  check `data.backlog_arrivals`.

New flags: `--backlog-weeks N` (default 8, validated) and `--csv-backlog FILE`.

### 4. CSV — both surfaces

- The existing per-task fact table gains two **appended** columns, `created_at`
  and `category`. Existing columns keep their position and the row set is
  unchanged; the header (`aitask_stats.py:481`) and the row producer
  (`stats_data.py:1091`) change in lockstep. *Caveat recorded:* open tasks are
  not rows in this table, so the backlog level is **not** reproducible from it —
  `created_at` here buys lead-time analysis, not backlog. The backlog series
  lives in the new writer.
- New `write_backlog_csv()` emitting `week_ending, category, open, arrived,
  departed, net`, reachable via `--csv-backlog FILE`.

### 5. TUI — new `stats/panes/backlog.py`

- `backlog.level` — `DataTable` category × week, mirroring
  `labels.py:_render_heatmap`. The corpus resolves to **17 distinct categories**;
  a 13-column × 17-row table needs a row cap with an `Other` bucket in the style
  of `chart_totals` (`stats_data.py:917`).
- `backlog.netflow` — **category-split**, not a totals chart. A plain
  `multiple_bar(weeks, [arrivals, departures])` mirroring `velocity.py` would
  drop the category dimension and fail the acceptance criterion. Use top-N
  categories + `Other`, and note `render_chart` defaults to `width=100`
  (`panes/base.py`), so per-category series must be capped rather than stacked.

Registered via `register(PaneDef(...))` and **added to the eager import list at
`stats/panes/__init__.py:9`** — a missed import there is a `ModuleNotFoundError`
that stops the whole TUI from starting. Guarded by an import-the-package test
asserting both ids are in `PANE_DEFS`.

**Presets — the task's premise is wrong, but nothing gets deleted.**
`load_layered_config` uses `deep_merge`, which merges dicts per-key and only
replaces lists. Verified: `stats_config.load()["presets"]` already contains
`sessions`, so the JSON's missing key masks **nothing**, and adding a new preset
to `DEFAULT_PRESETS` alone is sufficient and sufficient-by-mechanism, not by
luck. The task's "add to both or you add a third divergence" instruction rests
on a false premise.

So: **add `"backlog"` to `stats_config.py DEFAULT_PRESETS` only, and change no
config file at all.** No `aitasks/metadata/stats_config.json` edit, no data-branch
commit.

An earlier draft proposed deleting that file's redundant `presets` block. That is
withdrawn: it holds no genuine overrides *in this checkout*, which proves the
committed file is redundant **here** — not that the data-branch JSON is never a
real override surface in another project. Deleting it would remove a supported
project-local layout override to fix a cosmetic duplication, and could silently
discard a user's layout.

What *is* delivered instead is a **precedence test** making the override contract
explicit and enforced, since it is currently neither documented nor covered:

1. a preset key present only in `DEFAULT_PRESETS` (e.g. the new `backlog`)
   appears in `stats_config.load()["presets"]`;
2. a `presets.<name>` list present in the JSON **replaces** the code list for
   that preset (list semantics — this is the real, unnoticed drift: a pane added
   to an existing code preset *is* masked by a project JSON that pins that
   preset). The test pins the behaviour rather than changing it;
3. `backlog` survives alongside an existing JSON `presets` block — i.e. adding
   the pane cannot discard a user's overrides.

Also symmetric-but-additive: an equality test between the two literals would
lock the duplication in permanently, so the tests assert the **effective** config
via `stats_config.load()`, never the two literals.

The list-replacement semantics in (2) are worth a follow-up (merge-vs-replace for
config overrides over code defaults, per `planning_conventions.md`), but changing
them is a behaviour change to every preset and is **out of scope** here — the
test documents the current contract so a future task can change it deliberately.

**Week start.** The pane uses Monday, like every other pane, because
`stats_app.py` hardcodes `week_start_dow=1` at both `collect_stats` call sites
(:322, :356) *and* because the string→dow resolver `resolve_week_start` lives in
the CLI, not in `lib/` — honouring `stats_config`'s persisted-but-unread
`week_start` would require moving that resolver first. Stated in a code comment
pointing at the existing `panes/overview.py:13` t597_4 TODO — not silently
inherited.

### 6. Session-discovery dedupe (pre-existing bug, blocks the merge criterion)

`merge_stats_data` over `discover_stats_sessions()` **can** double-count today.
`_assemble_aitasks_sessions` (`lib/agent_launch_utils.py`) applies no dedupe
among live entries, and its registered-vs-live dedupe compares `project_name`,
not the path — while `AitasksSession.key` is `realpath(project_root)` and
`_stats_for` caches on that key, so it hands the **same StatsData object** back
twice and every counter doubles. Two reachable triggers: two live tmux sessions
in one repo, and a repo whose `project_config.yaml` declares a `project: name:`
differing from its directory basename (all six registered repos happen to match
today — luck, not a guarantee).

Fix: dedupe on `key` in `discover_stats_sessions()`, preferring the live entry,
and make the registered-vs-live dedupe path-based. This already corrupts every
existing flow counter; for a stock it would be unrecoverable, and the acceptance
criterion "a multi-project run does not drop or double-count them" is untestable
without it.

## Measured ground truth (probe over the real corpus during planning)

A throwaway probe implementing this design reproduces the task's prototype table
and pins the reconciliation numbers:

| Quantity | Value |
|---|---|
| Archived files / with a completion date | 1831 / **1828** (== `data.total_tasks`) |
| Archived tasks whose two clocks differ | 26 by a day, **6 by a week bucket** (0.3%) |
| Archived resolving under one clock but not the other | **0** in either direction |
| Live files | **420** (was 416 an hour earlier — concurrent sessions are moving the corpus) |
| Live `Done` but unarchived → **departed** | 1 (`t1392`) |
| Folded — live / archived | **5 / 0** (confirms deletion at archival) |
| Excluded — no frontmatter at all | **3** (`t20`, `t21`, `t22`, all archived) |
| Full scan incl. `classify()` on every file | 0.15s (baseline `collect_stats` 0.17s → roughly **2×**) |
| Deepest week offset with data | 29 (≈30 weeks of history) |
| Distinct categories resolved | 17 (14 present live) |

Under the approved `completed_at` clock a confirming run gives arrivals 2243,
departures 1829, **open now 414**, excluded `{no_frontmatter: 3, folded: 5}` —
and both reconciliation identities hold exactly (see Verification). Absolute
numbers are a moving snapshot; the **identities** are what the tests assert.

Corrections this forced:

1. **The live population is 420 (416 an hour earlier), not the 413 quoted in the
   task** — and it moves while you work. That figure
   came from a `find … -not -path '*metadata*'` which also excludes three task
   files whose *filenames* contain "metadata". Nothing derives from 413.
2. **`ait stats` resolves its paths from the process cwd.** A probe run from the
   wrong directory silently scans nothing and reports all-zero — so the new tests
   must pass `project_root=` (the `test_stats_multistage.py` style, preferred
   here since the new code walks both trees) or patch the globals on both modules.
3. The TUI cost is what to watch, not the CLI: `_load_data` runs synchronously in
   `on_mount` and collects once per session, so ~7 registered repos go from
   ~1.2s to ~2.3s of blocking startup. Hence the `with_backlog` opt-out.

## Decomposition

All children are **in-scope siblings**, plus a trailing retrospective per
`planning_conventions.md`. Ordering is testability-first — the pure, riskiest
units land and are provable before any surface consumes them.

| Child | Scope | Testable unit | Depends |
|---|---|---|---|
| `t1544_1` | Session-discovery dedupe (§6) | Two live roots at one path + a registry-name-mismatch row → 1 entry | — |
| `t1544_2` | `lib/task_category.py` + `split_frontmatter` (§1) | `tests/test_task_category.py`: precedence, unquote/clamp, invalid-with-tally, body slice against unterminated / no-frontmatter / `---`-in-body fixtures, `get_type_display_name` byte-identity | — |
| `t1544_3` | Backlog flows in `stats_data.py` (§2) + the `with_backlog=False` edit at `work_report_gather.py:394` | `_check_backlog(tmp)` in `test_stats_multistage.py`: open-across-boundary, completed-mid-series, classifier-only follow-up, missing `created_at`, **pre-horizon arrival**, **a live `review_approved`-pass task with no `completed_at` stays open**, **a task whose ledger week ≠ `completed_at` week departs in the `completed_at` week**, **a live `Done` task departs**, **an archived task with no `completed_at` is excluded from both flows**, Folded excluded, both reconciliation identities, merge/no-double-count; plus the three `with_backlog=False` tests | _1, _2 |
| `t1544_4` | CLI sections, flags, CSV (§3, §4) | Section headers present; a repo with 0 archives still renders; CSV header assertion; `--backlog-weeks` default resolves to `BACKLOG_WEEKS_DEFAULT` | _3 |
| `t1544_5` | TUI panes + `backlog` preset (§5) | `PANE_DEFS` membership (guards the `ModuleNotFoundError` trap); the three-part preset **precedence** test; pane horizon resolves to `BACKLOG_WEEKS_DEFAULT` | _3 |
| `t1544_6` | Website docs | Docs build; see below | _4, _5 |
| `t1544_7` | Aggregate manual verification | Human | _6 |
| `t1544_8` | Retrospective | Written outcome | all |

`t1544_6` is a first-class docs child, not a verification afterthought, per
`planning_conventions.md`, and it has real errors to fix beyond the new feature:

- `tuis/stats/_index.md:57` — "Four presets ship" (already 6, becoming 7).
- `tuis/stats/_index.md:66` — "Presets are defined in
  `aitasks/metadata/stats_config.json`" is factually wrong. They are defined in
  `stats_config.py DEFAULT_PRESETS`; the JSON is an **optional project-local
  override layer** that merges per key and replaces per list. That is exactly the
  contract `t1544_5`'s precedence test pins, so the doc and the test land
  describing the same thing.
- `commands/board-stats.md:64` — the flag table gains `--backlog-weeks` and
  `--csv-backlog`; `:80` pins the exact 10-column CSV list, which becomes 12.
- `commands/board-stats.md:78` already documents the completion fallback chain
  for the existing counters; extend it to state that the backlog series uses
  `completed_at` (falling back to `updated_at` for `Done`) rather than the ledger
  stamps the other sections use, so the two can differ by a week for ~0.3% of
  tasks, and that a `Done`-but-unarchived task counts as departed.
- `skills/aitask-stats.md` — the numbered list of report sections.

`t1544_8` exists because two shape commitments are made under partial
information: flows-only storage with a render-time stock, and the 8-week default
horizon / parent+child denominator. It documents outcomes and files standalone
follow-ups only if the data justifies them.

**Sequencing:** `_1` must land before `_3`'s merge test is meaningful — without
it, "a multi-project run does not double-count" is untestable because the
discovery layer hands you the same repo twice.

Also, per `planning_conventions.md` §"Dead code goes into the sibling refactor
task": `_2` drops a one-line note into `aitasks/t1304_consolidate_lib_frontmatter_parsers.md`
under `## Notes for sibling tasks`, naming `stats_data.py:249-269` and the new
`split_frontmatter`, so t1304 collapses both.

### Post-phase (risk mitigations)

Carried verbatim into `t1544_1`'s child plan, where it executes.

1. `[tui_discovery_smoke_after_dedupe]` After the dedupe lands, launch `ait board`,
   `ait monitor`, `ait minimonitor` and the `j` TUI switcher, and confirm each
   still lists every session it listed before — same count, same names, same
   order. Record the before/after session lists in the child plan's Final
   Implementation Notes. Add the same four checks as items on the `t1544_7`
   manual-verification checklist. The unit test cannot reach the live discovery
   path in four other TUIs; only this can.

## Verification

```bash
bash tests/run_all_python_tests.sh --test-dir tests
./ait stats                                           # new sections render
./ait stats --backlog-weeks 26                        # long horizon
./ait stats --csv /tmp/tasks.csv --csv-backlog /tmp/backlog.csv
./ait stats-tui                                       # backlog preset, both panes
shellcheck .aitask-scripts/aitask_*.sh
```

Two reconciliation identities are the real proof. Both held exactly on the
confirming run, and both are asserted in `_check_backlog` on synthetic fixtures
rather than on the moving live corpus:

- **`TOTAL OPEN` at `Now` == live files − live-folded − live-departed −
  live-excluded** (confirmed: 414 == 420 − 5 − 1 − 0). Count live files with
  `iter_active_markdown_files`, **not** with a `-not -path '*metadata*'` find.
- **Σ departures over all history == `data.total_tasks` + live-departed**
  (confirmed: 1829 == 1828 + 1). This holds because every archived task resolves
  a date under *both* clocks — 0 ledger-only and 0 `completed_at`-less — so the
  two clocks differ on the week bucket but never on set membership. If that ever
  stops being true, `archived_no_completed_at` is the counter that says so.

Both were briefly off by one during planning purely because a concurrent session
archived a task mid-measurement — a reminder that these belong in fixture tests,
not in assertions against the live corpus.
- Existing sections byte-identical before/after (diff two `ait stats` runs,
  ignoring the `Generated:` line).
- `tests/test_collection_parity.py` enforces unittest-count == pytest-count per
  module and specifically flags the `def test_x(tmp)` fixture-arg trap: the
  `_check_backlog(tmp)` prefix is correct, and `tests/test_task_category.py` must
  expose only `TestCase` methods, no module-level `test_*(arg)` helper.

**Commit hygiene:** the working tree carries another session's in-flight changes
(`CLAUDE.md`, `aidocs/framework/manual_verification_staleness.md` from t1538), and
the live task corpus is being added to concurrently. Every commit in this family
must stage explicit paths — never `git add -A`. No file under `aitasks/` is
modified by this task, so no `./ait git` commit is needed beyond the normal
task/plan bookkeeping.

## Out of scope

- Backfilling or writing `followup_kind` onto any task file.
- Changing the existing 4-week tables, charts or panes.
- A `boardcol`-based definition of "backlog" (set on only ~59 live tasks).
- Consolidating the two `lib/` `parse_frontmatter` functions — that is t1304's
  benchmark-gated decision; this task must not pre-empt it.
- Honouring `stats_config`'s `week_start` / `days` keys in the TUI (t597_4).
- Widening the existing 4-week horizon anywhere.

## Risk

### Code-health risk: high

- `t1544_1` changes `_assemble_aitasks_sessions` in `lib/agent_launch_utils.py`, the
  shared session-discovery helper behind **every** aitasks TUI (board, monitor,
  minimonitor, switcher, stats) — not just stats. A dedupe that is even slightly
  wrong silently removes a session from every one of those surfaces. Residual
  after mitigation: likelihood reduced (the pre-phase pins current behaviour, the
  post-phase smokes the four live surfaces), blast radius unchanged · severity: high
  · → mitigation: inline pre-phase characterize_session_discovery, inline
  post-phase tui_discovery_smoke_after_dedupe
- `StatsData` has three lockstep edit sites (dataclass :139, `_empty_stats_data`
  :1136, `merge_stats_data` :1164) and a missed merge silently drops the new
  series in multi-project aggregation; `lib/stats_data.py` is a base layer
  consumed by the CLI, the TUI and `work_report_gather` · severity: medium
  · → mitigation: covered in scope (merge assertion in `_check_backlog`)
- `collect_stats` roughly doubles in cost, and the stats TUI collects
  synchronously once per discovered session on mount · severity: medium
  · → mitigation: covered in scope (`with_backlog` opt-out)
- The report will carry **two** completion clocks: the existing sections keep
  `resolve_completion_date`, the backlog sections use `completed_at` (the task's
  stated definition, user-approved). They never disagree on *whether* a task
  completed, only on which week for 6 of 1828 tasks (0.3%) · severity: low
  · → mitigation: covered in scope (footnote, `board-stats.md:78`, and a boundary
  test with a task whose two clocks straddle a week edge)
- No config file is modified, so the project-local preset override surface is
  preserved intact; an earlier draft that deleted the redundant JSON block was
  withdrawn · severity: low · → mitigation: covered in scope (precedence test)

### Goal-achievement risk: medium

- The TUI presentation is unproven at real cardinality — 17 categories × 9 week
  columns in a `DataTable` (the shared 8-week default helps, but the row count is
  the harder half), and a plotext chart capped at ~100 columns. The CLI shape was
  rendered against live data at exactly 80 chars; the TUI shape was not
  · severity: medium · → mitigation: covered in scope (`t1544_8` retrospective)
- The open-task population embeds three judgement calls — Postponed counted as
  open, parents *and* children counted, follow-up kinds removed from their
  `issue_type` so `bug` reads differently in two sections of one report. Each is
  documented and footnoted, but a wrong call makes the headline number misleading
  rather than wrong · severity: medium · → mitigation: covered in scope
  (footnotes, parent/child split, `t1544_8`)
- Requirement coverage and feasibility are **not** open risks: a working probe
  reproduced the task's prototype table over the full corpus, and every
  acceptance criterion maps to a named child · severity: low · → mitigation: none

### Planned mitigations

- timing: pre-phase | name: characterize_session_discovery | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — shared session-discovery helper feeds every TUI | desc: characterization test pinning `_assemble_aitasks_sessions`'s current non-duplicate output before the dedupe edit
- timing: post-phase | name: tui_discovery_smoke_after_dedupe | type: manual_verification | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — shared session-discovery helper feeds every TUI | desc: after the dedupe, smoke board / monitor / minimonitor / switcher session lists and carry the checks into t1544_7

Both dispositions are **inline**, deliberately. This parent decomposes, so the
workflow's spawn hooks never fire for it — Step 7 creates "before" tasks and
Step 8d creates "after" tasks, and a decomposed parent reaches neither. Inline
phases land in `t1544_1`'s child plan, which is authored at decomposition time.

**Post-inline reassessment (one pass):** the two phases reduce the *likelihood*
of a session-discovery regression but not its *blast radius* — the helper still
feeds five TUIs — so the code-health level stays **high**. Goal-achievement is
unchanged at **medium** (the mitigations do not touch the TUI-cardinality or
population-definition risks). No new risks were introduced by the inline phases.
