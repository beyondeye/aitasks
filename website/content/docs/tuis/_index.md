---
title: "TUI Applications"
linkTitle: "TUIs"
weight: 30
description: "Terminal-based user interfaces for task management and code understanding"
aliases:
  - /docs/board/
  - /docs/board/how-to/
  - /docs/board/reference/
---

The aitasks framework includes several terminal-based user interfaces (TUIs) built with [Textual](https://textual.textualize.io/). Together they form the core of the ait tmux-based development environment: you launch them inside a single tmux session (typically via [`ait ide`]({{< relref "/docs/installation/terminal-setup" >}})) and hop between them with a single keystroke.

## Available TUIs

- **[Monitor](monitor/)** (`ait monitor`) — Dashboard of every pane in the current tmux session, categorized into code agents, TUIs, and other panes, with a live preview of the focused pane and keystroke forwarding. This is the home screen of the ait IDE.
- **[Minimonitor](minimonitor/)** (`ait minimonitor`) — Narrow sidebar variant of monitor, designed to sit next to a code agent pane so you can watch siblings and launch follow-up work without giving up screen real estate.
- **[Board](board/)** (`ait board`) — Kanban-style task board used at the **beginning** of the workflow: triage tasks, set priorities, organize work into columns, and decide what to implement next.
- **[Code Browser](codebrowser/)** (`ait codebrowser`) — Code navigation and diff review with task-aware annotations that show which aitasks contributed to each section, plus a **completed tasks history** screen (press `h`) for browsing archived work. Used at the **end** of the workflow or when onboarding to unfamiliar code.
- **[Settings](settings/)** (`ait settings`) — Configuration editor for code agent defaults, board settings, available models, and execution profiles. Also hosts the Tmux tab for editing integration settings.
- **[Stats](stats/)** (`ait stats-tui`) — Pane-based viewer for archived task completion statistics: summary, daily/weekly trends, label and issue-type breakdowns, code agent / LLM model histograms, and verified model score rankings. Swappable built-in layouts plus user-defined custom layouts.
- **Brainstorm** (`ait brainstorm`) — Interactive planning/brainstorming TUI for drafting new tasks. Dedicated documentation is pending.

All TUIs require the shared Python virtual environment installed by [`ait setup`]({{< relref "/docs/commands/setup-install" >}}).

## Navigating between TUIs

When you run the TUIs inside tmux, pressing **`j`** in any main TUI opens the **TUI switcher** dialog. The switcher lists the core integrated TUIs (Monitor, Board, Code Browser, Settings, Stats) plus your configured git TUI, and appends any running code agent and brainstorm windows discovered in the tmux session. Selecting a target either focuses the existing tmux window running that TUI or creates a new window and launches it — in one keystroke, without leaving tmux. Minimonitor is not listed in the switcher itself — it is auto-spawned alongside other TUIs when configured.

<!-- TODO screenshot: aitasks_tui_switcher_dialog.svg -->

The switcher only works inside tmux. If you are not running inside tmux yet, see [Terminal Setup]({{< relref "/docs/installation/terminal-setup" >}}) for how to set it up and launch the session via `ait ide`.

When more than one aitasks tmux session is running on the same tmux server, the switcher also shows a session row at the top. The attached session is marked with `▶`, and the selected session is highlighted. Use **Left/Right** to pick a different session; the list below refreshes to show that session's TUIs and windows. **Enter** (or any shortcut key like **`b`** for board, **`n`** for a new task) acts on the selected session — if it differs from your attached session, the switcher teleports your tmux client there automatically.

---

**Next:** [Board](board/) — start here for daily triage and task organization.
