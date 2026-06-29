---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: [t635_4, t635_8]
issue_type: feature
status: Implementing
labels: [gates, statistics, stats_ui]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-10 21:39
updated_at: 2026-06-29 15:27
---

## Context

Task-completion statistics (`ait stats`, `ait stats-tui`) assume work on a
task is a single linear pass ending in archival: they iterate ARCHIVED task
files only (`iter_archived_markdown_files`) and derive the completion date
from `completed_at` with an `updated_at` fallback for status Done
(`.aitask-scripts/stats/stats_data.py:229`, shared with
`aitask_stats.py`). The gates work breaks both assumptions:

- **Deferred archival (t635_4):** a task can be implementation-complete but
  unarchived for days while human gates pend — it is invisible to stats
  (not archived) and its eventual archival date no longer reflects when the
  work happened. Daily/global counts silently shift and dip.
- **Multi-stage work:** "completed" becomes ambiguous — implemented?
  review-approved? all-gates-pass? archived? Each is a different date with
  a different meaning.

## Goal — design pass first, then implement

Design (with trade-offs and rejected alternatives, doc under
`aidocs/gates/`) how completion statistics are computed and reported
meaningfully for multi-stage tasks, then implement in both `ait stats` and
the stats TUI.

Design questions to settle:
- **Which event is "completion"** for the headline counts — and should it
  be configurable? Candidate: keep archival as the headline event for
  continuity, but date it from a ledger-derived event (e.g. last gate
  pass / merge approved) rather than archive time.
- **In-flight visibility:** should stats count/report unarchived tasks
  whose implementation finished (gates pending)? E.g. a "completed,
  awaiting gates" series next to the archived series.
- **New ledger-enabled metrics** (the Gate Runs ledger gives per-checkpoint
  timestamps for free): time-in-phase (planning → implementing → gated →
  archived), gate pass/fail/retry rates per gate name, pending-human wait
  times. Decide which are worth surfacing vs noise.
- **Continuity/back-compat:** pre-gates archived tasks have no ledger —
  mixed-population statistics must not mislead (per-series cutover note or
  fallback derivation).
- Where derivation lives: reuse the shared Python gate-ledger parser
  (t635_8) — no forked parsing in stats code.

## References

- `aidocs/gates/integration-roadmap.md` (Phase 2 archival change, Phase 3)
- `.aitask-scripts/stats/stats_data.py` (`parse_completed_date`,
  `iter_archived_markdown_files`)
- `aidocs/framework/python_tui_performance.md` (if TUI runtime questions
  arise)

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-29T12:27:39Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-06-29T12:43:46Z status=pass attempt=1 type=human
