---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [board, tests]
assigned_to: dario-e@beyond-eye.com
anchor: 2034
followup_kind: upstream_defect
created_at: 2026-11-05 15:03
updated_at: 2026-11-05 15:41
---

## Origin

Spawned from t2210 during Step 8b review.

## Upstream defect

- `tests/test_board_footer_multirow.py:85 — test_fixture_facts asserts footer keys after a single pilot.pause(); under suite load the footer is not yet rendered (failed once in the full xdist suite, passes alone) — same CPU-idle single-pause race class as t2210`

## Diagnostic context

- One full run of `bash tests/run_all_python_tests.sh` (xdist lane, 2026-11-05, one host under load from concurrent agents) printed `PYTHON SUITE: FAILED (runner=pytest, exit=1)`. Its only failure was `BoardMultiRowFooterTests::test_fixture_facts`: `AssertionError: [] is not true : fixture must render footer keys`. The test passed alone, and so did its whole module (10/10).
- The test mounts `KanbanApp` with `run_test(size=(200, 48))`, does one `await pilot.pause()`, then queries `FooterKey`. In Textual 8.2.7, `pilot.pause()` with no delay is `wait_for_idle(0)`. That waits on CPU idleness, not on any ordering guarantee, so under load one pause need not cover the footer's compose/refresh.
- t2210 fixed the same class in `tests/test_monitor_shadow_zone.py`. Loaded, interleaved, 12 burners: baseline 3/40 failed, fixed 0/40. See `aiplans/archived/p2210_fix_shadow_zone_mounted_refresh_race.md`.

## Suggested fix

Replace the single pause before the precondition queries with a bounded wait on the precondition: poll `list(app.query(FooterKey))`, bounding each `pilot.pause()` with `asyncio.wait_for` and rejecting a late success, as t2210's `_until` does. Do this for the whole class if the other tests share the pattern. Keep the assertions unchanged. Check the class's other single-pause sites for the same exposure.
