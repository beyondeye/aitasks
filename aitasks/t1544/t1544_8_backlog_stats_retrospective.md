---
priority: medium
effort: low
depends: []
issue_type: chore
status: Ready
labels: [reporting, metrics, backlog]
gates: [risk_evaluated]
anchor: 1544
created_at: 2026-08-17 22:09
updated_at: 2026-08-17 22:09
---

## Context

Final child of t1544 (backlog level + net flow by category in `ait stats`).
Parent plan: `aiplans/p1544_stats_backlog_and_net_flow_by_category.md`.
Depends on every sibling.

Per `aidocs/framework/planning_conventions.md` §"Plan split: in-scope sibling
children, not deferred follow-ups", a decomposition that commits to a design
choice under partial information gets a trailing retrospective child. t1544 made
several such commitments, all of them defensible at planning time and none of
them provable until the feature has been used against the real, moving corpus.

This task is **evaluation, not implementation**. Its deliverable is a written
answer to each question below, plus standalone follow-up tasks **only where the
collected data justifies them**. "No change needed" is a valid and expected
outcome for most of these.

## Questions to answer

### 1. Was flows-only storage the right shape?

The data layer stores `backlog_arrivals` / `backlog_departures` and derives the
level at render time via `backlog_levels()`. The reasoning was that a stock
derived from summed flows equals the sum of the stocks, so multi-project
`merge_stats_data` stays a plain additive `Counter.update` and the
"summing a stock across projects" hazard disappears structurally.

- Did any consumer end up wanting a stored level?
- Did the O(k) suffix-scan cumulation stay cheap as history grew past ~30 weeks?
- Did the `out_offsets`-selects-output-columns-only contract survive contact
  with a second caller, or did someone re-introduce the horizon-restricted
  cumulation bug it was written to prevent?

### 2. Is 8 weeks the right default horizon?

`BACKLOG_WEEKS_DEFAULT = 8` was chosen because the categories-as-rows table
renders at exactly 80 characters at that width, and the task's motivation
section argued for 12-26 weeks. The compromise was: fit 80 columns by default,
let `--backlog-weeks` widen it.

- What do people actually pass? Is the default routinely overridden?
- Does 8 weeks show enough of a trend to answer "do we need a consolidation
  push?", or does it truncate the interesting part?
- Does the TUI pane, which reads the same constant, want a different value —
  and if so, is that a *user setting applied to both surfaces* rather than a
  second default? (The single shared constant exists specifically to stop the
  two surfaces drifting; do not resolve a difference by adding a literal.)

### 3. Is parent + child the right denominator?

Both parents and their children count as open, so a coordination shell and its
children all appear. The `TOTAL OPEN` row carries a `(parents / children)` split
to make that visible.

- Does the headline number read as "units of work" and mislead, or does the
  split do its job?
- Roughly 29 of ~300 open parents were pure coordination shells at planning
  time. Has that ratio moved enough to matter?

### 4. Postponed counted as open — right call?

9 live tasks (~2%) at planning time. They are outstanding work by the stated
definition, but they are deliberately parked, and the metric's whole purpose is
to decide whether a consolidation push is needed.

- Has the Postponed count grown enough to distort that decision?
- Is a separate row, or netting them out, warranted now?

### 5. Did the TUI presentation hold up at real cardinality?

This was the plan's main unproven risk: the CLI shape was rendered against live
data during planning, the TUI shape was not. 17 distinct categories x 9 week
columns in a `DataTable`, and a plotext chart capped at ~100 columns.

- Did the row cap / `Other` bucket land at a sensible threshold?
- Is `backlog.netflow`'s category split legible, or did it degrade into noise?
- Did either pane need a shape the plan did not anticipate?

### 6. Did the doubled `collect_stats` cost matter?

The feature roughly doubles `collect_stats` (measured 0.15s of added work over
~2250 files). The stats TUI collects synchronously on mount, once per discovered
session, so a multi-repo user pays it per repo.

- Measure `ait stats-tui` startup with the real number of registered repos.
- Was `with_backlog=False` on `work_report_gather` sufficient, or does another
  caller want it?
- Is the deliberately-out-of-scope no-live-walk opt-out (which would also have to
  gate `collect_inflight`) now worth filing?

### 7. Two completion clocks — did anyone get confused?

The backlog sections use `completed_at`; the pre-existing sections use
`resolve_completion_date`, which prefers ledger stamps. They disagree on the week
for ~0.3% of tasks (26 of ~1828 by a day, 6 by a week). This was a deliberate,
user-approved choice to meet the task's stated definition, footnoted in the
report and documented in the website docs.

- Did the footnote do its job, or did the discrepancy generate questions?
- Is converging the two clocks (in either direction) now worth a task?

### 8. Deferred items that may now be worth filing

- **Preset list-replacement semantics.** t1544_5 pinned, but did not change, the
  fact that a `presets.<name>` list in `aitasks/metadata/stats_config.json`
  **replaces** the code list — so a pane added to an existing code preset is
  silently masked for any project that pins that preset. Changing it to
  merge-instead-of-replace is a behaviour change to every preset. Worth a task?
- **`week_start` / `days` in `stats_config`** are persisted but never read; the
  TUI hardcodes Monday. Honouring them needs `resolve_week_start` moved from the
  CLI into `lib/` first (existing TODO t597_4). Still wanted?
- **`created_at` on the per-task CSV** was added for lead-time analysis, not
  backlog (open tasks are not rows there). Has anyone used it? If not, note it
  rather than removing it.

## Deliverable

Write the answers into this task's plan file under a
`## Retrospective findings` heading, one subsection per question, each ending in
an explicit disposition: **no change needed**, **filed as tN**, or **folded into
an existing task tN**. File only what the data supports — per
`planning_conventions.md`, an evaluation with no findings produces an
evaluation-only record, not speculative infrastructure.

## Verification steps

- Every question above has a written answer with a disposition.
- Any follow-up task created is referenced by ID in the findings.
- Numbers quoted in the findings are re-measured against the corpus at the time
  of writing, not copied from the parent plan's planning-time snapshot — the
  corpus moved measurably during planning alone.
