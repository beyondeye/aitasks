---
title: "Feature Reference"
linkTitle: "Reference"
weight: 20
description: "Keyboard shortcuts, configuration, and technical details for ait monitor"
---

### Keyboard Shortcuts

#### Zone Navigation

| Key | Action | Context |
|-----|--------|---------|
| `Tab` | Cycle focus to the next zone (pane list ↔ preview) | Global |
| `Shift+Tab` | Cycle focus to the previous zone | Global |
| `Up` | Focus the previous card in the pane list | Pane list zone |
| `Down` | Focus the next card in the pane list | Pane list zone |
| `q` | Quit monitor | Global |

#### Pane Interaction

| Key | Action | Context |
|-----|--------|---------|
| `Enter` | Send an `Enter` keystroke to the focused tmux pane | Pane list zone |
| `Enter` | Send an `Enter` keystroke to the focused tmux pane | Preview zone |
| Any other key | Forwarded to the focused tmux pane (characters, Ctrl-combos, arrows, Escape) | Preview zone |
| `s` | Switch tmux focus to the focused pane (`tmux switch-client`) | Pane list zone |
| `i` | Show the task detail dialog for the focused agent pane (requires a task ID in the window name) | Pane list zone |
| `k` | Kill the focused pane after confirmation (`tmux kill-pane`) | Pane list zone |
| `n` | Pick the next ready sibling task for the focused agent pane | Pane list zone |
| `R` | Restart the task running in the focused agent pane | Pane list zone |
| `L` | Open the log for the focused pane in a separate viewer | Pane list zone |

#### Monitor Controls

| Key | Action | Context |
|-----|--------|---------|
| `j` | Open the TUI switcher overlay | Global |
| `r` | Refresh the pane list and preview immediately | Global |
| `F5` | Refresh the pane list and preview immediately (alias for `r`, hidden in footer) | Global |
| `z` | Cycle the preview size through S / M / L presets | Global |
| `b` | Toggle the preview scrollbar visibility | Global |
| `t` | Scroll the preview to its tail (newest output) | Global |
| `a` | Toggle auto-switch mode (automatically focus idle agents needing attention) | Global |

> **Note:** In the preview zone, every keystroke that is not handled by a global binding is forwarded to the tmux pane via `tmux send-keys`. Special keys (Enter, Escape, Backspace, arrows, Space, Delete, Home, End, PageUp/Down) and Ctrl-combinations are translated; regular characters are sent literally.

### Zone Model

Monitor uses a two-zone model. Focus lives in one of:

| Zone | Widget | Behavior |
|------|--------|----------|
| `PANE_LIST` | `VerticalScroll` of `PaneCard` widgets | Up/Down navigate between cards; Enter sends an `Enter` keystroke to the focused pane |
| `PREVIEW` | `PreviewPanel` inside a `ScrollableContainer` | All non-bound keys are forwarded to the focused pane; a fast-refresh timer (300 ms) updates the preview while this zone is active |

`Tab` and `Shift+Tab` cycle between these zones. The active zone is reflected in the widget borders and in the content-header label above the preview.

### Pane Classification

`discover_panes()` in `tmux_monitor.py` categorizes every window in the monitored tmux session:

| Category | Rule |
|----------|------|
| **Agent** | Window name starts with any prefix listed in `tmux.monitor.agent_window_prefixes` (default `agent-`) |
| **TUI** | Window name is in `tmux.monitor.tui_window_names`, OR starts with `brainstorm-` |
| **Other** | Anything that does not match the rules above (shells, logs, ad-hoc windows) |

Agent panes whose window name contains a task ID (e.g., `agent-t42-claudecode`) are linked to the corresponding task file — that is what powers the `i` (Task Info) and `n` (Next Sibling) shortcuts.

### Preview Size Presets

Pressing `z` cycles through three preview size presets:

| Label | Section max height | Preview max height |
|-------|-------------------|--------------------|
| `S` | 12 | 10 |
| `M` (default) | 24 | 22 |
| `L` | 40 | 38 |

A notification shows the new size label when you cycle.

### Configuration

Monitor reads its configuration from `aitasks/metadata/project_config.yaml`. The relevant keys live under `tmux` and `tmux.monitor`:

```yaml
tmux:
  default_session: aitasks
  default_split: horizontal
  prefer_tmux: true
  git_tui: lazygit
  monitor:
    refresh_seconds: 3
    idle_threshold_seconds: 5
    capture_lines: 200
    agent_window_prefixes:
      - agent-
    tui_window_names:
      - board
      - codebrowser
      - settings
      - brainstorm
      - monitor
      - minimonitor
```

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `tmux.default_session` | string | `aitasks` | Expected tmux session name. Monitor matches the current session against this and offers to rename if they differ. |
| `tmux.default_split` | string | `horizontal` | How new panes are split when TUIs are launched from the switcher. |
| `tmux.prefer_tmux` | bool | `true` | Whether tmux-based workflows are the default for related commands. |
| `tmux.git_tui` | string | `lazygit` | Which git TUI the switcher targets for git windows. |
| `tmux.monitor.refresh_seconds` | int | `3` | Pane list refresh cadence in seconds. |
| `tmux.monitor.idle_threshold_seconds` | int | `5` | Threshold for marking a pane as idle in the card view. |
| `tmux.monitor.capture_lines` | int | `200` (in the shipped config; `30` if the key is absent) | Number of lines of pane output the preview captures per refresh. |
| `tmux.monitor.agent_window_prefixes` | list | `["agent-"]` | Window-name prefixes that classify a pane as an agent. |
| `tmux.monitor.tui_window_names` | list | board, codebrowser, settings, brainstorm, monitor, minimonitor | Window names classified as TUIs. `brainstorm-*` prefix matches are handled in addition to this list. |

All of these can be edited interactively via [`ait settings`]({{< relref "/docs/tuis/settings" >}}) → Tmux tab, which writes the same keys in `project_config.yaml`.

### Command-line Options

`ait monitor` is a thin wrapper around `monitor_app.py`. The underlying script accepts:

| Option | Default | Purpose |
|--------|---------|---------|
| `--session NAME` | Current tmux session | Explicit tmux session name to watch (bypasses auto-detection) |
| `--interval SECS` | `tmux.monitor.refresh_seconds` | Override the pane list refresh cadence |
| `--lines N` | `tmux.monitor.capture_lines` | Override the number of lines captured for previews |

`ait ide` always passes `--session` with the configured default, which is why it never triggers the Session Rename Dialog.

### Session-Name Fallback Dialog

When monitor starts, it resolves which tmux session to watch using this decision logic:

1. If `--session NAME` was passed on the command line, use that name.
2. Otherwise, detect the current tmux session name from `$TMUX`.
3. Compare the detected name against `tmux.default_session` from `project_config.yaml`.
4. If the names match, proceed normally.
5. If they differ **and** the configured session does not already exist, open the `SessionRenameDialog` offering to rename the current session to the configured name.
6. If they differ **and** the configured session exists, proceed watching the current session without prompting.

**When the dialog fires:** inside a tmux session whose name does not match the configured default (typical when you ran `tmux` without `-s NAME`).

**What the dialog does:** offers a one-click rename of the current session to the configured name; you can also dismiss the dialog to keep the current name.

**How to avoid it:**

- Launch monitor via [`ait ide`]({{< relref "/docs/workflows/tmux-ide" >}}), which always passes an explicit session name.
- Manually rename the session before launching monitor: `tmux rename-session -t "$OLD" "$NEW"`.

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `TMUX` | Set by tmux when inside a session. Monitor reads it to detect the current session name. Without it, monitor refuses to launch outside of a tmux context. |
| `PYTHON` | Optional override for the Python interpreter used by the launcher (defaults to the shared `ait setup` venv). |

### Related Commands and TUIs

| Command / TUI | Purpose | Reference |
|---------------|---------|-----------|
| `ait ide` | One-command launcher that starts/attaches to the configured tmux session and opens monitor | [tmux IDE workflow]({{< relref "/docs/workflows/tmux-ide" >}}) |
| `ait board` | Kanban board for task management — target of the TUI switcher | [Board]({{< relref "/docs/tuis/board" >}}) |
| `ait codebrowser` | Code browser TUI — target of the TUI switcher | [Code Browser]({{< relref "/docs/tuis/codebrowser" >}}) |
| `ait settings` | Settings TUI — target of the TUI switcher; also hosts the Tmux tab for editing the configuration above | [Settings]({{< relref "/docs/tuis/settings" >}}) |

---

**Next:** [Minimonitor](../../minimonitor/) — the narrow sidebar variant of monitor.
