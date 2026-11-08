---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [sitrep, monitor]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 2175
followup_kind: upstream_defect
created_at: 2026-11-08 09:16
updated_at: 2026-11-08 09:19
---

## Origin

Spawned from t2211_2 during Step 8b review.

## Upstream defect

- `tests/test_board_movement.py:1292 — IsolationNegativeControlTests asserts the REAL aitasks/ tree contains none of its fixture filenames, so it fails whenever a real task shares one (today t2226_stop_sync_fixture_copying_pycache_into_every_fixture.md); the control should use fixture names that cannot collide with real task files.`
- `tests/test_sitrep_window.py:61 — LIVE_PID = os.getpid() is used as a "not a companion" pid in matcher/classify fixtures that reach the real /proc cmdline rung, so they fail when the test process argv contains "minimonitor" (e.g. a pytest run naming tests/test_minimonitor_*.py in the same invocation); those fixtures should patch _is_companion_process like ConsumerTableTests does.`

## Diagnostic context

- During t2211_2 the full Python suite (`bash tests/run_all_python_tests.sh --test-dir tests`)
  failed only on `test_board_movement.py::IsolationNegativeControlTests::test_in_process_task_dir_override_reads_the_real_repo`
  with `['t2226_stop_sync_fixture_copying_pycache_into_every_fixture.md'] != [] : the real
  tree must contain none of the fixture files` — a real task (t2226) happens to carry one of
  the control's fixture filenames. Independent of any code change: the assertion reads the
  live `aitasks/` tree.
- Running `python -m unittest tests.test_sitrep_window tests.test_minimonitor_sibling_fallback`
  (or pytest naming `tests/test_minimonitor_own_identity_renumber.py` together with
  `tests/test_sitrep_window.py`) produced ~18 spurious failures in `MatcherTests` /
  `ClassifyParityTests` / spawn tests: their pane fixtures use `pid=os.getpid()`, and
  `monitor_core._is_companion_process` matches `minimonitor` in that pid's `/proc/<pid>/cmdline`,
  so the "agent" fixture becomes a companion. The suite runner's xdist workers hide it.

## Suggested fix

- test_board_movement: generate fixture task names that cannot exist in the real tree (e.g. a
  unique, clearly synthetic prefix or a uuid suffix), or assert on fixture-specific content
  instead of filename absence.
- test_sitrep_window: wrap the LIVE_PID-based fixtures in `patch.object(mc, "_is_companion_process", lambda pid: False)`
  (as `ConsumerTableTests` does), keeping the one test that needs the real cmdline rung
  (the booting-companion stand-in) explicit.
