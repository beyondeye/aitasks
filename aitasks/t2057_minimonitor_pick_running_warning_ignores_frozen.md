---
priority: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [minimonitor, monitor, frozen_agents]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
folded_tasks: [2058, 2059]
assigned_to: dario-e@beyond-eye.com
anchor: 2049
followup_kind: review_finding
created_at: 2026-10-19 11:16
updated_at: 2026-10-19 12:18
---

## Symptom

In the minimonitor's pick-by-number flow (`p`), the confirmation dialog warns
"⚠ t<id> is already running in this session" for a task whose only window is a
**frozen** stand-in. The agent is stopped — its pane holds the `ait frozenagent`
viewer — so the warning is false.

Reproduced with the `tests/test_minimonitor_pick_by_number.py` fixtures: follow a
frozen t77 (`_snap(..., frozen=True)`), press `p`, enter `77` → the dialog's
`_already_running` names t77's window. Launching still works.

t2054 made this reachable: before it, `p` on a frozen followed agent re-picked
instead of prompting, so the confirm dialog never opened in that state. The
scanner itself is older.

## Root cause

`MiniMonitorApp._find_running_agent_line` (`.aitask-scripts/monitor/minimonitor_app.py`)
filters snapshots only by `PaneCategory.AGENT`, session scope and task id. A frozen
snapshot keeps `category == AGENT` (`frozen=True`, `frozen_record_id` set), so it
counts as running.

## Fix

- Skip frozen snapshots in `_find_running_agent_line` (`self._is_frozen(snap)` —
  the same strict predicate the rest of the app uses).
- Decide (and document in a comment) whether a frozen agent of the target task
  deserves a *different* note instead — e.g. "t<id> has a frozen agent in window
  …; restore or re-pick it from its viewer" — rather than silence. Silence is the
  minimal fix; a distinct note is the better UX if it fits the narrow dialog.
- Regression in `tests/test_minimonitor_pick_by_number.py`: frozen snapshot of
  the target task → `_already_running` is None (or the frozen note); live
  snapshot of the same task → still warns (control).
- Check whether the full monitor has an equivalent "already running" scan with
  the same hole (`monitor_app.py`) and fix it the same way if so.

## Merged from t2058: minimonitor next kills frozen standin unleased


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

## Merged from t2059: recheck frozen before pick kill


## Origin

Risk-mitigation ("after") follow-up for t2054, created at Step 8d after implementation landed.

## Risk addressed

code-health race (agent frozen while the pick dialogs are open)

> Existing race, kept by this plan: the frozen guard in `_on_pick_number_entered` reads the snapshot taken when the prompt opened. `_on_pick_confirmed` checks only that the pane still exists, and `_launch_pick` kills only after another dialog. If another monitor freezes a live followed agent while these dialogs are open, a ticked kill still reaches `kill_agent_pane_smart`'s unleased frozen path and deletes the capture · severity: medium · → mitigation: recheck_frozen_before_pick_kill

## Goal

In the minimonitor pick flow (`.aitask-scripts/monitor/minimonitor_app.py`
`_on_pick_confirmed` / `_launch_pick`), re-read the kill target's **current**
frozen state immediately before `kill_agent_pane_smart` runs. Read it from the
live `self._snapshots` entry, or better from the store/pane option at kill time,
because a snapshot can itself be a tick stale. If the target is frozen now, launch
without killing and say so (e.g. "Followed agent was frozen meanwhile — launched
without kill; drop it with k"). Never pass a frozen pane to
`kill_agent_pane_smart`.

The guard belongs at the kill site in `_launch_pick` (after the launch, right
before the kill), so it also covers `n`'s `_launch_pick_for_own` route. t2058
tracks that route's own missing frozen guard, and the two fixes should share this
check.

Regression tests (in `tests/test_minimonitor_pick_by_number.py`):
- live followed agent, kill ticked, snapshot flips to frozen between the confirm
  dialog and the launch result → no `kill_agent_pane_smart` call, a warning toast;
- control: stays live → still killed.

## Folded Tasks

The following existing tasks have been folded into this task. Their requirements are incorporated in the description above. These references exist only for post-implementation cleanup.

- **t2058** (`t2058_minimonitor_next_kills_frozen_standin_unleased.md`)
- **t2059** (`t2059_recheck_frozen_before_pick_kill.md`)
