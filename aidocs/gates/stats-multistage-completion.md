---
title: Stats for Multi-Stage Completion
category: design
tags: [aitasks, gates, statistics, stats_ui, ledger, deferred-archival, time-in-phase]
sources: [aitask-gate-framework.md, integration-roadmap.md, gate-guarded-archival.md, python-gate-ledger-parser.md]
confidence: high
created: 2026-06-29
updated: 2026-06-29
---

# Stats for Multi-Stage Completion

Phase 3 of the gate-framework roadmap ([[integration-roadmap]]). Companion to
[[gate-guarded-archival]] (t635_4, which makes archival defer until all gates
pass) and the shared Python ledger parser (t635_8). It redefines how
task-completion statistics (`ait stats`, `ait stats-tui`) are computed once work
is multi-stage and archival can lag the actual work.

## Problem

`ait stats` (CLI `aitask_stats.py`) and `ait stats-tui` (`stats_app.py`) both
consume `collect_stats()` in `.aitask-scripts/stats/stats_data.py`, which assumed
a single linear pass ending in archival:

1. It iterates **archived task files only** (`iter_archived_markdown_files`), and
2. dates each task via `parse_completed_date` — `completed_at`, falling back to
   `updated_at` for `Done`.

The gate framework breaks both:

- **Deferred archival (t635_4):** a task can be implementation-complete but
  unarchived for days while human/async gates pend. It is invisible to stats (not
  archived), and when it finally archives, `completed_at`/`updated_at` reflect the
  *archive* moment — so daily/weekly counts silently shift and dip.
- **Multi-stage work:** "completed" is ambiguous, and the `## Gate Runs` ledger now
  records a per-checkpoint `run=<ISO-8601-Z>` timestamp (`plan_approved`,
  `review_approved`, `merge_approved`, …) pinning when each milestone happened.

## Decisions

### D-1 — Completion date is ledger-derived by precedence; the COUNT stays the archived population

`collect_stats` keeps iterating the **archived** population, so the headline
counts (Total / Last 7d / Last 30d) never change definition or jump for users who
have not adopted gates. What changes is the **date** each archived task is bucketed
under. `resolve_completion_date(content, frontmatter)` picks the first available:

1. `merge_approved` ledger `run=` ts — the shared/canonical "landed in main" event.
   **Primary**: it is the date meaningful for *all* users once pushed, not just the
   local reviewer.
2. `review_approved` ledger `run=` ts — fallback when no merge marker exists. This
   is the case on **current-branch profiles** (`fast`), where Step 9 records
   `merge_approved` only under the "separate branch" path; on the current branch
   the reviewed commit *is* the landing.
3. `completed_at` frontmatter — today's primary (pre-gates / no-ledger tasks).
4. `updated_at` (status `Done`) — today's final fallback.

The cutover is **per-task and automatic**: a task with no ledger
(`has_gate_markers` false) dates exactly as today; a gated task dates by when its
work landed, even if archived days later — back-filling the *correct* historical
day and fixing the "shift and dip".

**Pass-only, resolver-only.** A `merge_approved`/`review_approved` marker is used
for dating only when its *current* derived status is `pass` (`derive_gate_runs` is
last-wins, so a `fail`→`pass` retry counts via its final `pass`; a marker left
`fail`/`error` is skipped to the next rung). This is **resolver-only**: there is
**no whole-task exclusion** — a task carrying an unrelated lingering failure (e.g.
a `build_verified: fail` that proceeded anyway in Step 9) still stays in
`Total`/the archived series and is still ledger-dated by its passing checkpoint.

- *Rejected — a `completion_event:` config knob:* its only effect would be shifting
  dates by hours/days, and the ledger-derived date is strictly more accurate than
  archive time, so there is no real use case for selecting "archive time".
- *Rejected — "last gate pass":* a late async human gate would push the date well
  past the actual work.
- *Rejected — folding in-flight into the headline:* breaks `Total` continuity,
  double-counts on later archival, and conflates "done" with "done-but-gated".

### D-2 — In-flight "completed, awaiting gates" is a SEPARATE series

A distinct series, **never summed into the archived totals**, sourced from
**active** (non-archived) task files. A task qualifies iff (classified from content
via the shared parser): `has_gate_markers` is true, `review_approved` is `pass`,
and `archive_status_from_text(...)[0] == "BLOCKED"` (a declared gate is not yet
pass — exactly t635_4's deferred-archival state). Tasks that are merely
mid-implementation (`plan_approved` only) are excluded. Dated by `review_approved`.

Today this series is usually **empty** (the only default gate, `risk_evaluated`,
passes at planning time, so nothing defers); it populates once human/async gates
(t635_15, `docs_updated` t635_19) enter the picture, and renders as `0`/empty-state
until then — the honest "no data yet" path.

### D-3 — Time-in-phase aggregate — ledger timestamps only

Two spans, computed **exclusively from `## Gate Runs` `run=` timestamps** (uniform
UTC second precision) with **passing endpoints**:

- **Implement span:** `plan_approved` → `review_approved`.
- **Review→Merge span:** `review_approved` → `merge_approved` — computed **only when
  `merge_approved` exists**.

Each span reports its own sample `N` (they legitimately differ — current-branch
tasks contribute to Implement but never Review→Merge). A non-`pass` endpoint drops
the task from *that span's* sample (never zero — zero would bias the median).

**No archival-date fallback in the timing metric.** Falling back to the archival
date for the second span would (a) measure post-review *archival delay*, not
verification, and (b) mix a second-precision UTC ledger timestamp with a
**day-granular** archival `date`. D-1 *dating* may still fall back to the archival
date (dating is day-granular by design); the *timing metric* must not.

- *Rejected — a "planning" span (`created_at` → `plan_approved`):* dominated by how
  long a task sat `Ready` before pickup; noise, not signal.

### D-4 — Continuity / mixed-population honesty

- Pre-gates archived tasks (no ledger) date via the legacy fallback (D-1 §3-4) — no
  flag day, no behavior change for non-adopters.
- The Pipeline Timing section and in-flight surfaces **show their `N`**, so a small
  gated sample is never mistaken for the whole population.
- The headline COUNT is unchanged (archived population).

### D-5 — Derivation location: extend `stats_data.py`, import from `gate_ledger.py`

All new derivation lives in the pure data layer (`stats_data.py`), consumed by both
CLI and TUI. **No forked parsing** — it calls `gate_ledger` primitives
(`has_gate_markers`, `derive_gate_runs`, `archive_status_from_text`); a new
content-level `archive_status_from_text` wrapper was added to `gate_ledger.py` so
the active-task scan classifies from content alone (no path open → deterministic
under a rebased project root). `parse_completed_date` is kept intact as the
no-ledger fallback.

## Accepted approximation

Ledger `run=` stamps are UTC; `completed_at`/`updated_at` are local. Completion
*dating* slices to day granularity (`[:10]`, the precision stats already use), so a
task completed near midnight UTC could land on an adjacent local day. This is
accepted as negligible for day/week buckets. Timing *spans* use full UTC datetimes
on both endpoints, so they are unaffected.

## Deferred to a follow-up (designed here, not implemented in t635_20)

Per the agreed scope, two further ledger-enabled metrics are specified here so the
follow-up is turnkey:

- **Per-gate pass/fail/retry rates.** For each gate name across the archived (and
  optionally in-flight) population, count `pass`/`fail` runs and average `attempt=`
  (retry depth). Surfaces framework health (which gates fail/retry most). A CLI
  table + a TUI pane (e.g. `pipeline.gate_health`). Derive from
  `parse_gate_run_blocks` (all runs, not just last-wins) so retries are visible.
- **Pending-human wait.** Time a gate sat `pending` before `pass`: requires a
  `pending` marker with a `run=` ts followed by a later `pass` for the same gate;
  compute the delta per gate and aggregate. Data-sparse today (most gates record
  only a final `pass`), which is why it is deferred — only emit where the
  `pending`→`pass` transition actually exists, and report its `N`.

## References

- `.aitask-scripts/stats/stats_data.py` — `resolve_completion_date`,
  `iter_active_markdown_files`, `collect_inflight`, `PhaseTimings`,
  `format_duration`.
- `.aitask-scripts/lib/gate_ledger.py` — `archive_status_from_text`,
  `derive_gate_runs`, `has_gate_markers` ([[python-gate-ledger-parser]]).
- `.aitask-scripts/aitask_stats.py` — Summary in-flight line, `render_pipeline_timing`.
- `.aitask-scripts/stats/panes/pipeline.py` — `pipeline.timing` / `pipeline.inflight`.
