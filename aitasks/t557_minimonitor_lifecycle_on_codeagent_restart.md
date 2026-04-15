---
priority: medium
effort: medium
depends: [556]
issue_type: refactor
status: Ready
labels: [aitask_monitor]
created_at: 2026-04-15 10:48
updated_at: 2026-04-15 11:16
boardidx: 10
---

## Context

Raised while implementing t556 (task restart action in ait monitor TUI).

When multiple code agents are spawned in the same tmux window (e.g., via the new "R" restart action or via "n" pick-next-sibling), the minimonitor companion pane lifecycle is under-specified:

- `maybe_spawn_minimonitor` (`.aitask-scripts/lib/agent_launch_utils.py:213`) splits the current agent window with a minimonitor pane. The function only checks whether a monitor/minimonitor pane already exists in the window; it assumes one-agent-per-window.
- `TmuxMonitor.kill_pane` (`.aitask-scripts/monitor/tmux_monitor.py:413`) kills only the agent pane. If the same window has an associated minimonitor pane, the minimonitor pane (and the window) survive.
- `kill_window` (added in t556) kills the whole window — safe for the restart case where the old window is replaced by a new one with the same name, but overly aggressive if multiple agent panes coexist in a single window.

## Problems to investigate

1. **Multiple agents per window.** Can `AgentCommandScreen` + `launch_in_tmux` actually place two agent panes in the same window today? Review `TmuxLaunchConfig` (`agent_launch_utils.py:32`) — new_session / new_window / split — to enumerate the paths.
2. **Minimonitor cleanup on "n" (pick next sibling).** The existing Done/parent-with-children branch in `_on_next_sibling_result` (`monitor_app.py:1384-1391`) calls `kill_pane`, leaving a potential orphan minimonitor pane + window.
3. **Window-name ambiguity.** `maybe_spawn_minimonitor` resolves a window by **first-matching name** (`agent_launch_utils.py:258-263`). If two windows share the same `agent-pick-<N>` name (which happens whenever the old window has not been torn down before a new launch), the minimonitor is attached to the wrong window. t556 side-stepped this by using `kill_window` before launch; sibling flows may still be affected.
4. **Detection rule.** Define when to kill an orphaned minimonitor: should it be "no agent panes remain in the window"? Who enforces it — `TmuxMonitor` on next refresh, or the callback that killed the agent pane?

## Expected output

- A short write-up of the actual failure modes (repro or proof-by-code-reading).
- A concrete rule for minimonitor lifecycle (e.g., "when the last agent pane in a window dies, kill the minimonitor pane too") and where to enforce it.
- Patches for the identified callers (at minimum: `_on_next_sibling_result` and any future restart variants).
