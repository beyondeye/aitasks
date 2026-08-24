---
Task: t1544_5_stats_tui_backlog_panes.md
Parent Task: aitasks/t1544_stats_backlog_and_net_flow_by_category.md
Sibling Tasks: aitasks/t1544/t1544_6_backlog_stats_documentation.md, aitasks/t1544/t1544_7_manual_verification_stats_backlog.md, aitasks/t1544/t1544_8_backlog_stats_retrospective.md
Archived Sibling Plans: aiplans/archived/p1544/p1544_1_session_discovery_dedupe.md, aiplans/archived/p1544/p1544_2_task_category_axis_module.md, aiplans/archived/p1544/p1544_3_backlog_flow_collection.md, aiplans/archived/p1544/p1544_4_cli_backlog_sections_and_csv.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-24 17:16
---

# p1544_5 — Stats TUI backlog panes

## Context

t1544 adds a **backlog level** (open tasks per category per week) and a **net
flow** (arrivals vs departures per week) series to `ait stats`. t1544_3 landed
the data layer; t1544_4 landed the CLI text/CSV surface. This task is the third
and last rendering consumer: the same two series exposed in the **stats TUI** as
registered panes reachable from a preset.

Parent AC: *"The stats TUI exposes the same information as registered pane(s),
reachable from a preset"* — and the net-flow surface must be **split by the
unified category axis**, not a totals chart.

This plan was re-verified against the current tree (t1544_4 landed 2026-08-24 as
`dc69a2b26`). Verification findings are recorded below; the substance of the
original plan stands, with four corrections.

---

## Verification findings (this re-verification pass)

**Confirmed unchanged and still accurate:**

- `stats/panes/__init__.py:9` eager-import line is verbatim what the plan quotes:
  `from . import overview, labels, agents, velocity, sessions, pipeline`.
- `base.py`: `PaneDef(id, title, category, render)`; `render(StatsData, Container) -> None`
  mounts into the container; `render_chart(setup_fn, container, width=100, height=22)`.
- `sessions.py` (38 lines) and `labels.py::_render_heatmap` are the templates.
- `stats_data.BACKLOG_WEEKS_DEFAULT = 8` (`stats_data.py:61`) — its docstring
  **already names this pane** as the second consumer.
- The `t597_4` week-start TODO is `overview.py:13`.
- `stats_app.py` passes `week_start_dow` positionally as the literal `1` at both
  `collect_stats` call sites (`:322`, `:356`) and never reads `stats_config`'s
  `week_start`. A pane receives only `(StatsData, Container)` — no config.
- **Deliverable 3's premise holds.** `deep_merge` (`config_utils.py:101-118`)
  merges dicts per key and replaces lists. `presets` is a dict, so a *new* key in
  `DEFAULT_PRESETS` survives the JSON layer by mechanism — `sessions` is the live
  proof. **No config file needs changing.**

**Corrections / additions the original plan did not carry:**

1. **`collect_stats(..., with_backlog=True)` is the default** — the TUI gets the
   backlog counters for free. No wiring change needed. (Worth stating: the plan
   was silent, which reads as an open question.)

2. **The `excluded=` clamp sink must be a per-render scratch `Counter`.**
   t1544_3's recorded contract says *"Pass `data.backlog_excluded` as `excluded`
   to keep the clamp counter live"* — correct for a one-shot CLI, **actively
   wrong here**. `stats_app._show_pane` (`:423-429`) re-renders against the
   **same cached `self.stats_data`** on every pane switch, so passing the shared
   counter would increment `negative_level` without bound for the session.
   `aitask_stats.BacklogAxis`'s own docstring makes the same point about
   per-section calls. **Never pass `stats.backlog_excluded`.**

3. **The two tables use different membership *and* different ordering rules.**
   The plan mentioned neither.
   - level: members are `any(levels[(c,o)] for o in offsets)`; sort
     `(-levels[(c,0)], category_display_name(c))`, then partitioned
     follow-ups / genuine (`aitask_stats.py:357`).
   - netflow: members are `any(arrivals or departures)`; sort
     `(not is_followup_category(c), -levels[(c,0)], category_display_name(c))`
     (`aitask_stats.py:497`).
   `kind:docs_gap` is the live discriminating case — real flow, zero level. Using
   the level rule for netflow would drop it; t1544_4 pinned that with a negative
   control.

4. **`TOTAL OPEN` must come from an independent all-tasks axis.** This matters
   *more* here than in the CLI, because this pane **caps rows**. Summing the
   visible rows would make `TOTAL OPEN` wrong by construction. The re-key must
   **accumulate** (`agg[("all", off)] += n`) — a dict comprehension keeps only the
   last category per offset, which t1544_4 pinned with a negative control.

5. **The exclusion / clamp diagnostics are part of "the same information".** The
   original plan omitted them entirely. The CLI prints them on the **populated**
   path (`:453`) *and* the **empty** path (`:419`), and its docstring
   (`:386-392`) states why: on the empty path the tally *"is not a footnote of a
   table — it is the explanation for the table's absence"*, and `main()`'s
   `has_backlog` predicate (`:874`) admits an all-excluded repo **precisely
   because those counters are non-empty**. A TUI that renders a generic "No data"
   there would report nothing where the CLI reports a data-quality problem. The
   CLI also splits the empty message two ways (`:415-418`).

**Boundary:** `_build_backlog_axis`, `_aggregate_all` and `BACKLOG_TASK_EXCLUSION_REASONS`
are private to `aitask_stats.py`, absent from its `__all__`, and **nothing in the
tree imports `aitask_stats`**. The pane must re-derive, not import — inverting the
layering would be the first pane→CLI import. This duplication is deliberate and
already owned by **t1586**, which is gated on this task landing precisely so the
seam is designed against a real second consumer. Finding 5 adds
`BACKLOG_TASK_EXCLUSION_REASONS` to that duplicated set, which is *good* for
t1586: that constant is one of the three items it names, and it now has the second
consumer it needs to be extracted against rather than guessed at.

---

## Implementation steps

### 1. `.aitask-scripts/stats/panes/backlog.py` (new)

Shape follows `sessions.py`. Imports come from `lib/` only:

```python
from stats_data import (BACKLOG_WEEKS_DEFAULT, StatsData, backlog_levels,
                        backlog_week_offsets, build_chart_title)
from task_category import category_display_name, is_followup_category
from .base import PaneDef, empty_state, register, render_chart
```

**Testability-first split.** Row derivation is **pure** (no Textual), and the two
`_render_*` functions are thin mounting shells over it. This is what makes the
invariants below unit-testable without booting an app — and is exactly the seam
t1586 will lift into `lib/backlog_view.py`.

```python
_LEVEL_ROW_CAP   = 6   # per block (follow-ups / genuine); the Other row counts toward it
_NETFLOW_SERIES  = 5   # chart series: top-4 categories + Other

# The seven reasons that count TASKS. `negative_level` is deliberately absent:
# it counts clamped OUTPUT CELLS and must never be summed into a task total.
# Re-declared from aitask_stats.py (private there); t1586 lifts both.
_TASK_EXCLUSION_REASONS = (...)

def _aggregate_all(flow: Counter) -> Counter: ...
def _derive_levels(stats, offsets) -> tuple[Counter, Counter, Counter, int]: ...
def _diagnostic_lines(stats, clamped_cells: int) -> list[str]: ...
def _level_rows(stats, weeks: int = BACKLOG_WEEKS_DEFAULT) -> tuple[list[str], list[tuple[str, list[str]]], list[str]]: ...
def _netflow_rows(stats, weeks: int = BACKLOG_WEEKS_DEFAULT) -> tuple[list[str], list[tuple[str, list[str]]], list[str], list[list[int]]]: ...
```

`_derive_levels` allocates its **own scratch `Counter`** for `excluded=` (finding 2)
and returns `(levels, scope_levels, total_levels, clamped_cells)`, the third from
`_aggregate_all` (finding 4). `_aggregate_all` carries the
accumulate-not-comprehend comment.

**The scratch counter is returned, not discarded.** `_derive_levels` reads
`clamps["negative_level"]` out before dropping the counter. Allocating a private
sink and then throwing it away is the exact defect `aitask_stats.py:386-392`'s
docstring names — *"Dropping it there would capture the diagnostic without
surfacing it."*

`_diagnostic_lines` mirrors `aitask_stats.py::_render_backlog_exclusions` (:385):
one line summing the seven **task** reasons with their per-reason detail, and a
separate line for clamped **cells**, never summed into the task total. It returns
`[]` when both are empty.

### 2. `backlog.level` — `DataTable(zebra_stripes=True)`

Mirrors `labels.py::_render_heatmap`. Columns `["Category", "Now", "W-7" … "W-1"]`
(`columns = [0] + [o for o in offsets if o != 0]`, matching the CLI).

Rows, per block (`followup_rows` then `genuine_rows`):
- top `_LEVEL_ROW_CAP - 1` categories by the level sort rule;
- an `Other` row summing the remainder **only if non-zero** (the `chart_totals`
  idiom at `stats_data.py:1055` — adapted, not reused: `chart_totals` collapses
  weeks into one total and cannot produce a per-week series);
- the block subtotal (`-- follow-ups` / `-- genuine`) summed over the **whole**
  block, so `shown + Other == subtotal` is an invariant;
- an empty block emits **no** subtotal row (t1544_4's recorded deviation).

Then `TOTAL OPEN` (from `total_levels`), `of which parents`, `of which children`
(from `scope_levels`).

**Diagnostics on BOTH paths** — mirroring `_render_backlog_exclusions`, which the
CLI calls on the populated path (`:453`) *and* the empty path (`:419`):

- **Populated:** mount the `DataTable`, then a `Static` carrying
  `_diagnostic_lines(...)` beneath it. Omit the `Static` entirely when the list is
  empty — never mount a blank one.
- **Empty (no rows):** do **not** fall through to the generic `empty_state`.
  Reproduce the CLI's two-branch message (`:415-418`): if any of the seven task
  reasons is non-zero, *"No open tasks could be placed in the backlog series."*;
  otherwise *"No open tasks found."* Follow it with the same
  `_diagnostic_lines(...)` `Static`. On this path the tally is not a footnote — it
  is the **explanation for the table's absence**, and it is what makes the TUI
  report a data-quality problem instead of a generic "no data" while the CLI
  explains itself.

Build these with `Static(Text(...))` or `markup=False`. Reason names are
bracket-free today, but `Static` has `markup=True` by default and silently eats
any bracketed run.

### 3. `backlog.netflow` — totals strip + per-category chart

Two widgets mounted into the container (precedent: `overview._render_summary`
mounts a `Horizontal`; `agents.VerifiedRankingsPane` is a composite `Vertical`).

- **Totals strip** — a plain `Static` (4 lines: header + `ARRIVALS` / `DEPARTURES` /
  `NET`), summed over the flow-bearing categories exactly as the CLI does
  (`aitask_stats.py:507-513`). Plain text, no Rich markup.
- **Chart** — `multiple_bar(week_labels, [net_per_category…], labels=[…])` with the
  `hasattr(plt, "multiple_bar")` fallback from `velocity.py:74-78`.

  **Series selection is by horizon volume, not by net.** Rank on
  `(-volume, category_display_name(c))` where

  ```python
  volume = sum(arrivals.get((c, o), 0) + departures.get((c, o), 0) for o in offsets)
  ```

  Ranking on net — or on `|net|` — would hide exactly the category this pane exists
  to show: one with many arrivals and equally many departures nets to ~0 while
  being among the most active in the horizon. That is the live `kind:docs_gap`
  shape (3 arrivals, 3 departures, level 0 everywhere) and the same case finding 3
  covers on the membership axis; volume ranks it fairly, net buries it in `Other`.

  The `category_display_name` tie-break is not optional: the CLI's own comment at
  `aitask_stats.py:358-359` records that sorting a `Counter` keyset on the numeric
  key alone is insertion-order dependent, which makes the output non-deterministic.

  Keep the top `_NETFLOW_SERIES - 1`; `Other` is the per-week **net** summed over
  the remainder, appended only if any of its values is non-zero (the `chart_totals`
  idiom).

Columns are the CLI's netflow order — `[o for o in offsets if o != 0] + [0]`, i.e.
`W-7 … W-1`, `Now*` last — and membership is the **flow** rule (finding 3).

**Height budget:** `#content` is a plain `Container` (`stats_app.py:159-163`) with
`padding: 1 2` and **no scrollbar**, so the pane must fit. Pass an explicit
`render_chart(setup, container, height=18)`; strip (4) + chart (18) + padding (2)
= 24 rows. Verified legible at 8 weeks × 5 series during planning against live
values.

Empty state when there is no flow in the horizon.

### 4. Week start — comment, no constant

Week start stays Monday. Add a comment at the top of the module stating so and
pointing at `overview.py:13`'s `t597_4` TODO, with the two reasons: `stats_app.py`
hardcodes `1` at both `collect_stats` call sites, and `resolve_week_start` lives in
the CLI rather than `lib/`. Do **not** declare an unused `_WEEK_START_DOW` — the
pane computes no dates, so a constant would be dead code.

### 5. Registration + the import trap

```python
register(PaneDef("backlog.level", "Backlog level", "Backlog", _render_level))
register(PaneDef("backlog.netflow", "Net flow", "Backlog", _render_netflow))
```

**Append** `backlog` to the eager-import list in `stats/panes/__init__.py:9`.
Append rather than insert: the list order determines `PANE_DEFS` iteration order,
which the pane-selector modal uses to group by category, so inserting would
reorder existing groups. A wrong entry here is a `ModuleNotFoundError` that stops
the **whole TUI** from starting (sibling risk task t1305).

### 6. Preset

Add `"backlog": ["backlog.level", "backlog.netflow"],` to
`stats/stats_config.py::DEFAULT_PRESETS`.

**Change no config file.** Do not edit `aitasks/metadata/stats_config.json`, and
do not delete its redundant `presets` block — it holds no overrides *in this
checkout*, which proves it redundant **here**, not that a project-local layout
override is never real elsewhere.

### 7. Tests — `tests/test_stats_backlog_panes.py` (new)

Plain `unittest.TestCase` methods only (`tests/test_collection_parity.py` enforces
unittest-count == pytest-count per module). Synthetic `StatsData` fixtures; the
pure row functions need no Textual app.

1. `test_backlog_panes_are_registered` — import `stats.panes`; assert both ids in
   `PANE_DEFS`. **The import-trap guard.**
2. `test_backlog_preset_is_in_the_effective_config` — `stats_config.load()["presets"]["backlog"]`
   equals both ids. Asserts the **effective** config, never literal-vs-literal.
3. `test_a_json_preset_list_replaces_the_code_list` — a temp project JSON pinning
   `presets.overview` to one pane, loaded through `load_layered_config(tmp, local_path=<absent>,
   defaults=stats_config.DEFAULTS)` (the exact seam `load()` uses, without chdir or
   leaking the developer's real `stats_config.local.json`). Asserts the JSON list
   **replaces** the code list. **Pins current behaviour; does not change it.**
4. `test_backlog_survives_an_existing_json_presets_block` — same fixture; `backlog`
   still present. Adding the pane cannot discard a user's overrides.
5. `test_pane_horizon_tracks_the_shared_constant` — `_level_rows` / `_netflow_rows`
   default `weeks` equals `stats_data.BACKLOG_WEEKS_DEFAULT`. **States its limit in
   a comment:** this is a *drift* guard, not an origin guard — it cannot tell a
   read of the constant from a hardcoded `8` today, but it goes red the day the
   constant changes, which is the drift the task is guarding against.
6. `test_rendering_does_not_mutate_the_shared_exclusion_counter` — derive twice
   from one `StatsData`; assert `backlog_excluded` is byte-equal to its initial
   value. **Guards finding 2.**
7. `test_zero_level_category_with_flow_is_a_netflow_row` — a category with equal
   arrivals and departures in one week (level 0 everywhere) appears in netflow and
   **not** in level. **The `kind:docs_gap` case; guards finding 3.**
8. `test_total_open_is_independent_of_the_row_cap` — more categories than
   `_LEVEL_ROW_CAP`; `TOTAL OPEN` equals `parents + children` and equals the true
   corpus total. **Guards finding 4 plus the cap interaction.**
9. `test_other_row_and_shown_rows_reconcile_with_the_block_subtotal` — per column,
   for both blocks.
10. `test_diagnostics_are_surfaced_on_the_populated_path` — a fixture with rows and
    a non-zero `no_frontmatter` / `folded` tally; assert `_level_rows`' third
    element names both reasons and their counts.
11. `test_diagnostics_explain_an_empty_level_table` — a fixture with **only**
    exclusions and no placeable task; assert the empty message is the
    *"could not be placed"* branch, not *"No open tasks found."*, and that the
    tally accompanies it. **The `has_backlog` case the CLI admits on the strength
    of these counters alone.**
12. `test_clamped_cells_are_reported_separately_from_the_task_tally` — a fixture
    whose departures exceed its arrivals (forcing `negative_level`); assert the
    clamp count is surfaced on its own line and is **not** added into the task
    total. **Guards the cells-vs-tasks confusion t1544_3 recorded.**
13. `test_netflow_series_are_ranked_by_horizon_volume` — an over-cap fixture
    containing a high-volume / zero-net category; assert the **exact** chosen
    category list (order included) and the **exact** `Other` per-week series.
    Pinning both is what makes the assertion fail on a net-based ranking, on a
    missing tie-break, and on a mis-bucketed `Other` — a membership-only check
    passes all three.

### Post-phase (risk mitigations)

Both run after step 7, as part of this task.

1. **[pin_cli_tui_backlog_parity]** Add a cross-surface parity test to
   `tests/test_stats_backlog_panes.py`. Build **one** synthetic `StatsData`; render
   it through `aitask_stats.render_backlog_level` / `render_backlog_netflow` (they
   write markdown to an `io.StringIO`) and through the pane's `_level_rows` /
   `_netflow_rows`; parse the CLI's pipe table and assert the two surfaces carry
   **identical numbers** for every shared row.

   Assert **surface against surface**, never surface against a third probe. Use a
   fixture with fewer categories than `_LEVEL_ROW_CAP` so the row sets are directly
   comparable, plus one over-cap fixture where parity is asserted on the
   `TOTAL OPEN` / `of which parents` / `of which children` / `ARRIVALS` /
   `DEPARTURES` / `NET` rows — those must match regardless of capping, and that is
   precisely the invariant the cap could break.

   Negative control: invert the netflow `net` sign in the pane and confirm this
   test reddens.

2. **[smoke_render_backlog_panes_live]** Add a live-render smoke test that boots
   the stats TUI under `App.run_test(size=(120, 40))` — an explicit target
   terminal size, since every geometry assertion below is meaningless without one
   — applies the `backlog` layout, and asserts:

   - `backlog.level` mounts exactly one `DataTable`, with the expected column
     count and a non-zero row count;
   - `backlog.netflow` mounts exactly **two** children — the strip `Static` and the
     chart `Static`;
   - **the chart Static is a real chart, not the fallback.** `render_chart`
     (`base.py:51-55`) mounts a `Static` and returns early when `plotext` is
     missing, so the success and failure paths are **both** "one `Static`" and a
     type-only assertion cannot tell them apart. Assert the rendered text does
     **not** equal the `plotext not installed` fallback and **does** contain the
     chart title plus at least one bar glyph;
   - **the 24-row budget actually fits.** `#content` has no scrollbar, so assert
     both children's regions lie inside `#content`'s region — bottom edge included.
     A type assertion says nothing about clipping.

   This is the only check that exercises the **real mount path** — `DataTable.add_columns`
   on a mounted widget, and the composite mount into a non-scrolling `#content`.
   Everything else in step 7 tests pure functions or a bare package import.

   It does **not** replace the manual readability check in `## Verification`: the
   test proves the widgets exist, are non-fallback and are unclipped; whether the
   bars are *legible* still needs a human at a real terminal.

   **It joins the serial carve-out.** Per `CLAUDE.md`, live-TUI modules are excluded
   from the parallel lane because a loaded worker pool turns their boot budget into
   a flake. Add the new module to the carve-out list in
   `tests/run_all_python_tests.sh` alongside `test_board_startup_focus_live.py` and
   `test_codebrowser_startup_focus_live.py`, and give it its own synthetic project
   rather than the real repo (only `test_board_header_row_live.py` uses the real
   repo, and it takes `.git/index.lock`).

   Note `App.run_test` misses startup focus on some drivers and a `@work` worker
   still in flight at block exit fails the *enclosing* test — see
   `aidocs/framework/testing_conventions.md`. Assert on mounted widget types, not
   on focus.

---

## Verification

```bash
bash tests/run_all_python_tests.sh --test-dir tests   # read the LAST line only
~/.aitask/venv/bin/python -m pyflakes .aitask-scripts/stats/panes/backlog.py
```

`bash tests/run_all_python_tests.sh` piped discards the status — use
`${PIPESTATUS[0]}` or `set -o pipefail`.

Manual (also seeded on t1544_7's checklist):

- `ait stats-tui` **starts at all** — the import trap.
- The `backlog` layout appears in the layout picker; both panes appear in the sidebar.
- Each pane renders real data, not its empty state.
- The level `DataTable` is readable at a normal terminal width and its row cap
  engages on the real corpus (17 categories today).
- The netflow pane visibly carries the **category** dimension, and the strip +
  chart both fit without clipping.
- The level pane's diagnostic line matches the CLI's `_Excluded from the backlog
  series: …_` footnote for the same corpus (today: 8 tasks — `no_frontmatter: 3`,
  `folded: 5`). Diagnostics belong to the **level** pane only; the CLI's net-flow
  section prints none.
- The other five presets still list their original panes and still render.
- The TUI's backlog numbers match `ait stats` for the same week and horizon.

Negative controls (each re-run with `__pycache__` cleared — t1544_3 recorded a
verification defect where a same-second, same-size restore left a stale `.pyc`):

| mutation | must redden |
|---|---|
| `_aggregate_all` uses a dict comprehension | `test_total_open_is_independent_of_the_row_cap` |
| netflow reuses the level membership rule | `test_zero_level_category_with_flow_is_a_netflow_row` |
| `_derive_levels` passes `stats.backlog_excluded` as `excluded=` | `test_rendering_does_not_mutate_the_shared_exclusion_counter` |
| `backlog` removed from the `__init__.py` import list | `test_backlog_panes_are_registered` |
| block subtotal summed over shown rows instead of the whole block | `test_other_row_and_shown_rows_reconcile_with_the_block_subtotal` |
| netflow `net` sign inverted | `pin_cli_tui_backlog_parity` |
| empty level path falls through to the generic `empty_state` | `test_diagnostics_explain_an_empty_level_table` |
| `negative_level` summed into the task exclusion total | `test_clamped_cells_are_reported_separately_from_the_task_tally` |
| netflow series ranked by net instead of arrivals + departures | `test_netflow_series_are_ranked_by_horizon_volume` |
| `plotext` import forced to fail | `smoke_render_backlog_panes_live` (chart-content assertion) |

---

## Post-Review Changes

### Change Request 1 (2026-08-24 18:28)

- **Requested by user:** Move the `Now` column in the backlog **level** pane from
  first to last (after `W-1`), matching the change they had just landed in the
  CLI as **t1588**. A peer session (the t1544_4 CLI author) independently sent
  the same notice, reporting that t1588 had broken this task's in-flight parity
  test.
- **Confirmed before changing:** the two `TestCliParity` tests failed on header
  order alone — `['Now','W-7'…'W-1'] != ['W-7'…'W-1','Now']`. The parity test
  detected the upstream reorder immediately, which is what it was added for.
- **Changes made:**
  - Added `_columns(offsets, now_label)` to `stats/panes/backlog.py`, mirroring
    t1588's `aitask_stats._backlog_columns` — same signature and body, same
    `now_label` split (`Now` for the level, a stock correct as-of-now; `Now*` for
    the flow, where a partial week is genuinely incomplete).
  - Both `_level_rows` and `_netflow_rows` now call it, so the two panes cannot
    drift into different column orders. The flow pane's output is unchanged (it
    already ended in `Now*`); only the level pane reorders.
  - **Not** imported from `aitask_stats`: nothing in the tree imports that module,
    and a pane→CLI import would invert the layering. An identical local shape
    keeps t1586 a straight lift of both copies into `lib/backlog_view.py`.
  - Corrected `_level_rows`' docstring, which still claimed "`Now` first then the
    horizon weeks oldest-first, matching the CLI" — wrong in both directions
    after t1588.
  - Added a negative control (`level columns put Now FIRST again`) pinning the
    order; it reddens both parity tests and nothing else.
- **Files affected:** `.aitask-scripts/stats/panes/backlog.py`
- **Re-verified:** full suite `PYTHON SUITE: PASSED (runner=pytest, exit=0)` —
  5193 passed, 2 skipped; 13/13 negative controls redden their named assertion;
  pyflakes clean; live tmux boot shows the level table ending in `Now` and
  matching `ait stats` row-for-row.

## Risk

*Levels reassessed against the augmented plan, after both mitigations were
confirmed as inline post-phases.*

### Code-health risk: medium

- ~120 lines of axis / ordering / subtotal logic re-derived from
  `aitask_stats.py`, whose versions are underscore-private and outside `__all__`,
  so they cannot be imported without inverting the CLI/TUI layering. · severity: low · → mitigation: t1586
- The `excluded=` clamp sink is a live foot-gun that t1544_3's own recorded
  contract points the wrong way on: the TUI re-renders against one cached
  `StatsData`, so the sibling's advice would corrupt a counter for the session. · severity: medium · → mitigation: covered in-plan (step 7, test 6)
- The eager-import list is a `ModuleNotFoundError` trap that takes down the whole
  TUI, not just this pane. · severity: medium · → mitigation: inline post-phase smoke_render_backlog_panes_live
- The live-render smoke test joins the serial carve-out in
  `tests/run_all_python_tests.sh`, adding to a budget that is explicitly kept small
  because a loaded worker pool turns a boot budget into a flake. · severity: low · → mitigation: inline post-phase smoke_render_backlog_panes_live

### Goal-achievement risk: low

- "Same information as the CLI" is asserted only by eye. The unit tests check the
  pane against its own fixtures, not against the CLI's rendering of the same
  `StatsData` — two surfaces that could drift silently. · severity: medium · → mitigation: inline post-phase pin_cli_tui_backlog_parity
- Netflow chart legibility at 8 weeks × 5 series and the strip+chart height fit in
  a non-scrolling `#content`. Both were checked empirically during planning
  against live values. · severity: low · → mitigation: covered in-plan (step 3, height budget)

### Planned mitigations
- timing: post-phase | name: pin_cli_tui_backlog_parity | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — CLI/TUI parity asserted only by eye | desc: Assert the pane's derived rows against the CLI's rendered backlog tables from one shared StatsData.
- timing: post-phase | name: smoke_render_backlog_panes_live | type: test | priority: medium | effort: medium | inline_risk: low | added_complexity: medium | addresses: code-health — eager-import trap and the never-exercised real mount path | desc: Boot the stats TUI under App.run_test, apply the backlog layout, assert both panes mount their widgets; add the module to the serial carve-out.

---

## Final Implementation Notes

- **Actual work done:** All seven implementation steps plus both inline
  post-phase mitigations, as planned. New `.aitask-scripts/stats/panes/backlog.py`
  (~310 lines): `_columns`, `_aggregate_all`, `_derive_levels`,
  `_diagnostic_lines`, `_cap_block`, the two pure row functions
  (`_level_rows` / `_netflow_rows`), `_totals_strip`, the two `_render_*` shells,
  and both `register()` calls. `stats/panes/__init__.py` gained `backlog` at the
  end of the eager-import list; `stats/stats_config.py` gained the `backlog`
  preset. **No config file was changed**, as Deliverable 3 requires. New
  `tests/test_stats_backlog_panes.py` (25 tests) and
  `tests/test_stats_backlog_panes_live.py` (9 tests).

- **Deviations from plan:** Four, three of which are corrections to plan steps
  that could not have worked as written.

  1. **The live-render module is NOT in `SERIAL_CARVE_OUT`.** The plan said to add
     it and to edit CLAUDE.md's marker block. Verified instead that the carve-out
     exists for modules booting a real TUI **in a tmux pane** under a hard
     wall-clock budget; this module uses `App.run_test` (headless, in-process),
     and **93 existing modules** already do so inside the parallel pool. Adding it
     would have grown a deliberately-small carve-out for no reason and forced an
     unnecessary CLAUDE.md edit plus the `test_serial_carveout_doc_drift.sh`
     coupling.
  2. **The `#content` fit assertion is wanted-lines vs available-rows, not
     region vs region.** The planned region comparison is **structurally incapable
     of failing**: Textual clips a child's `region` to its parent, so an
     overflowing widget reports a clipped height. Caught by its own negative
     control, which passed while the mutation was live. (Also learned: plotext
     clamps its own output to the terminal, so `_NETFLOW_CHART_H` can never
     overflow by itself — the discriminating mutation is a taller *strip*.)
  3. **The pane-registration test runs in a subprocess.** In-process it was
     vacuous: this test module imports `stats.panes.backlog` directly for the row
     functions, and that import alone runs `register()`, so `PANE_DEFS` contained
     both ids even with `backlog` removed from the eager-import list — blind to
     the exact trap it exists to guard. Also caught by its negative control.
  4. **Two extra live tests for `_render_level`'s empty branch.** The planned
     pure-function test asserts on `_level_rows`' return value, which stays
     correct even when the render path throws the message away; deleting the
     empty-path message left the suite green.

- **Issues encountered:**
  - **Upstream reorder mid-review (t1588).** After implementation was complete,
    the user asked to move the level pane's `Now` column last, and the t1544_4
    session independently reported that t1588 had already landed the same change
    in the CLI. The parity test failed on header order immediately — see
    Post-Review Changes above. Resolved by mirroring t1588's `_backlog_columns`
    as a local `_columns`, used by both panes.
  - Three of eleven initial negative controls were **vacuous** (nothing failed).
    Each exposed a real test defect, listed under Deviations 2-4. Re-running the
    controls after each fix is what turned them into guards rather than decoration.
  - A test bug of my own: the CLI-footnote parity assertion stripped `_` globally
    to remove markdown italics, which also mangled `no_frontmatter`. Fixed to
    assert the exact wrapped line.
  - Manual TUI verification persisted `active: backlog` into the gitignored
    `aitasks/metadata/stats_config.local.json`; restored to `labels`.

- **Key decisions:**
  - **The `excluded=` clamp sink is a per-render scratch `Counter`, never
    `stats.backlog_excluded`.** t1544_3's recorded contract says to pass the
    shared counter "to keep the clamp counter live" — correct for a one-shot CLI,
    **wrong for a TUI**: `stats_app._show_pane` re-renders against the same cached
    `StatsData` on every pane switch, so the shared counter would accumulate
    `negative_level` without bound for the session. The scratch counter is read
    out and returned, not dropped — allocating a sink and discarding it is
    capturing a diagnostic without surfacing it.
  - **Diagnostics render on BOTH the populated and the empty path**, with the
    CLI's two-branch empty message. On the empty path the tally is the
    *explanation for the table's absence*, not a footnote — `main()`'s
    `has_backlog` predicate admits an all-excluded repo precisely on the strength
    of those counters. The original plan omitted this entirely; it was added
    after review feedback.
  - **Net-flow chart series rank by horizon VOLUME (arrivals + departures), not
    net.** A category with many arrivals and equally many departures nets to ~0
    while being among the most active — ranking on net buries exactly the
    category this pane exists to show. That is the live `kind:docs_gap` shape.
  - **Row derivation is pure and Textual-free**, with the `_render_*` functions as
    thin mounting shells. This is what makes the invariants unit-testable without
    an app, and it is the seam t1586 lifts.
  - **`TOTAL OPEN` comes from the independent all-tasks axis**, which matters more
    here than in the CLI because this pane caps rows: the total cannot be
    recovered by summing what is on screen.
  - **Per-block row cap with a per-block `Other`**, so `shown + Other == subtotal`
    holds per column and the capped table stays reconcilable.

- **Upstream defects identified:** None.

- **Notes for sibling tasks:**

  **For t1586 (`extract_backlog_view_helper`) — this task is its second consumer.**
  The duplication is now concrete and enumerable. `stats/panes/backlog.py` carries
  local mirrors of four things private to `aitask_stats.py`: `_columns` /
  `_backlog_columns` (t1588), `_aggregate_all`, the level and flow ordering +
  membership rules, and `BACKLOG_TASK_EXCLUSION_REASONS`. Both copies were
  deliberately kept **shape-identical** so the extraction is a straight lift
  rather than a reconciliation of two designs. Two things the extraction must
  decide rather than inherit:
  1. **Clamp-sink ownership.** The CLI wants a per-section scratch counter for
     idempotency; the TUI wants a per-render one because it re-renders against a
     cached `StatsData`. A lifted helper should own the scratch counter and return
     the clamp count, never accept a caller-supplied shared sink — otherwise every
     consumer re-decides it and the TUI's answer is the non-obvious one.
  2. **The row cap is a TUI concern, not a shared one.** The CLI never caps. Lift
     the ordering and membership rules; leave `_cap_block` behind.

  **For t1544_6 (documentation):** the TUI surface is the `backlog` preset with
  panes `backlog.level` ("Backlog level") and `backlog.netflow` ("Net flow"). The
  level pane caps each block at 6 rows with an `Other` bucket — a difference from
  the CLI worth documenting, since `Other` has no CLI counterpart. Both panes read
  `BACKLOG_WEEKS_DEFAULT`; the horizon is not configurable from the TUI (no CLI
  `--backlog-weeks` equivalent), and week start is fixed to Monday.

  **For t1544_7 (manual verification):** the checklist items in this plan's
  `## Verification` "Manual" block were all executed and passed during this
  session against a live tmux boot at 150x45.

### Verification results

- `tests/test_stats_backlog_panes.py` 25/25; `tests/test_stats_backlog_panes_live.py`
  9/9, under **both** backends (pytest and the `unittest discover` fallback).
- `bash tests/run_all_python_tests.sh --test-dir tests` ->
  `PYTHON SUITE: PASSED (runner=pytest, exit=0)`; 5193 passed, 2 skipped.
- `pyflakes` clean on all three new/changed Python files. (`stats/panes/__init__.py`
  reports its side-effect imports as unused — pre-existing, verified against
  `HEAD`; pyflakes does not honour the `# noqa: F401`.)
- **Live in a tmux pane (150x45):** `ait stats-tui` starts; the `backlog` layout
  appears in the picker and applies; both panes appear in the sidebar; the level
  table renders 9 columns ending in `Now` with the cap engaged (`Other 27`) and
  `TOTAL OPEN 438 = 312 + 126`; the diagnostic line matches the CLI footnote
  verbatim; the net-flow pane shows the totals strip over a 5-series category
  chart, unwrapped and unclipped. All six pre-existing presets still list their
  original panes.
- **13 negative controls**, each re-run with `__pycache__` cleared, each reddening
  its named assertion and no unrelated one:

  | mutation | discriminating assertion |
  |---|---|
  | level columns put `Now` first again (pre-t1588) | both `TestCliParity` level tests |
  | `_aggregate_all` uses a dict comprehension | `test_total_open_is_independent_of_the_row_cap` |
  | netflow reuses the LEVEL membership rule | `test_zero_level_category_with_flow_is_a_netflow_row` |
  | `_derive_levels` passes the shared exclusion counter | `test_rendering_does_not_mutate_the_shared_exclusion_counter` |
  | `backlog` dropped from the eager-import list | `test_backlog_panes_are_registered` |
  | block subtotal summed over shown rows only | `test_other_row_and_shown_rows_reconcile_with_the_block_subtotal` |
  | netflow `net` sign inverted | `test_netflow_totals_and_per_category_nets_match_the_cli` |
  | empty level path falls through to a generic message | `test_empty_level_pane_explains_itself_rather_than_saying_no_data` |
  | `negative_level` summed into the task tally | `test_clamped_cells_are_reported_separately_from_the_task_tally` |
  | netflow series ranked by net instead of volume | `test_netflow_series_are_ranked_by_horizon_volume` |
  | `plotext` import forced to fail | `test_netflow_chart_is_a_real_chart_not_the_fallback` |
  | totals strip blown past the `#content` budget | `test_netflow_fits_the_content_budget` |
  | level diagnostics dropped from the render path | `test_level_pane_mounts_its_diagnostic_line` |

  The `plotext`-failure and strip-overflow controls are the two that matter most:
  the first is the only thing separating a real chart from `render_chart`'s
  silent fallback, and the second is the only thing that makes the height budget
  a real constraint rather than a comment.
