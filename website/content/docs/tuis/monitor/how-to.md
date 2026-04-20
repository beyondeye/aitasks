---
title: "How-To Guides"
linkTitle: "How-To Guides"
weight: 10
description: "Task-oriented guides for using ait monitor"
---

### How to Start the Monitor

**Recommended — via `ait ide`:**

```bash
ait ide
```

This is the one-command path to the ait tmux IDE. `ait ide` resolves the tmux session name from `tmux.default_session` in `project_config.yaml` (defaulting to `aitasks`), creates or attaches to that session, and opens a `monitor` window inside it. Because it always passes an explicit session name, the [session-rename dialog](reference/#session-name-fallback-dialog) never fires.

**Standalone — from inside an existing tmux session:**

```bash
ait monitor
```

Run this from within a tmux session you already have open. Monitor attaches to the current session.

> **Note:** If you launched tmux without specifying a session name (or with a name that does not match `tmux.default_session`), monitor offers to rename the session on startup. See [How to handle a session-name mismatch](#how-to-handle-a-session-name-mismatch).

### How to Read the Pane List

The pane list zone groups the tmux session's windows into three categories:

- **Agents** — windows whose names start with a configured agent prefix (default `agent-`). These are running code agents started via `ait codeagent`. When the window name contains a task ID (e.g., `agent-t42-<...>`), the card shows the task number.
- **TUIs** — windows whose names are in the configured TUI list (board, codebrowser, settings, monitor, minimonitor, brainstorm), or whose names start with `brainstorm-`.
- **Others** — shells, logs, and anything else.

Each card shows:

- Window name and category badge
- An **idle indicator** when the pane has not produced new output for longer than `tmux.monitor.idle_threshold_seconds` (default 5 seconds)
- For agent panes carrying a task ID in the window name, the associated task number

Classification rules are config-driven — you can change the agent prefixes and the TUI list by editing `aitasks/metadata/project_config.yaml` directly or via [`ait settings`]({{< relref "/docs/tuis/settings" >}}) → Tmux tab. See the [Reference](reference/#pane-classification) for details.

### How to Navigate Between Zones

Monitor uses a zone model with two zones: the pane list and the preview.

1. Press **Tab** to move focus from the pane list to the preview, or vice versa. **Shift+Tab** cycles in the opposite direction.
2. In the **pane list zone**, **Up** and **Down** move focus between cards.
3. Whenever you focus a card, the preview updates to show that pane's live content.

The active zone is reflected in the widget borders and the footer.

### How to Interact with a Pane From the Preview

The preview zone is not a passive viewer — when it has focus, every keystroke is forwarded to the focused tmux pane in real time. This lets you interact with whatever is running in the pane (a code agent, a shell, a TUI) without switching tmux windows.

1. Focus the pane you want to interact with in the pane list (Up/Down)
2. Press **Tab** to move focus into the preview zone
3. Type normally — characters, Ctrl-combinations, arrow keys, and Escape are all forwarded
4. Press **Tab** again to return focus to the pane list

> **Note:** Pressing **Enter** while the pane list zone is focused also sends an `Enter` keystroke to the focused pane. This is a shortcut for unblocking agents that are waiting for input, without having to move into the preview zone first.

### How to Send Enter to a Blocked Agent

A common workflow pattern: an agent has asked a clarifying question and is waiting for you to press Enter to continue (for example, after an `/aitask-pick` prompt).

1. Focus the agent's card in the pane list zone
2. Press **Enter**

This sends a single `Enter` keystroke to that pane via `tmux send-keys` without moving focus into the preview zone. A delayed refresh then updates the preview so you can see the agent's response.

### How to Switch tmux to the Focused Pane

To move your tmux focus to the pane you are currently previewing (so that your next keystrokes go there natively):

1. Focus the pane's card in the pane list
2. Press **s**

Monitor calls `tmux switch-client`/`select-window` to bring that pane to the front. A notification confirms the switch.

### How to Jump to Another TUI

Press **j** from any zone to open the TUI switcher overlay. The overlay lists the TUIs integrated with the tmux workflow:

- **board** — `ait board`
- **monitor** — `ait monitor` (the current TUI)
- **minimonitor** — the minimal monitor variant
- **codebrowser** — `ait codebrowser`
- **settings** — `ait settings`
- **brainstorm** — `ait brainstorm`

Select a target and the switcher either focuses the existing tmux window running that TUI or creates a new window and launches it. This is the fastest way to move between the monitor dashboard and any other ait TUI without leaving tmux.

<!-- SCREENSHOT: aitasks_tui_switcher_dialog.svg — the TUI switcher overlay as shown from monitor -->

### How to Show Task Info for an Agent Pane

For agent panes whose window name carries a task ID (e.g., `agent-t42-claudecode`), you can open the full task detail dialog directly from the monitor:

1. Focus the agent's card in the pane list
2. Press **i**

Monitor refreshes the task cache and opens the same task detail dialog used by [`ait board`]({{< relref "/docs/tuis/board" >}}), showing the task's metadata, lock status, and content.

### How to Kill a Pane

To terminate a tmux pane from monitor:

1. Focus the pane's card
2. Press **k**
3. A confirmation dialog appears showing the window name and, if it is an agent pane, the associated task information
4. Confirm the kill

Monitor calls `tmux kill-pane` and refreshes the pane list.

### How to Pick the Next Sibling Task

When an agent pane finishes a child task, you can have monitor suggest and launch the next ready sibling without leaving the window:

1. Focus the agent's card (it must carry a task ID in the window name)
2. Press **n**
3. A dialog appears showing the current task and the suggested next sibling (or child) — confirm to launch it

Monitor resolves the next ready sibling via the task cache and starts a new agent window for the chosen target using the standard pick workflow.

### How to Cycle the Preview Size

Press **z** to cycle the preview zone through six size presets — **S**, **M**, **L**, **XL_9**, **XL_6**, **XL_3** — for quickly adjusting how much pane output vs. agent-list you see at once. The `S/M/L` presets set a fixed preview height; the `XL_N` presets size the pane-list to fit N agents and give the rest of the screen to the preview. A notification shows the new size label. The default is **M**.

### How to Refresh the Pane List

Press **r** (or **F5**) to force an immediate refresh of the pane list and preview content. Monitor also refreshes automatically every `tmux.monitor.refresh_seconds` seconds (default 3), so manual refresh is only needed when you want an immediate update.

### How to Toggle Auto-Switch Mode

Press **a** to toggle auto-switch mode. When auto-switch is **on**, monitor automatically focuses idle agent panes that appear to be waiting for attention, so you don't have to scan the pane list manually. Press **a** again to turn it off. The session bar shows the current state.

### How to Quit

Press **q** to quit monitor. The tmux window running monitor closes; the rest of your tmux session is unaffected.

### How to Handle a Session-Name Mismatch

Monitor expects the current tmux session name to match `tmux.default_session` from `project_config.yaml`. If the names do not match and the configured session does not already exist, monitor opens the Session Rename Dialog on startup, offering to rename the current tmux session to the configured name.

**Recommended fix:** launch monitor via `ait ide`, which always passes an explicit session name and bypasses the dialog entirely.

**Manual workaround:** rename the session yourself before launching monitor:

```bash
tmux rename-session -t "$OLD" "$NEW"
ait monitor
```

See the [Session-name fallback dialog](reference/#session-name-fallback-dialog) in the reference for the full decision logic.

---

**Next:** [Reference](../reference/) — full keybinding list, configuration keys, and internals.
