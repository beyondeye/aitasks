---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [minimonitor, monitor, frozen_agents]
anchor: 2049
followup_kind: upstream_defect
created_at: 2026-10-19 12:00
updated_at: 2026-10-19 12:00
---

## Origin

Spawned from t2054 during Step 8b review.

## Upstream defect

- `.aitask-scripts/monitor/minimonitor_app.py:3211-3351` — `n` (`action_pick_next_for_own` → `_launch_pick_for_own` → `_launch_pick`) has no frozen guard; when the followed task is a parent / archived / Done it kills the frozen stand-in via `kill_agent_pane_smart`, whose frozen path is an unleased kill-then-drop that deletes the capture without warning (the hazard `_drop_frozen`'s docstring describes).

## Diagnostic context

t2054 moved the frozen restore/re-pick keys to the frozen-agent viewer, so the
monitors' keys keep their live-agent meaning. While making `p` (pick-by-number)
reachable on a frozen followed agent, it hid the pick dialog's "kill followed
agent" checkbox for a frozen agent. The reason: `kill_agent_pane_smart`
(`.aitask-scripts/monitor/monitor_core.py`, `kill_agent_pane_smart` /
`_drop_session_record`) kills the pane FIRST and then runs
`aitask_frozen.sh drop`. The kill takes no lease, so it can tear down a stand-in
whose record a restore coordinator owns, and the drop deletes the only copy of
the agent's output without the warning `k` shows.

`n` reaches the same sink by a different route, with no checkbox at all:
`_launch_pick_for_own` sets `should_kill` from the followed task's status
(parent-split / archived / Done) and passes the followed pane to `_launch_pick`,
which calls `self._monitor.kill_agent_pane_smart(kill_pane_id)` after a
successful launch. Nothing checks `self._is_frozen(snap)`. On a frozen agent whose
task is Done, which is the typical "I froze it once it finished" case, `n`
silently deletes the capture.

## Suggested fix

In `_launch_pick_for_own` (or at the kill site in `_launch_pick`, which also
covers the pick-dialog race tracked by t2054's planned mitigation
`recheck_frozen_before_pick_kill`), never pass a frozen pane to
`kill_agent_pane_smart`. Either launch without killing and tell the user to
retire the frozen agent with `k`, or route it to the leased `_drop_frozen` behind
its confirmation. Add a regression with a frozen Done followed agent (`n` →
launch, no `kill_agent_pane_smart` call) and a live Done control that still kills.
