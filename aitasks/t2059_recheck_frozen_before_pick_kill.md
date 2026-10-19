---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [minimonitor, monitor, frozen_agents]
anchor: 2049
followup_kind: risk_mitigation
created_at: 2026-10-19 12:13
updated_at: 2026-10-19 12:13
---

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
