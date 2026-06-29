---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [gates, statistics, stats_ui]
gates: [risk_evaluated]
anchor: 635
created_at: 2026-06-29 15:52
updated_at: 2026-06-29 15:52
---

## Context

Follow-up to **t635_20** (stats multi-stage completion). t635_20 landed the
core ledger-aware completion dating, the in-flight "completed, awaiting gates"
series, and a time-in-phase aggregate, but **deferred two further
ledger-enabled metrics** by agreed scope. Both are fully specified (turnkey) in
`aidocs/gates/stats-multistage-completion.md` § "Deferred to a follow-up".

Depends on t635_20 (extends the same `stats_data.py` derivation layer + the
shared `gate_ledger.py` parser — no forked parsing, D6).

## Goal — implement the two deferred metrics in both `ait stats` and the stats TUI

1. **Per-gate pass/fail/retry rates.** For each gate name across the archived
   (and optionally in-flight) population, count `pass`/`fail` runs and average
   `attempt=` (retry depth). Derive from `gate_ledger.parse_gate_run_blocks`
   (ALL runs, not last-wins, so retries are visible). Surface as a CLI table +
   a new TUI pane (e.g. `pipeline.gate_health`).
2. **Pending-human wait.** Time a gate sat `pending` before `pass`: requires a
   `pending` marker with a `run=` ts followed by a later `pass` for the same
   gate; compute the delta per gate and aggregate. Data-sparse today (most gates
   record only a final `pass`) — only emit where the `pending`→`pass`
   transition actually exists, and report its N (mixed-population honesty).

## Key files

- `.aitask-scripts/stats/stats_data.py` — new derivation (reuse
  `parse_gate_run_blocks`, `format_duration`; mirror `PhaseTimings`/`collect_*`).
- `.aitask-scripts/aitask_stats.py` — CLI report sections.
- `.aitask-scripts/stats/panes/pipeline.py` (+ `panes/__init__.py`,
  `stats_config.py` + `aitasks/metadata/stats_config.json` preset) — TUI pane.
- `aidocs/gates/stats-multistage-completion.md` — the spec (update "Deferred"
  section to "implemented" on completion).

## Verification

- Unit tests for both metrics (synthetic ledgers with retries + pending→pass
  transitions), mirroring `tests/test_stats_multistage.py`.
- `./ait stats` + `./ait stats-tui` render the new surfaces with honest N.
