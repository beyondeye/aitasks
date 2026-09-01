---
priority: medium
risk_code_health: low
risk_goal_achievement: medium
effort: medium
depends: []
issue_type: bug
status: Done
labels: []
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1653
followup_kind: review_finding
implemented_with: claudecode/opus5
created_at: 2026-09-01 09:53
updated_at: 2026-09-01 17:02
completed_at: 2026-09-01 17:02
---

`test_minimonitor_startup_input_latency.py::MountWindowProbeTests::test_mount_returns_while_the_window_probe_is_still_blocked`
fails inside the parallel suite lane after t1653's minimonitor bottom-pin
change (`451dd3af7`, +325 lines to `.aitask-scripts/monitor/minimonitor_app.py`).

Found while running t1636_6's manual-verification checklist, which requires a
green `bash tests/run_all_python_tests.sh --test-dir tests`. Raised here rather
than as a t1636 follow-up because no t1636 commit touches that file or that test.

## Evidence

- Two full-suite runs on a tree carrying t1653's change (uncommitted at the
  time; the same bytes are now HEAD):
  - `key took 822.3ms with the loop otherwise idle` — assertion budget is
    `INPUT_BUDGET_S / 2` = 500ms.
  - `key took 595.3ms` on a re-run with the machine **otherwise idle**, so this
    is not external contention.
- The same test passes in **0.41s** when run alone, so it only misses under the
  `-n 4 --dist loadfile` lane.
- A/B against a pristine pre-t1653 baseline (`git archive` of the then-HEAD,
  independently confirmed free of the change: `grep -c MiniPaneScrollBar` -> 0
  there, 4 with the change): the same test **PASSES** in the same full-lane run.
  The baseline run has 4 failures of its own — `test_board_movement`,
  `test_profile_editor_shadow_tier` x2, `test_settings_brainstorm_descriptions`
  — all of which pass in the real tree; they are artifacts of a `.git`-less
  archive tree without local config, not signal.

## What to work out

Whether t1653's added work (the `MiniPaneScrollBar` subclass, the `MiniPaneList`
additions, `_restore_list_scroll`) lands on the mount / first-input path this
test measures, or whether it merely lengthens the lane enough to push an already
marginal timing assertion over its budget.

Those two have different fixes: the first is a real input-latency regression in
minimonitor; the second means the assertion needs the right instrument rather
than a wall-clock budget measured under a loaded worker pool (see
`aidocs/framework/testing_conventions.md`). Decide which before changing either
the code or the budget — raising the budget to make it green would erase the
signal if it is the first.

## Acceptance

- The mechanism is identified and stated (regression vs. marginal assertion).
- `bash tests/run_all_python_tests.sh --test-dir tests` reports
  `PYTHON SUITE: PASSED` on an idle box, repeatably.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-01T12:19:40Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-01T13:58:08Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-09-01T14:02:42Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:1bfc029f49048e4f

> **✅ gate:risk_evaluated** run=2026-09-01T14:02:42Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1660/risk_evaluated_2026-09-01T14:02:42Z-risk_evaluated-a1.log`
