---
date: 2026-04-12
title: "v0.15.0: One-step startup with `ait ide`, Live monitor TUI for agent panes, and Minimonitor side panel"
linkTitle: "v0.15.0"
description: "v0.15.0 is a big release centered on live tmux monitoring. Running several code agents in parallel is now a first-class experience, with two new monitor TUIs, a one-keystroke TUI switcher, and a single `ait ide` command to get everything going."
author: "aitasks team"
---


v0.15.0 is a big release centered on live tmux monitoring. Running several code agents in parallel is now a first-class experience, with two new monitor TUIs, a one-keystroke TUI switcher, and a single `ait ide` command to get everything going.

## One-step startup with `ait ide`

Spinning up your workspace used to take four steps: open a terminal, `cd` into the project, start tmux, then start the monitor. Now it's just `ait ide`. The new command creates (or attaches to) your project's tmux session and opens a monitor window for you — whether you're running it fresh outside tmux, inside an existing session, or on a second terminal to get another view of the same workspace.

## Live monitor TUI for agent panes

`ait monitor` is a full-screen dashboard showing every tmux code-agent pane in your session with a live preview of what each one is doing. You can forward keystrokes straight into a paused agent, kill a runaway session with `k`, pull up task context with `i`, and flip auto-switch on to let the dashboard follow whichever agent needs attention next. Preview size cycles between S/M/L so you can balance overview and detail.

## Minimonitor side panel

Every time you launch an agent, a compact minimonitor now auto-spawns right beside it as a side panel. It lists the agents running in the same window, and two bindings do the heavy lifting: Tab jumps tmux focus to the agent pane next to you, and Enter sends an Enter keystroke to that sibling pane — perfect for unsticking a paused Claude without leaving your current context.

## Jump anywhere with `j`

A new TUI switcher (`j` from any dashboard) gives you a single keystroke to hop between the board, monitor, codebrowser, settings, brainstorm, and your running code agents. It also picks up your configured git TUI (lazygit, gitui, or tig) automatically, with inline key hints showing you the one-letter shortcut for each destination.

## Pick-as-you-go workflows

Several small-but-nice workflow additions land together: press `n` in the monitor to pick the next ready sibling (or first ready child) and close out the finished agent, press `N` in the board to rename a task with a clean git commit, and hit `(A)gent` in the launch dialog to override the model for a single run without touching your defaults.

---

---

**Full changelog:** [v0.15.0 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.15.0)
