---
title: "The IDE model"
linkTitle: "The IDE model"
weight: 120
description: "How ait ide turns tmux into a navigable agentic IDE around the monitor TUI."
---

## What it is

The aitasks **IDE** is a tmux session organized by **window-naming convention**, not a fixed layout. The framework reserves a small set of window names — `monitor`, `board`, `codebrowser`, `settings`, `brainstorm`, plus an `agent-<n>` prefix for code agent windows — and the integrated TUIs all look up tmux windows by these names. Open, close, rearrange, or split them however you like; what matters is the name.

The [Monitor TUI]({{< relref "/docs/tuis/monitor" >}}) acts as the conventional home screen, listing every code agent and TUI window in the session with a live preview and keystroke forwarding. Pressing **`j`** in any main TUI opens the **TUI switcher** dialog, which lists every integrated TUI plus every running code agent window — selecting an entry either focuses the existing window (looked up by name) or spawns it on the fly. A narrow [Minimonitor sidebar]({{< relref "/docs/tuis/minimonitor" >}}) variant of monitor can sit next to a code agent pane to keep sibling activity visible without giving up screen real estate.

`ait ide` bootstraps such a session — installing the wrappers (if needed), opening the tmux session, launching monitor, and starting whichever agent windows you have configured — but you can also attach to an existing session and the convention still applies.

## Why it exists

A code agent is most useful when it can be observed and steered without interrupting it. Building the IDE around tmux rather than a graphical shell means the same workflow runs identically over SSH, in a screen-shared remote pairing session, and on every operating system the framework supports. Centering it on the monitor TUI gives every pane a single home screen with live previews and keystroke forwarding, so spawning a new agent or checking on a sibling is always one keystroke away.

## How to use

The command-line entry point — `ait ide`, its flags, and the session-sharing gotcha — is documented in [Terminal Setup]({{< relref "/docs/installation/terminal-setup" >}}). The integrated TUI list lives in the [TUIs section]({{< relref "/docs/tuis" >}}).

## See also

- [Monitor TUI]({{< relref "/docs/tuis/monitor" >}}) — the home screen
- [Agent memory]({{< relref "/docs/concepts/agent-memory" >}}) — how the Code Browser surfaces archived task context
- [Locks]({{< relref "/docs/concepts/locks" >}}) — multi-agent coordination inside the IDE

---

**Next:** [Agent memory]({{< relref "/docs/concepts/agent-memory" >}})
