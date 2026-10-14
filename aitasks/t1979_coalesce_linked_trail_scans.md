---
priority: low
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: []
issue_type: performance
status: Implementing
labels: [trails, performance, cross_repo]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1957
followup_kind: review_finding
implemented_with: claudecode/opus5_5
created_at: 2026-10-14 11:25
updated_at: 2026-10-14 17:10
---

## Context

Review finding on t1957_4 (the `L` Linked Trails action in the board's
By-Trail view and `ait trails`). Every accepted `L` press starts a new
`_trail_link_worker` in `.aitask-scripts/board/board_trail_screen.py`
(`action_trail_linked`). The supersession stamp (`_trail_link_gen`, checked in
`_on_trail_links`) discards an obsolete result only AFTER its
`scan_linked_trails` has completed. Each scan independently runs one export
subprocess per candidate project, on a pool of up to 4 workers
(`.aitask-scripts/lib/trail_links.py`, `scan_linked_trails` / `_collect_export`).
Repeated or held `L` presses therefore multiply export work: N overlapping scans
spawn up to 4·N concurrent export subprocesses, although only the newest answer
can ever be displayed. Measured scan time on the dev host is ~1.5s, with
7 registered projects.

This was a deliberate part of the t1957_4 concurrency design ("a new press
supersedes the previous one"), so it is an improvement, not a defect.

## Goal

Bound the work of overlapping searches while keeping the newest-request-wins
behaviour exactly as it is today:
- the result shown is always the newest press's;
- tab switch / close / leaving By-Trail / a content change still drop a
  result (see the guards in `_on_trail_links`).

Options to weigh:
- **Coalesce:** while a scan is in flight, a new `L` only records "re-run when
  this one lands". When it lands, its result is dropped and ONE fresh scan
  runs for the latest request. At most one scan runs at a time, plus at most
  one pending.
- **Bound:** a module-level semaphore in `trail_links` around
  `scan_linked_trails`, so concurrent scans queue instead of multiplying the
  pool.

Coalescing needs care: the request that actually runs must be built from the
trail and doc snapshot taken at the LATEST press (`action_trail_linked`
captures `origin` and a `copy.deepcopy` of the doc). Re-using the first
press's snapshot would show links for a stale revision.

## Verification

- Extend the event-gated tests in `tests/test_trails_app.py`
  (`LinkedTrailsTabTests`, especially `test_two_searches_show_only_the_newest_in_either_order`)
  and `tests/test_board_bytrail_view.py` (`LinkedTrailsTests`). Several presses
  while a scan is gated → at most one scan in flight, plus one pending. Only
  the newest request's result shows. The pending scan uses the latest
  snapshot. The tab-switch / close / content-change drops still hold.
- `bash tests/run_all_python_tests.sh`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-14T14:10:19Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-14T14:50:52Z status=pass attempt=1 type=human
