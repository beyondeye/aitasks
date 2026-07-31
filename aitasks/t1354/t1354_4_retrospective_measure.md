---
priority: medium
effort: low
depends: []
issue_type: performance
status: Ready
labels: [test]
gates: [risk_evaluated]
anchor: 1111
created_at: 2026-07-31 07:56
updated_at: 2026-07-31 07:56
---

## Context

Fourth child of t1354 (parent plan `aiplans/p1354_speed_up_python_test_suite.md`);
depends on t1354_1, t1354_2, t1354_3. Bounded retrospective per
`aidocs/framework/planning_conventions.md` ("Plan split: in-scope sibling
children, not deferred follow-ups"): measure what actually landed, tune the
one identified floor only if data justifies it, and file follow-ups only where
the collected data warrants.

Baseline (2026-07-31, 24-core machine): full suite 746s serial-unittest;
per-file sweep sum 688s; top offenders test_board_bytrail_view 165s (migrated
in t1354_1), test_syncer_rows 124s, ~8 board modules ~200s (migrated in
t1354_2). Projection recorded in the parent plan: fixtures → ~280s; + xdist →
~60–120s. Projections are NOT hard gates — a miss is presented to the user,
never silently re-scoped.

## Key Files to Modify

- `aiplans/p1354/p1354_4_*.md` (this child's plan) — the measurement record is the deliverable
- `tests/test_syncer_rows.py` — split by test class into 2–3 files ONLY if measurement shows it is the binding per-worker floor
- Possibly: new standalone follow-up tasks via `aitask_create.sh --batch` where data justifies

## Reference Files for Patterns

- `tests/test_syncer_rows.py` — 2797 lines, 18 classes, 136 tests; ~76 full `SyncerApp` boots via the `booted()` asynccontextmanager (:869-913, boots `run_test(size=(120,30))` per test with 14 seams mocked at :880-906 — no network/git/tmux). Booting classes: TabbedShellTests (25), SettingsTabTests (29), UpgradeActionTests (16), VersionsTabTests (6); the other ~60 tests are pure-unit. Under `--dist loadfile` the whole file pins one worker → it is the likely makespan floor.
- Timing method from the t1354 exploration: per-file `python -m unittest discover -s tests -p <file>` sweep + one-denominator full `bash tests/run_all_python_tests.sh` wall time (use `${PIPESTATUS[0]}`/`set -o pipefail` when piping — the verdict banner is on stderr).

## Implementation Plan

1. Re-run the per-file sweep and the full-suite measurement on this machine, both backends: (a) unittest serial, (b) pytest+xdist parallel lane. Record before/after tables in the plan against the 2026-07-31 baseline.
2. Identify the parallel makespan floor (slowest single file). If it is test_syncer_rows and it dominates (floor ≈ total), split the file by test class into 2–3 files (pure file moves of whole classes — no test-logic changes; keep shared helpers importable from one place, e.g. promote `booted()`/`Seams` to `tests/lib/` or a sibling module). If the floor is elsewhere or splitting buys <20%, do NOT split — record why.
3. Compare the end state against the parent's projections. For any missed target, present the data to the user and let them decide the disposition (further work / accept / new task) — never auto-revise.
4. File standalone follow-up tasks only where the data justifies them (e.g. a newly-grown slow file, a flaky test under contention), each with the measured evidence inline.
5. Write the retrospective summary (what was projected vs achieved, decisions taken, follow-ups filed) into this child's plan Final Implementation Notes — it is the primary deliverable.

## Verification Steps

- Full suite green under both backends; wall times recorded with one denominator.
- If test_syncer_rows was split: all its tests still collected and green under both backends (`test_no_zero_collection.py` guards collection), and the measured makespan improvement is recorded.
- The plan contains the complete before/after table and explicit dispositions for every projection.
