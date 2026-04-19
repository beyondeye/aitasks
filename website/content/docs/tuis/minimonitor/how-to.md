---
title: "How-To Guides"
linkTitle: "How-To Guides"
weight: 10
description: "Task-oriented guides for using ait minimonitor"
---

### How Minimonitor Is Auto-Spawned

Minimonitor is meant to be auto-spawned — you almost never start it yourself. Every ait TUI that launches a new code agent window also creates a minimonitor split next to it:

- [`ait board`]({{< relref "/docs/tuis/board" >}}) — when you pick a task and launch its agent (action menu or agent command screen).
- [`ait codebrowser`]({{< relref "/docs/tuis/codebrowser" >}}) — when you launch an agent from a code file or the history screen.
- [`ait monitor`]({{< relref "/docs/tuis/monitor" >}}) — when you press **n** on an agent card to pick its next ready sibling task, which creates a new agent window.
- The TUI switcher's explore launch — when it creates an agent window for an explore target.

In every case the flow is the same: the launching TUI creates a new tmux window named `agent-...`, then the auto-spawn helper creates a horizontal right-split inside that window and runs `ait minimonitor` in it. The helper skips the split if the window name does not start with the configured agent prefix (default `agent-`) or if a monitor/minimonitor is already running in the window.

> **Auto-despawn:** minimonitor closes itself automatically when the agent pane it sits next to exits. On every refresh cycle it checks the panes in its own tmux window; the first refresh after the agent pane has gone (so there is no pane left other than minimonitor itself) triggers an `exit()` and the minimonitor pane closes. A 5-second grace period after startup prevents premature exit on cold launch. You never need to `ait minimonitor` after an agent finishes — a new one will spawn with the next agent you launch.

### How to Start Minimonitor Manually

Manual launch is an escape hatch for edge cases (an agent pane you started by hand, a killed sidebar you want to bring back). From inside a tmux session, run:

```bash
ait minimonitor
```

This starts minimonitor in the current tmux pane.

> **Single-instance guard:** `ait minimonitor` checks the current tmux **window** for any existing monitor or minimonitor process. If one is already running in the same window, the new invocation prints a short message and exits. The guard is per-window, so you can still have minimonitor split alongside each of several agent windows in the same session.

### How to Read the Agent List

Minimonitor shows a single scrollable list of **agent panes** (windows whose names match the configured agent prefix — default `agent-`). TUIs, shells, and other panes are deliberately filtered out; for the full categorized view use [`ait monitor`]({{< relref "/docs/tuis/monitor" >}}).

Each card in the list shows:

- A status dot: **green** when the agent has produced recent output, **yellow** when it is idle
- The agent window name (truncated to 22 characters on narrow layouts)
- An `IDLE <n>s` label when the pane has been quiet longer than `tmux.monitor.idle_threshold_seconds` (default 5 seconds)
- For agents whose window name carries a task ID, a second dimmed line showing the task's title

The session name and the running/idle count are shown in a compact header bar at the top of the pane.

### How to Navigate the Agent List

- **Up** / **Down** — Move focus between agent cards within the list.
- The footer hint summarizes the navigation and action keys for the current layout.

When minimonitor is shown as a side split next to an agent, it auto-selects the card for that agent whenever the minimonitor pane regains terminal focus — so the focused card always reflects the neighbor you are working with, unless you explicitly moved focus somewhere else.

### How to Focus the Sibling Agent Pane

Minimonitor is designed to live beside an agent pane in the same tmux window. Pressing **Tab** moves **tmux focus** to that sibling pane (the first non-minimonitor pane in the same window), so your next keystrokes go directly to the agent. This is the fastest way to jump from glancing at the status sidebar to typing into the agent it sits next to.

If minimonitor is the only pane in its window (no sibling to target), Tab shows a notification and does nothing.

### How to Send Enter to the Sibling Agent

When a code agent is waiting for you to press Enter (for example, it just asked a clarifying question), you can unblock it without moving tmux focus:

1. Make sure minimonitor has terminal focus
2. Press **Enter**

Minimonitor sends a single `Enter` keystroke to the sibling pane via `tmux send-keys`. Tmux focus stays on minimonitor, so you can keep watching the agent status while it processes the input.

### How to Switch to the Selected Agent

To jump your tmux session focus to the **selected** card's agent (which may be in a different window from the minimonitor you're in):

1. Focus the agent's card with Up/Down
2. Press **s**

Minimonitor asks tmux to switch focus to the agent's window (preferring the companion pane when the card is next to its own minimonitor). A notification confirms the switch.

### How to Show Task Info for an Agent

For agent panes whose window name carries a task ID (e.g., `agent-t42-claudecode`), minimonitor can open the same task detail dialog used by the other TUIs:

1. Focus the agent's card with Up/Down
2. Press **i**

The task cache is refreshed and the task detail dialog appears with the task's metadata and content. If the focused card has no task ID in its window name, a warning notification is shown instead.

### How to Jump to Another TUI

Press **j** to open the TUI switcher overlay. The overlay lists the TUIs integrated with the tmux workflow:

- **board** — `ait board`
- **monitor** — `ait monitor`
- **minimonitor** — `ait minimonitor` (the current TUI)
- **codebrowser** — `ait codebrowser`
- **settings** — `ait settings`
- **brainstorm** — `ait brainstorm`

Select a target and the switcher focuses the existing tmux window running that TUI or creates a new window and launches it.

<!-- SCREENSHOT: aitasks_tui_switcher_dialog.svg — the TUI switcher overlay as shown from minimonitor -->

### How to Refresh the Agent List

Press **r** to force an immediate refresh of the agent list. Minimonitor also refreshes automatically every `tmux.monitor.refresh_seconds` seconds (default 3), so manual refresh is only needed when you want an immediate update.

### How to Quit

Press **q** to quit minimonitor manually. The pane running minimonitor closes; the rest of your tmux session is unaffected. Because auto-despawn already closes minimonitor whenever its companion agent exits, manual quit is mainly useful when you want to reclaim the sidebar column while the agent is still running.

### Pairing Minimonitor with Monitor

Minimonitor and monitor are complementary and can run side by side. A productive layout looks like this:

- **Window 0 — `monitor`:** full dashboard via `ait monitor` (or `ait ide`), with pane list, preview, and all controls.
- **Window 1 — `agent-t42-...`:** a code agent window. Split horizontally so that the **left pane** runs the agent and the **right pane** runs minimonitor.
- **Window 2 — `agent-t43-...`:** another agent window with its own minimonitor split.
- **Window 3+ — other TUIs:** board, codebrowser, settings, brainstorm, all reachable from any monitor via `j`.

From any of the agent windows, Tab jumps into the code agent pane and j opens the TUI switcher to hop back to the full monitor dashboard. From monitor, `s` on an agent card brings you to the companion minimonitor alongside it. See [How to Switch tmux to the Focused Pane](../monitor/how-to/#how-to-switch-tmux-to-the-focused-pane) in the monitor docs for the reverse direction.

### Configuring Auto-Spawn

Auto-spawn (from board, codebrowser, monitor's next-sibling launch, and the TUI switcher's explore launch) is controlled by two keys in `aitasks/metadata/project_config.yaml`:

```yaml
tmux:
  minimonitor:
    auto_spawn: true   # set to false to disable automatic side splits
    width: 40          # width (in columns) of the minimonitor side pane
```

You can edit these directly, or use [`ait settings`]({{< relref "/docs/tuis/settings" >}}) → Tmux tab, which writes the same keys.

### Key Bindings Quick Reference

| Key | Action |
|-----|--------|
| `Up` / `Down` | Move focus between agent cards |
| `Tab` | Move tmux focus to the sibling pane in this window |
| `Enter` | Send an `Enter` keystroke to the sibling pane |
| `s` | Switch tmux focus to the selected agent's window |
| `i` | Show task info for the selected agent |
| `j` | Open the TUI switcher |
| `r` | Refresh the agent list |
| `q` | Quit minimonitor |

Minimonitor inherits config keys (`tmux.default_session`, `tmux.monitor.refresh_seconds`, `tmux.monitor.idle_threshold_seconds`, `tmux.monitor.capture_lines`, `tmux.monitor.agent_window_prefixes`, `tmux.monitor.tui_window_names`) from the same `project_config.yaml` section monitor uses — see the [monitor reference]({{< relref "/docs/tuis/monitor/reference" >}}#configuration) for the full list.

---

**Next:** [Code Browser]({{< relref "/docs/tuis/codebrowser" >}}) — review diffs with task-aware annotations.
