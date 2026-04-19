---
title: "Minimonitor"
linkTitle: "Minimonitor"
weight: 17
description: "Compact sidebar variant of the ait monitor TUI for watching code agents"
---

`ait minimonitor` is a narrow (~40 column) sidebar TUI that lists the code agents running in the current tmux session, with idle indicators and a companion-pane focus model. It is the agents-only cousin of [`ait monitor`]({{< relref "/docs/tuis/monitor" >}}): no preview panel, no TUI/other pane categories — just the running agents in a compact column designed to sit next to a code pane while you work.

Minimonitor is **meant to be auto-spawned** alongside every code agent you launch from the ait TUIs. You rarely need to start it yourself — whenever a new agent window is created, the launching TUI also splits a minimonitor pane next to it, and minimonitor closes itself automatically when the agent pane exits. Manual launch via `ait minimonitor` is supported but is an escape hatch rather than the primary workflow.

<!-- SCREENSHOT: aitasks_minimonitor_main_view.svg — minimonitor running as a right-side split alongside an agent pane -->

## Purpose

Minimonitor is the persistent sidebar companion of a code agent pane. It gives you an at-a-glance status view of all running agents in the session without giving up screen real estate to the full monitor dashboard, so you can keep watching the agent next to you (and all the others) while you stay focused on the agent's output.

## Relationship to monitor

| Aspect | `ait monitor` | `ait minimonitor` |
|--------|---------------|-------------------|
| Width | Full window | ~40 columns (configurable) |
| Shows agents | Yes | Yes |
| Shows TUIs and other panes | Yes | No |
| Preview zone with keystroke forwarding | Yes | No |
| Intended placement | Its own tmux window | A side split inside an agent window |
| TUI switcher (`j`) | Yes | Yes |

The two can coexist in the same tmux session — a typical layout has monitor in its own window as a dashboard, and minimonitor split alongside each agent pane. See [Pairing minimonitor with monitor](how-to/#pairing-minimonitor-with-monitor) in the how-to for details.

## Auto-spawn and auto-despawn

Minimonitor's lifecycle is tied to the agent pane it sits next to — every agent window you launch from an ait TUI gets a minimonitor split alongside it, and that minimonitor closes itself when the agent pane exits. You don't manage minimonitors explicitly; they appear and disappear with the agents they track.

**Where auto-spawn fires:** any TUI that can launch a new code agent window also spawns a minimonitor split next to it:

- [`ait board`]({{< relref "/docs/tuis/board" >}}) — when you pick a task and launch its agent (from the action menu or the agent command screen).
- [`ait codebrowser`]({{< relref "/docs/tuis/codebrowser" >}}) — when you launch an agent from a code file or from the history screen.
- [`ait monitor`]({{< relref "/docs/tuis/monitor" >}}) — when you press `n` on an agent card to pick its next ready sibling task, which creates a new agent window.
- The [TUI switcher](../monitor/how-to/#how-to-jump-to-another-tui) — when it creates an agent window for an explore target.

All of these call the same auto-spawn helper. It only acts when:

- The new window name starts with `agent-` (the default agent prefix).
- No monitor or minimonitor pane is already running in that window.

**Auto-despawn:** minimonitor polls the panes in its own tmux window on every refresh cycle. As soon as there is no longer any pane other than minimonitor itself — typically because the code agent has finished and its pane exited — minimonitor calls `exit()` and the split pane closes. A 5-second grace period after startup prevents premature exit on cold launch. The net effect is that the sidebar appears when the agent starts and disappears when the agent finishes, without any manual cleanup.

Auto-spawn is controlled by `tmux.minimonitor.auto_spawn` (default `true`) and `tmux.minimonitor.width` (default `40` columns) in `project_config.yaml`; see the [how-to](how-to/#configuring-auto-spawn) for details.

## When to launch manually

Because auto-spawn is the primary mode, manual `ait minimonitor` invocations are rare. Reach for them only when:

- You want a status sidebar in a window that was not created by an ait TUI (e.g., you started an agent pane by hand).
- You killed a minimonitor split and want to bring it back without restarting the agent.
- You are experimenting with a layout where minimonitor sits alongside a non-agent pane.

For a full dashboard with previews, pane classification, and kill/switch controls, use [monitor](../monitor/) instead.

---

**Next:** [How-To Guides](how-to/) — layouts and launch recipes for the narrow sidebar.
