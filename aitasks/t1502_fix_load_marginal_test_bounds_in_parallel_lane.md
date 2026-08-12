---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [aitask_monitormini]
anchor: 1159
followup_kind: upstream_defect
created_at: 2026-08-12 23:38
updated_at: 2026-08-12 23:38
---

## Origin

Spawned from t1159_2 during Step 8b review.

## Upstream defect

- `tests/test_board_movement.py:1432 — the t1395 attribution-tier
  negative-control bound (25ms of a 50ms injection) is contention-marginal
  under the parallel lane: it flaked in ~4 of 10 full-suite runs on a loaded
  box (worker packing shifts when test modules are added), passes standalone
  and on a parent-commit control; candidate for the runner's serial carve-out
  or a tolerance derived from a same-run baseline`
- `tests/test_codebrowser_startup_focus_live.py — hot-handoff live test
  missed its boot budget once under the same sustained load; passes
  standalone; same load-sensitivity class as the board benchmark`

## Diagnostic context

During t1159_2's review loop, repeated back-to-back full-suite runs (~10 in
two hours, `-n 4` parallel lane) intermittently failed on these two tests
while every other test stayed green in every run. Both pass standalone in the
same session. A parent-commit control run in an isolated worktree also passed
the board benchmark — the trigger is that adding test modules shifts
`--dist loadfile` worker packing, changing which files share the benchmark's
worker during its timed window. The failing assertion reads e.g.
"`render` absorbed 39.4 ms of a cost injected into `refocus`" — wall-clock
self-time attribution bleeding across spans under CPU contention, not an
accounting logic error. `tests/run_all_python_tests.sh` already has a serial
carve-out (`SERIAL_CARVE_OUT=(test_board_header_row_live.py)`) for exactly
this class of live/budgeted test.

## Suggested fix

Either add the two modules (or just the benchmark test class) to the runner's
serial carve-out, or derive the attribution tolerance from a same-run
measured baseline instead of a fixed 25ms constant (the t1395 perf-gate
convention: one denominator, within-run ablation — see
`aidocs/framework/python_tui_performance.md` and the
`project_benchmark_contention_concurrent_agents` practice).
