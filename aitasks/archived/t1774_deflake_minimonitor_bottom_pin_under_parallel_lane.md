---
priority: medium
risk_code_health: low
risk_goal_achievement: medium
effort: low
depends: []
issue_type: bug
status: Done
labels: [test_infrastructure, minimonitor]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1599
followup_kind: upstream_defect
implemented_with: claudecode/opus5
created_at: 2026-09-09 22:23
updated_at: 2026-09-10 14:48
completed_at: 2026-09-10 14:48
---

## Origin

Spawned from t1725_3 during Step 8b review.

## Upstream defect

- `tests/test_minimonitor_bottom_pin.py:349 — DegenerateRangeTests::test_pinned_list_that_stops_overflowing_never_goes_negative is load-sensitive and fails under the parallel lane.` Failed at 97% in one full-suite run (`PYTHON SUITE: FAILED`), passed 8/8 standalone, and passed in an immediate re-run (`7200 passed, 0 failed`). It has zero references to anything t1725_3 touched. CLAUDE.md carves the `*_live.py` minimonitor module out of the parallel lane for exactly this boot-budget reason; this non-live module shares the sensitivity but is not carved out, so it can turn any developer's suite verdict red at random.

## Diagnostic context

Observed while running `bash tests/run_all_python_tests.sh --test-dir tests` to
verify t1725_3. The first run reported:

    [gw3] [ 97%] FAILED tests/test_minimonitor_bottom_pin.py::DegenerateRangeTests::test_pinned_list_that_stops_overflowing_never_goes_negative
    ============ 1 failed, 7199 passed, 2 skipped in 305.32s ============
    PYTHON SUITE: FAILED (runner=pytest, exit=1)

Run standalone immediately afterwards: `8 passed in 13.35s`. An immediate
re-run of the whole suite: `7200 passed, 2 skipped`, `PYTHON SUITE: PASSED`.

The test drives a Textual `VerticalScroll` through `pilot`, dragging the thumb,
shrinking the pane set, and asserting `scroll_y` never goes negative after the
compositor re-arranges -- i.e. it depends on layout settling within a bounded
number of pilot pauses. That is the same class of timing dependency CLAUDE.md
already documents for the four carved-out modules, whose "hard wall-clock boot
budget ... fails rather than skips" and which "a loaded worker pool turns into
a flake".

Note this is a verdict-level problem, not just an annoyance: the runner's last
line is the documented way to read the suite result, so one flaky module makes
that line untrustworthy for every other change.

## Suggested fix

Either make the settle deterministic (await a specific compositor state rather
than a fixed number of pilot pauses), or add the module to the serial carve-out
in `tests/run_all_python_tests.sh` alongside the four `*_live.py` modules. The
carve-out is the cheaper option but costs suite wall-clock; the deterministic
settle is the better one if the state to await can be named. Check whether the
sibling `test_minimonitor_bottom_pin_live.py` (already carved out) shares the
helper, in which case fixing the helper covers both.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-10T09:45:48Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-10T11:23:28Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-09-10T11:41:55Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:a73dedaff868c1a0

> **✅ gate:risk_evaluated** run=2026-09-10T11:41:55Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1774/risk_evaluated_2026-09-10T11:41:55Z-risk_evaluated-a1.log`

> **✅ gate:review_approved** run=2026-09-10T11:47:54Z status=pass attempt=2 type=human
