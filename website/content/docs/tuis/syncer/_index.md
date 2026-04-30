---
title: "Syncer"
linkTitle: "Syncer"
weight: 40
description: "TUI for tracking remote desync state of main and aitask-data"
maturity: [stabilizing]
depth: [intermediate]
---

`ait syncer` is a Textual TUI that surfaces remote desync state for the project's tracked branches and offers one-keystroke pull, push, and sync actions. It watches `main` and `aitask-data`, shows ahead/behind counts against `origin`, and falls through to a code-agent escape hatch when a sync action fails.

## Purpose

Cross-machine workflows accumulate divergence: another PC pushes commits to `origin/main`, a mobile session lands a task on `origin/aitask-data`, or a long-lived branch needs to be reconciled. The syncer makes that drift visible and resolvable without leaving tmux. Pair it with [monitor]({{< relref "/docs/tuis/monitor" >}}) and [minimonitor]({{< relref "/docs/tuis/minimonitor" >}}), which surface a compact one-line desync summary in their session bar fed by the same data helper.

## Launching

```bash
ait syncer                # manual launch
ait syncer --interval 60  # override the polling interval (seconds)
ait syncer --no-fetch     # offline mode — skip git fetch
```

`ait ide` can also launch a singleton `syncer` window automatically — see [`ait ide` autostart](#ait-ide-autostart) below.

## Layout

The syncer window stacks vertically:

1. **Header** — application title and a subtitle showing the current polling interval and fetch state (e.g., `interval=30s  fetch=on`).
2. **Branches table** — one row per tracked ref (`main`, `aitask-data`) with columns: Branch, Status, Ahead, Behind, Last refresh.
3. **Detail panel** — for the selected ref, lists the subjects of remote commits not yet pulled and the affected file paths.
4. **Footer** — dynamic keybinding hints.

## Polling and refresh

The syncer polls every 30 seconds by default. Each tick recomputes ahead/behind state for both refs, optionally running `git fetch` first.

| Key | Action |
|-----|--------|
| **r** | Refresh immediately |
| **f** | Toggle `git fetch` on/off (offline mode) |

The CLI flags `--interval SECS` and `--no-fetch` set the initial values; the `f` toggle changes the fetch state at runtime and the subtitle updates accordingly.

## Actions

| Key | Target ref | Action |
|-----|-----------|--------|
| **s** | `aitask-data` | Sync via `ait sync --batch` (auto-merges frontmatter conflicts) |
| **u** | `main` | Pull with `git pull --ff-only` |
| **p** | `main` | Push to `origin main:main` |
| **a** | (last failure) | Re-open the most recent failure modal |
| **q** | — | Quit |

The syncer scopes each action to the appropriate ref: `s` only operates on `aitask-data`, `u` and `p` only on `main`. Selecting a row and pressing the wrong key shows a notification rather than running the action.

The `u` action refuses to pull on a dirty working tree or when HEAD is not on `main`. The `s` action runs the same code path as the [`ait sync`]({{< relref "/docs/commands/sync" >}}) CLI in batch mode; if `aitask_merge.py` cannot resolve a conflict automatically, the syncer pushes a conflict-resolution screen that can hand off to interactive sync.

## Failure handling

When sync, pull, or push exits with an error, the syncer captures the command, status, and tail of the output and shows a modal:

- **Launch agent to resolve** — opens an `AgentCommandScreen` that dispatches a code agent in a sibling tmux pane (`agent-syncfix-<ref>`) with a prompt summarizing the failure. The agent is launched using the configured default model from [Settings]({{< relref "/docs/tuis/settings" >}}). Minimonitor auto-spawns alongside the agent pane.
- **Dismiss** — closes the modal. The most recent failure stays available via `a` so you can re-open it later.

## TUI switcher integration

Press **`y`** from any switcher-aware TUI ([board]({{< relref "/docs/tuis/board" >}}), [monitor]({{< relref "/docs/tuis/monitor" >}}), [minimonitor]({{< relref "/docs/tuis/minimonitor" >}}), [codebrowser]({{< relref "/docs/tuis/codebrowser" >}}), [settings]({{< relref "/docs/tuis/settings" >}}), brainstorm, syncer itself) to focus the existing `syncer` window or create a new one. The switcher modal also shows a one-line desync summary for the selected session — handy for spotting drift before you switch in.

## `ait ide` autostart

Set the `tmux.syncer.autostart` key in `aitasks/metadata/project_config.yaml` to have [`ait ide`]({{< relref "/docs/installation/terminal-setup" >}}) open a singleton `syncer` window alongside the `monitor` window:

```yaml
tmux:
  syncer:
    autostart: true
```

Default is `false` (key omitted, blank, or explicitly `false`). When enabled, `ait ide` creates the `syncer` window if one does not already exist; if a `syncer` window is already running in the session, it is reused.

## Relationship to `ait sync`

[`ait sync`]({{< relref "/docs/commands/sync" >}}) is the underlying CLI that the syncer's `s` action invokes in batch mode. The CLI is the single source of truth for the bidirectional task-data sync — auto-merge rules, network timeout, batch protocol, and exit codes are documented there. The syncer adds an interactive surface, the `main` pull/push actions, and the agent escape hatch on top.

## Configuration

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `tmux.syncer.autostart` | bool | `false` | When `true`, `ait ide` opens a singleton `syncer` window inside the project session. |

For the full `tmux.*` schema (default session, monitor cadence, agent prefixes, etc.) see the [Monitor reference]({{< relref "/docs/tuis/monitor/reference" >}}#configuration). The [Settings TUI]({{< relref "/docs/tuis/settings" >}}) → Tmux tab edits the same keys interactively.

---

**Next:** [Settings]({{< relref "/docs/tuis/settings" >}}) for editing the configuration, or back to [TUIs]({{< relref "/docs/tuis" >}}) for the full TUI list.
