---
priority: medium
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [reporting, tui, backlog, metrics]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5
created_at: 2026-08-17 17:36
updated_at: 2026-08-17 22:02
---

## Goal

Add a **backlog** dimension to `ait stats` (CLI + TUI): a weekly time series of
*open* tasks split by category, plus the **net flow** (arrivals vs departures per
week) that explains why the backlog moves. The purpose is operational — decide
whether a consolidation push is needed to bring the backlog back under control.

Today `ait stats` answers only "how much did we complete?". It cannot answer
"how much is outstanding, of what kind, and is it growing faster than we burn
it down?".

## Motivation (measured, not hypothetical)

A prototype run over the real corpus during exploration:

```
week_end   | open | mv | risk | upstr | genuine
2026-07-20 |  201 | 24 |   12 |     4 |     155
2026-07-27 |  257 | 38 |   24 |    11 |     178
2026-08-03 |  339 | 46 |   44 |    27 |     212
2026-08-10 |  390 | 54 |   59 |    42 |     223
2026-08-17 |  421 | 63 |   66 |    47 |     228
```

Backlog roughly doubled in five weeks. Auto-spawned follow-ups went 46 -> 194 —
now **46% of the whole backlog** — while genuine new work grew only 155 -> 228.
That is exactly the signal this feature must make visible on an ongoing basis.

## Scope

### 1. The category axis (unified)

One dimension, resolved per task in this order:

1. `followup_kind` from frontmatter when present;
2. otherwise the kind retro-derived by
   `.aitask-scripts/lib/followup_backfill_classify.py::classify()` — a **pure,
   side-effect-free** classifier (no writes, no git, no subprocess);
3. otherwise `issue_type` (the task is genuine new work).

This yields the split the user asked for — bug / manual verification / risk
mitigation / upstream defect / ... / genuine — in a single readable axis.

**Do not backfill or write `followup_kind` as part of this task.** Classification
happens at read time. `aitask_followup_backfill.sh` operates only on live tasks
and would leave the 1824 archived tasks unmarked anyway; live classification
covers the whole corpus without mutating anything.

### 2. The two series

- **Backlog level (a stock):** for each week bucket W, the number of tasks with
  `created_at <= end(W)` and (`completed_at` absent or `> end(W)`), per category.
- **Net flow (a flow):** arrivals (`created_at` in W) and departures
  (`completed_at` in W) per category, and their difference.

### 3. Surfaces

- **CLI** (`.aitask-scripts/aitask_stats.py`): new `### ` section(s) in
  `render_text_report()` (insert among the existing sections, ~:327-:425),
  following the established pipe-table style. Add the corresponding CSV columns
  in `write_csv()` (:480) and the row producer (`stats_data.py:1091`).
- **TUI** (`.aitask-scripts/stats/`): register new pane(s) via
  `register(PaneDef(...))`. If a new module is added it must be appended to the
  eager import list in `stats/panes/__init__.py:9` — a missed import is a
  `ModuleNotFoundError` that stops the whole TUI from starting.
- **Presets:** add the pane id(s) to **both** `stats/stats_config.py:17-24` and
  the shipped `aitasks/metadata/stats_config.json`. These two are duplicated and
  already drift (the JSON is missing the `sessions` preset) — do not add a third
  divergence.

## Key implementation constraints found during exploration

### `collect_stats()` is completion-keyed and archived-only

`lib/stats_data.py:1039-1104` iterates **archived** tasks only and buckets
everything by completion date. `created_at` is read **nowhere** in the stats
feature; active (non-archived) tasks are read only by `collect_inflight()`
(:976), whose `iter_active_markdown_files()` (:849) is the seam to reuse.

Backlog is therefore a **genuinely new axis**, not a variation on an existing
counter: it needs both an arrival key and the live-task population.

### The hard-coded 4-week ceiling

Weekly bucketing is a relative `week_offset` in `0..3`
(`week_offset_for` :241, `week_start_for` :236), with `range(4)` hard-coded in
roughly eight places: `stats_data.py:898,917`; `aitask_stats.py:363,380,398,416`;
`stats/panes/labels.py` `_HEATMAP_WEEKS = 4`; `stats/panes/velocity.py`
`weeks = [3,2,1,0]`.

A backlog trend needs 12-26 weeks. **Add a new absolute-week bucketing helper —
do not widen the existing constant**, which would reshape every existing table
and chart. Decide and document how the new helper relates to `week_start_for`
so there is one week-boundary definition, not two.

Related: `week_start_dow` is a `collect_stats` parameter but the TUI hard-codes
Monday (`stats_app.py:322,356`; `overview.py:13`), and the `week_start` /`days`
keys in `stats_config.DEFAULTS` are persisted but never read. Do not silently
inherit that inconsistency into the new pane; either honour the config key or
state explicitly that it stays Monday-only.

### `StatsData` must be edited in three lockstep sites

`lib/stats_data.py`: `collect_stats()` construction (:1106), `_empty_stats_data()`
(:1136), and `merge_stats_data()` (:1164). Missing the merge means multi-project
aggregation silently drops the new category.

**Merge semantics need explicit thought:** the existing fields are all *flows*
(counts of completions), where summing across projects is obviously right. The
backlog level is a *stock*. Summing open counts across distinct projects is
correct, but the same task must never be counted twice — confirm the session
discovery path (`discover_stats_sessions()` `stats_app.py:68`) cannot present
overlapping roots, or guard against it.

### The classifier needs the body, which `collect_stats` currently discards

`classify(metadata, body, filename)` uses prose-provenance rules anchored on body
headings (`## Origin`, `## Upstream defect`, `## Failed verification item from t`)
in addition to `issue_type`. `collect_stats` has `content` in hand in its loop
but keeps only the frontmatter dict.

Two integration details:

- `stats_data.parse_frontmatter` (:249) is the **flat string scanner**, not
  `task_yaml.parse_frontmatter`. It is correctly scoped to the leading `---`
  block (it breaks at the second delimiter), so the classifier's load-bearing
  anti-false-positive property is preserved. Verify that `classify()`'s
  `_labels(metadata)` and `metadata.get("issue_type")` behave correctly against
  the flat parser's **all-string** values, since the classifier was written
  against the YAML parser's typed output.
- Note the adjacent open task **t1304** (consolidate the two `lib/`
  `parse_frontmatter` functions). This task should not pre-empt or contradict
  that consolidation — pick whichever parser it will converge on, or state the
  dependency.

### Performance is not a constraint

Measured over the full corpus (1824 archived + 413 live = 2237 tasks):
decompress + iterate 0.10s, YAML frontmatter parse 0.67s, classify 0.06s —
**0.83s total**, and the flat parser used by `collect_stats` is cheaper still.
`archive_iter.iter_all_archived_markdown()` already transparently reads the
compressed `_bN/oldM.tar.zst` bundles.

### Data coverage

- 1824/1827 archived tasks carry `created_at`; 1816 carry `completed_at`.
- All 413 live tasks carry `created_at`.
- Coverage spans 2026-02 onward, so the series can go back ~6 months.
- Decide and document the handling of the handful of tasks missing a date
  (exclude them, and surface the excluded count rather than silently dropping).

## Precedent to follow, not reinvent

`.aitask-scripts/lib/work_report_gather.py` already imports `collect_stats` from
`stats_data` (:65) **and** reads `followup_kind` via `followup_kind_field` (:64,
:210) and `boardcol` (:194) on its own `TaskRow` (:123). It shows exactly how
both vocabularies are clamped at the read boundary. Mirror that rather than
writing a second clamping rule.

Vocabulary sources: `lib/followup_kinds.py` (kinds, glyphs, colours, and the
`followup_kind_field` clamp), `get_valid_task_types()` (`stats_data.py:875`) for
`issue_type`, and the display-name map at `aitask_stats.py:212-225`.

## Out of scope

- Backfilling or writing `followup_kind` onto any task file.
- Changing the existing 4-week tables, charts or panes.
- A `boardcol`-based definition of "backlog". The board column is set on only
  ~59 of 413 live tasks, so it is not a usable population definition; backlog
  here means *open* (created, not yet completed).

## Acceptance criteria

- `ait stats` prints a weekly backlog-level section and a weekly net-flow
  section, both split by the unified category axis, over a horizon longer than
  4 weeks.
- The stats TUI exposes the same information as registered pane(s), reachable
  from a preset, with the preset present in both config sources.
- CSV export carries the new columns.
- The new series are derived without writing to any task file.
- `merge_stats_data()` handles the new fields; a multi-project run does not drop
  or double-count them.
- Tests extend `tests/test_aitask_stats_py.py::TestCollection` and/or add a
  `_check_*` to `tests/test_stats_multistage.py`, covering at minimum: a task
  open across a week boundary, a task completed mid-series, a follow-up whose
  kind is only derivable by the classifier, and a task with a missing date.
- Existing stats output for the current categories is unchanged.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-17T19:02:14Z status=pass attempt=1 type=human
