---
title: "Syncer"
linkTitle: "Syncer"
weight: 40
description: "TUI for tracking remote desync state of main and aitask-data"
maturity: [stabilizing]
depth: [intermediate]
---

`ait syncer` is a Textual TUI that surfaces remote desync state for the tracked branches of **every discovered aitasks repo** and offers one-keystroke pull, push, and sync actions. It watches `main` and `aitask-data` per repo, shows ahead/behind counts against `origin`, and falls through to a code-agent escape hatch when a sync action fails. With a single repo it shows just that repo's two branches; when two or more repos are discovered — live tmux sessions plus the [cross-repo project registry]({{< relref "/docs/workflows/multi_project" >}}) — the table gains a Project column with one row per repo × branch, and actions target the highlighted row's repo.

> **Customizable keys:** every shortcut here can be rebound. Press `?` in this
> TUI for the in-place editor, or open
> [Settings → Shortcuts]({{< relref "/docs/tuis/settings#shortcuts-s" >}}).

## Purpose

Cross-machine workflows accumulate divergence: another PC pushes commits to `origin/main`, a mobile session lands a task on `origin/aitask-data`, or a long-lived branch needs to be reconciled. The syncer makes that drift visible and resolvable without leaving tmux — across all of your registered projects from one place, so you can spot and fix a lagging repo without switching sessions. Pair it with [monitor]({{< relref "/docs/tuis/monitor" >}}) and [minimonitor]({{< relref "/docs/tuis/minimonitor" >}}), which surface a compact one-line desync summary in their session bar fed by the same data helper.

## Launching

```bash
ait syncer                # manual launch
ait syncer --interval 30  # override the automatic refresh interval (seconds)
ait syncer --no-fetch     # offline mode — skip git fetch
```

`ait ide` can also launch a singleton `syncer` window automatically — see [`ait ide` autostart](#ait-ide-autostart) below.

## Layout

The syncer window stacks vertically:

1. **Header** — application title and a subtitle showing the repo count (multi-repo mode), the refresh interval, and the fetch state (e.g., `repos=3  interval=60s  fetch=on`).
2. **Branches table** — one row per repo × tracked ref (`main`, `aitask-data`). Multi-repo columns: Project, Branch, Status, Ahead, Behind, Fetched (age since that repo's last successful fetch, e.g. `32s`, `5m`, `—` if never). With a single repo the Project column is omitted and the last column shows the wall-clock time of the last refresh, as before.
3. **Detail panel** — for the selected row (project + ref in multi-repo mode), lists the subjects of remote commits not yet pulled and the affected file paths.
4. **Footer** — dynamic keybinding hints.

In multi-repo mode the repo you launched from is always listed first, even if it is not in the registry. Repos sharing a name are disambiguated with a compact path suffix.

## Polling and refresh

The syncer refreshes automatically every 60 seconds by default. To keep network traffic bounded with many repos, each tick runs `git fetch` for **one** repo — the one whose last successful fetch is oldest (never-fetched repos first) — while every repo's ahead/behind state is recomputed from local git data. The **Fetched** column shows each repo's age since its last successful fetch, so you can always see how current a row is. With a single repo, every tick fetches it, matching the classic behavior.

| Key | Action |
|-----|--------|
| **r** | Refresh now — fetches the highlighted row's repo immediately |
| **f** | Toggle `git fetch` on/off (offline mode) |

A manual `r` also pushes that repo to the back of the automatic fetch queue (the scheduler simply picks whichever repo is least recently fetched). The CLI flags `--interval SECS` and `--no-fetch` set the initial values; the `f` toggle changes the fetch state at runtime and the subtitle updates accordingly. With fetch off, all state is local-only and the Fetched ages keep growing.

## Mouse Support

The Syncer TUI supports full mouse interaction in addition to the keyboard shortcuts:

- **Click a row in the Branches table** — select that ref (mirrors ↑ / ↓ navigation).
- **Scroll wheel** — scroll the detail panel and table content.
- **Click failure-modal buttons** — both **Launch agent to resolve** and **Dismiss** are clickable.

All keyboard actions documented below remain available.

## Actions

Actions always target the **highlighted row's repo** — highlight another project's `aitask-data` row and press `s` to sync that repo without leaving the TUI.

| Key | Target ref | Action |
|-----|-----------|--------|
| **s** | `aitask-data` | Sync via that repo's `ait sync --batch` (auto-merges frontmatter conflicts) |
| **u** | `main` | Pull with `git pull --ff-only` in that repo |
| **p** | `main` | Push to `origin main:main` from that repo |
| **a** | (last failure) | Re-open the most recent failure modal |
| **q** | — | Quit |

The syncer scopes each action to the appropriate ref: `s` only operates on `aitask-data` rows, `u` and `p` only on `main` rows — the footer hints follow the highlighted row. Before running anything, the syncer verifies the target repo still resolves (and, for pull/push, that a status snapshot exists so the branch is derived from the right repo); failures surface as a notification naming the project. There is no batch fan-out: each action affects exactly one repo.

The `u` action refuses to pull on a dirty working tree or when HEAD is not on `main`. The `s` action runs the same code path as the [`ait sync`]({{< relref "/docs/commands/sync" >}}) CLI in batch mode; if `aitask_merge.py` cannot resolve a conflict automatically, the syncer pushes a conflict-resolution screen that can hand off to interactive sync.

## Failure handling

When sync, pull, or push exits with an error, the syncer captures the command, status, and tail of the output and shows a modal:

- **Launch agent to resolve** — opens an `AgentCommandScreen` that dispatches a code agent in a sibling tmux pane (`agent-syncfix-<action>`) with a prompt summarizing the failure. The agent is rooted in the repo the failed action targeted and launched using the configured default model from [Settings]({{< relref "/docs/tuis/settings" >}}). Minimonitor auto-spawns alongside the agent pane.
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
