---
Task: t1354_4_retrospective_measure.md
Parent Task: aitasks/t1354_speed_up_python_test_suite.md
Sibling Tasks: aitasks/t1354/t1354_1_board_fixture_harness.md, aitasks/t1354/t1354_2_migrate_remaining_board_tests.md, aitasks/t1354/t1354_3_parallel_test_lane.md
Archived Sibling Plans: aiplans/archived/p1354/p1354_*_*.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1354_4 — Retrospective measurement + floor tuning

## Goal

Measure what t1354_1..3 actually delivered against the parent's projections
(one denominator: `bash tests/run_all_python_tests.sh` wall time on the same
machine), tune the identified makespan floor only if data justifies it, and
file evidence-backed follow-ups. The measurement record in this plan is the
primary deliverable. Depends on all three siblings.

## Baseline (2026-07-31, 24-core machine)

- Full suite: 746s (serial unittest). Per-file sweep sum: 688s.
- Projections (parent plan; NOT hard gates): fixtures → ~280s; + xdist → ~60–120s.
- Known floor candidate: `tests/test_syncer_rows.py` — 124s, 2797 lines,
  18 classes, 136 tests, ~76 full `SyncerApp` boots via the `booted()`
  asynccontextmanager (:869-913; 14 seams mocked at :880-906 — no
  network/git/tmux). Under `--dist loadfile` the whole file pins one worker.

## Steps

1. Re-run the per-file sweep + full-suite measurement, both backends
   (unittest serial; pytest+xdist). Record before/after tables here. When
   piping, use `set -o pipefail` / `${PIPESTATUS[0]}` — the verdict banner is
   on stderr.
2. Identify the parallel makespan floor (slowest single file). If it is
   test_syncer_rows AND it dominates (floor ≈ total): split by test class into
   2–3 files — pure whole-class moves, no test-logic changes; promote shared
   helpers (`booted()`, `Seams`, `activate_tab`) to one importable place. If
   the floor is elsewhere or splitting buys <20%, do NOT split — record why.
3. Compare end state vs projections. Present any miss to the user with the
   data; the disposition (more work / accept / new task) is their call — never
   auto-revise.
4. File standalone follow-up tasks only where the data justifies them, each
   with measured evidence inline.
5. Write the retrospective (projected vs achieved, decisions, follow-ups) into
   this plan's Final Implementation Notes.

## Verification

- Suite green under both backends; wall times recorded, one denominator.
- If split: all syncer tests still collected + green under both backends
  (`tests/test_no_zero_collection.py` guards collection); makespan improvement
  recorded.
- Plan contains the complete before/after table + explicit dispositions for
  every projection.
