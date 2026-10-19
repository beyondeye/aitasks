---
priority: low
effort: low
depends: []
issue_type: bug
status: Ready
labels: [minimonitor, monitor, frozen_agents]
anchor: 2049
followup_kind: review_finding
created_at: 2026-10-19 11:16
updated_at: 2026-10-19 11:16
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
