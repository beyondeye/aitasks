---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [trails, cross_repo]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1957
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-14 17:54
updated_at: 2026-10-14 21:57
---

## Origin

Spawned from t1979 during Step 8b review.

## Upstream defect

- `.aitask-scripts/board/board_trail_screen.py:1164 — _trail_jump_prepare_worker / _trail_jump_finish_worker run in Textual's default worker group; an exclusive default-group worker (_run_sync, run_dialog_command) cancelling one before it starts skips its finally, leaving _trail_jump_busy True so every later linked-trail jump is refused ("A jump is already in progress")`

## Diagnostic context

t1979 coalesced the linked-trail (`L`) scans behind a `_trail_link_running` slot
flag that is freed only in `_on_trail_links`, called from the worker's `finally`.
A review found that the scan worker ran in Textual's default worker group:
`@work(exclusive=True)` workers in that group — `aitask_board.py` `_run_sync`
(`exclusive=True, thread=True`) and the mixin's own `run_dialog_command`
(`board_trail_screen.py`, `exclusive=True`) — call
`workers.cancel_group(node, "default")` (textual `worker_manager.py`
`add_worker`: `if exclusive and worker.group: self.cancel_group(...)`). A thread
worker cancelled before its executor task starts never runs its body, so its
`finally` never runs either. t1979 fixed the scan by giving
`_trail_link_worker` its own group (`group="trail_link"`), pinned by
`test_an_exclusive_default_group_worker_cannot_strand_the_scan` in
`tests/test_board_bytrail_view.py` (it starts `app.run_worker(lambda: None,
thread=True, exclusive=True)` in the same tick as the press).

The jump workers (`_trail_jump_prepare_worker`, `_trail_jump_finish_worker`)
guard the same way with `_trail_jump_busy`, set in `_on_linked_trail_chosen` and
cleared only by their UI callbacks. Not reproduced separately; same mechanism.

## Suggested fix

Give both jump workers a dedicated non-default group (e.g. `group="trail_jump"`)
and add a twin of the t1979 regression test (exclusive default-group worker
started in the same tick as the pick; assert the jump completes and
`_trail_jump_busy` clears). Also audit the other default-group thread workers in
`board_trail_screen.py` (reload, drift, xdep, discovery) for state that only
their callback resets.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-14T18:57:31Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-14T19:12:18Z status=pass attempt=1 type=human
