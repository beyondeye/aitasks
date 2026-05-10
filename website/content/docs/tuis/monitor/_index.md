---
title: "Monitor"
linkTitle: "Monitor"
weight: 15
description: "tmux pane monitor and orchestrator TUI — the dashboard of the ait tmux IDE"
maturity: [stabilizing]
depth: [intermediate]
---

The `ait monitor` command launches an interactive TUI that shows every pane in the current tmux session, categorized as code agents, TUIs, or other panes, with a live preview of the focused pane and keystroke forwarding. It is the dashboard of the ait tmux-based development environment: from a single window you can watch agents work, jump to any other TUI, and interact with running processes without leaving the monitor.

{{< static-img src="imgs/home/monitor.svg" alt="Monitor TUI showing the pane list and live preview" caption="The ait monitor dashboard with categorized panes and live preview." >}}

## Tutorial

### Launching the Monitor

The recommended way to start monitor is via [`ait ide`]({{< relref "/docs/installation/terminal-setup" >}}):

```bash
ait ide
```

`ait ide` creates (or attaches to) the tmux session whose name is configured in `tmux.default_session` and opens a monitor window in one step. Because it always passes an explicit session name, it bypasses the [Session Rename Dialog](reference/#session-name-fallback-dialog).

To launch the monitor standalone from inside an existing tmux session:

```bash
ait monitor
```

If the current tmux session's name does not match the configured `tmux.default_session` and the configured session does not already exist, monitor offers to rename the current session. See [How to handle a session-name mismatch](how-to/#how-to-handle-a-session-name-mismatch) for details.

### Understanding the Layout

The monitor window has four stacked areas from top to bottom:

1. **Header** — application title bar
2. **Session bar** — shows the tmux session name monitor is watching and the current auto-switch state
3. **Pane list zone** — scrollable list of tmux panes grouped by category (agents, TUIs, others)
4. **Preview zone** — live rendering of the focused pane plus a content-header label; forwards keystrokes directly to tmux when focused
5. **Footer** — dynamic keybinding help

<!-- SCREENSHOT: Annotated monitor layout showing header, session bar, pane list, preview, and footer -->

The **pane list** classifies each tmux window in the session:

- **Agents** — windows whose names start with a configured agent prefix (default `agent-`). These are running code agents invoked via `ait codeagent`.
- **TUIs** — windows whose names are in the configured TUI list (board, codebrowser, settings, monitor, minimonitor, brainstorm, stats, syncer) or start with `brainstorm-`.
- **Others** — shells, logs, and any other tmux window.

Each card in the pane list shows the window name, category badge, an idle indicator (when the pane has been quiet longer than `idle_threshold_seconds`), and, for agent panes carrying a task ID in the window name, the task number.

The **preview zone** shows the content of the focused pane in real time. When you focus it, every keystroke you type is forwarded directly to the underlying tmux pane, so you can interactively control whatever is running there — answer an agent's question, run a shell command, scroll a log — without switching tmux windows.

### Navigating the Monitor

All navigation is keyboard-driven. Monitor uses a **zone model**: focus lives in either the pane list zone or the preview zone, and `Tab` cycles between them.

- **Tab** / **Shift+Tab** — Cycle focus between the pane list zone and the preview zone
- **Up** / **Down** — Move focus between cards in the pane list zone
- **Enter** (pane list zone) — Send an `Enter` keystroke to the focused tmux pane (useful to unblock an agent waiting for input without switching away)
- **Enter** (preview zone) — Send an `Enter` keystroke to the focused tmux pane, same as above
- Any other key in the **preview zone** — Forwarded to the tmux pane (characters, Ctrl-combinations, arrow keys, Escape, etc.)
- **q** — Quit the monitor

### Jumping to Another TUI

Press **j** from any zone to open the TUI switcher overlay. The overlay lists the TUIs that are integrated with the tmux workflow (board, monitor, minimonitor, codebrowser, settings, stats, brainstorm, syncer). Select one and monitor either focuses the existing tmux window running that TUI or creates a new window and launches it. This is the fastest way to move between the ait dashboard and any other TUI without leaving tmux.

When `aitask-data` or `main` falls behind origin, the monitor's session bar appends a compact desync summary (e.g., `· desync: aitask-data 3↓`). For an interactive surface that pulls/pushes/syncs the same refs, see the [Syncer]({{< relref "/docs/tuis/syncer" >}}).

<!-- SCREENSHOT: aitasks_tui_switcher_dialog.svg — the TUI switcher overlay as shown from monitor -->

For the complete list of keybindings and configuration options, see the [Reference](reference/).

---

**Next:** [How-To Guides](how-to/) — step-by-step flows. Or go straight to the [Reference](reference/) for keybindings and configuration.
