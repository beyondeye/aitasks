---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [tests, testing]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1599
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-11-15 18:31
updated_at: 2026-11-15 22:12
---

## Origin

Spawned from t1912_2 during Step 8b review. t1912_2 ran the full Python suite
(`bash tests/run_all_python_tests.sh`), which reported
`PYTHON SUITE: FAILED (runner=pytest, exit=1)`: 8 failed, 12104 passed. None of
the failures is related to t1912_2. Both modules were then rerun in isolation,
and the 8 tests were run in a scratch worktree at HEAD `57b660ff0` without any
t1912_2 change. They fail deterministically in every run.

## Upstream defect

- `tests/test_screen_recording_cli.py` — 6 contact-sheet label layout tests fail:
  - `AnimMode::test_narrow_roi_sheet_labels_stay_inside_their_cells`
  - `BugMode::test_layout_reduced_sheets_list_the_frames_they_hold`
  - `ContactSheets::test_too_many_frames_for_readable_labels_reduce_each_sheet`
  - `SheetMode::test_hostile_names_are_staged_and_shown_safely`
  - `SheetMode::test_narrow_tiles_keep_labels_inside_their_cells`
  - `SheetMode::test_too_many_per_sheet_is_split_with_a_warning`

  Observed assertion messages:
  - `AssertionError: 1485 not less than or equal to 400 : premise: w_min was measured over these labels`
  - `AssertionError: 64 not less than 64`
  - `AssertionError: 1 not greater than 1`
  - `AssertionError: '...' not found in '#1 t00000100_xxxx…xxxx.png'`
  - `AssertionError: False is not true`
  - `AssertionError: [] == []` (as printed)
- `tests/test_aitask_questions.py` — 2 StoreTests fail (the t2281 area):
  - `StoreTests::test_candidate_is_a_remote_client_inside_the_project`, with
    `AssertionError: stand-in (thread) never started its child`
  - `StoreTests::test_children_are_read_from_every_thread_and_hosting_stops_at_an_app_server`,
    with `AssertionError: stand-in (main) never started its child`

## Diagnostic context

- Not diagnosed. t1912_2 only established that these tests fail independently of its change.
- The screen-recording assertions measure rendered label widths. That suggests a dependency on the font or ffmpeg build in this environment (Linux 7.2.15 omarchy box, Python 3.14.10, venv `~/.aitask/venv`).
- The questions tests wait for a stand-in process's child and fail even when run alone (`-p no:randomly`, no parallel lane). So this is not load-induced flakiness.

## Suggested fix

Start with `git log` for both modules, since the recent commits are t2238 / t2239 (screen recording) and t2281 (questions). Determine whether each failure is environment-dependent, in which case the test needs a capability probe or a measured premise, or a real regression. Fix the cause, not the assertion.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-15T20:11:58Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-15T21:43:14Z status=pass attempt=1 type=human
