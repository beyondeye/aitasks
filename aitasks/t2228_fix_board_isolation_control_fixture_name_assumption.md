---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [aitask_board, python]
gates: [risk_evaluated]
anchor: 1887
followup_kind: upstream_defect
created_at: 2026-11-07 22:17
updated_at: 2026-11-07 22:17
---

## Origin

Spawned from t1893_6 during Step 8b review.

## Upstream defect

- `tests/test_board_movement.py:1291 — IsolationNegativeControlTests.test_in_process_task_dir_override_reads_the_real_repo asserts no real task file ends in `_fixture.md`, but the live tree now holds t2226_stop_sync_fixture_copying_pycache_into_every_fixture.md (added in 92559489d by another session), so the control fails on every run regardless of the code under test (reproduced alone: 1 failed in 0.36s)`

## Diagnostic context

The full Python suite run for t1893_6 (`bash tests/run_all_python_tests.sh`) failed on this test, which is unrelated to screen-recording. It reproduces on its own:

```
python -m pytest -q "tests/test_board_movement.py::IsolationNegativeControlTests::test_in_process_task_dir_override_reads_the_real_repo"
AssertionError: Lists differ: ['t2226_stop_sync_fixture_copying_pycache_into_every_fixture.md'] != []
  : the real tree must contain none of the fixture files
```

The control (around lines 1280-1292) enumerates the real `aitasks/*.md` and requires that no name ends in `_fixture.md`. The intent is "the real tree contains none of *our* fixture files". The real task t2226 ends in `..._every_fixture.md`, which is a normal task name.

## Suggested fix

Assert on the exact fixture file names the test creates, or on a fixture-unique marker (prefix or content), rather than the generic `_fixture.md` suffix. Then the premise does not depend on what real task names happen to exist. Add a check that the real tree contains none of those exact names.
