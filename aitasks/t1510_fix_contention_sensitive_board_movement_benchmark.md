---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [tui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
risk_mitigation_tasks: [1519]
assigned_to: dario-e@beyond-eye.com
anchor: 1449
followup_kind: upstream_defect
implemented_with: claudecode/opus5
created_at: 2026-08-13 15:44
updated_at: 2026-08-14 10:25
---

## Origin

Spawned from t1500 during Step 8b review.

## Upstream defect

- `tests/test_board_movement.py:1429-1433` — `test_attribution_tier_localises_an_injected_cost`
  asserts a wall-clock upper bound (neighbour self-time < 25 ms) that the
  suite's own 4-worker parallel lane can violate; observed `render`=40.0 ms in
  one of three full runs, passes standalone.
- `CLAUDE.md:44-46` — the documented serial carve-out ("currently
  `tests/test_board_header_row_live.py`") is stale; the runner announces three:
  `test_board_header_row_live.py`, `test_board_startup_focus_live.py` and
  `test_codebrowser_startup_focus_live.py`.

## Diagnostic context

Both surfaced while running the full Python suite three times to verify t1500's
board live-test flake fix.

**The benchmark.** Run 1 of three failed with:

```
AssertionError: 40.005746588576585 not less than 25.0 : `render` absorbed
40.0 ms of a cost injected into `refocus` -- self-time accounting is not
localising
```

Runs 2 and 3 passed (4540 passed, 2 skipped each), and the test passes
standalone in 6.7 s. The module imports nothing from the codebrowser and was
untouched by t1500, so this is not a regression from that change — it is a
timing assertion exposed to CPU contention from the suite's own
`-n 4 --dist loadfile` lane. The upper-bound *neighbour* assertions are the
fragile half: the lower-bound `delta >= NEGCTRL_SLEEP * 0.8` check is robust
because the injected 50 ms dominates, but "a neighbour absorbed < 25 ms" is a
statement about scheduling, not about attribution, and a descheduled worker
lands its stolen time wherever the clock happens to be running. Note the
existing `assertLess(clean[...]["refocus"], NEGCTRL_SLEEP * 1000, "control run
already exceeds the injected cost -- the negative control below could not
discriminate")` guard already acknowledges this class of problem for the
control run; the neighbour bounds have no equivalent.

**The carve-out list.** The runner's own banner reads:

```
parallel lane: -n 4 --dist loadfile (serial carve-out:
test_board_header_row_live.py test_board_startup_focus_live.py
test_codebrowser_startup_focus_live.py)
```

CLAUDE.md still describes the carve-out as a single module. The list grew when
the two `*_startup_focus_live.py` modules were added, and the doc was not
updated with it. This matters beyond tidiness: carve-out membership determines
whether a live tmux test runs against a loaded box, which is exactly the
variable t1500's flake turned on.

## Suggested fix

- Benchmark: make the neighbour-localisation assertions robust to contention
  rather than deleting them — e.g. assert on the *share* of the injected cost
  that landed in `refocus` versus each neighbour (a ratio is contention-invariant
  in a way an absolute millisecond bound is not), or take the best of N
  repetitions, or gate the absolute bounds behind a "quiet box" precondition the
  test can actually verify. Do not simply widen the 0.5 factor — that trades one
  arbitrary threshold for another and weakens the localisation claim the test
  exists to make.
- CLAUDE.md: derive the documented carve-out list from
  `tests/run_all_python_tests.sh`'s actual constant, or at minimum update the
  prose and add a guard test asserting the doc and the runner agree.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-13T19:57:49Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-14T07:23:07Z status=pass attempt=1 type=human
