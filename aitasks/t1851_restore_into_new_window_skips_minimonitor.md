---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [frozen, minimonitor]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
created_at: 2026-09-21 22:42
updated_at: 2026-09-22 23:43
---

## Problem

When a frozen agent is restored into a **new** window (its pane is gone, e.g. after a tmux server restart), the agent comes back alone. The minimonitor companion pane that normal agent launches get is not spawned.

Observed on 2026-09-21: restoring t1687_1 after a reboot (tmux session killed) produced an `agent-pick-1687_1` window with only the agent in it.

## Root cause (verified)

`agent_restore.py::_launch_into_new_window` calls `launch_in_tmux(..., TmuxLaunchConfig(new_window=True, ...))` and never calls `agent_launch_utils.maybe_spawn_minimonitor`, which the normal launch paths use for `agent-*` windows.

## Fix

- After a successful new-window restore/re-pick, call `maybe_spawn_minimonitor` for the new window (it already carries the `auto_spawn`, existing-minimonitor, and pane-count guards). Respect the "stamped agent pane" identity so the companion follows the restored agent, not itself.
- Same-pane restores (window survived) should keep whatever companion is already there and must not spawn a second one.
- The same applies to viewer windows recreated by the `ait ide` frozen-agent prompt (sibling task), if companions are wanted for frozen stand-ins.
- Add a test for the new-window branch: a companion is spawned; for the same-pane branch, no duplicate is spawned.
