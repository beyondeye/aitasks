---
title: "Terminal Setup & Monitoring"
linkTitle: "Terminal Setup"
weight: 50
description: "Multi-tab terminal workflow and monitoring during implementation"
---

## Multi-Tab Terminal Workflow

The aitasks framework is built for terminal-centric development. Using a terminal emulator that supports multiple tabs or panes — switchable with keyboard shortcuts — makes the workflow significantly more efficient.

**Recommended terminal emulators:**

- [**Warp**](https://www.warp.dev/) — Modern terminal with built-in Claude Code integration, multi-tab support, and real-time diff viewing. Available for Linux, macOS, and Windows
- **tmux** — Terminal multiplexer with split panes and sessions. Works everywhere
- [**Ghostty**](https://ghostty.org/) — Fast GPU-accelerated terminal with tabs and splits

**Typical tab layout:**

| Tab | Purpose |
|-----|---------|
| Tab 1 | Main Claude Code session running [`/aitask-pick`](../../skills/aitask-pick/) |
| Tab 2 | [`ait board`](../../commands/board-stats/#ait-board) for visual task management and triage |
| Tab 3 | [`ait create`](../../commands/task-management/#ait-create) ready to launch for capturing new ideas |
| Tab 4 | Git status / diff viewer for monitoring implementation changes |

**IDE alternative:** You can also run a terminal inside your IDE (VS Code, IntelliJ, etc.) and use another pane to watch file changes in real time. However, dedicated terminal emulators with keyboard-driven tab switching tend to be faster for this workflow.

---

## Monitoring While Implementing

While [`/aitask-pick`](../../skills/aitask-pick/) is running — especially during the exploration or implementation phases which can take several minutes — you can stay productive in other terminal tabs.

**What to do while waiting:**

- **Triage tasks** — Open [`ait board`](../../commands/board-stats/#ait-board) in another tab to review priorities, move tasks between kanban columns, update metadata (priority, effort, labels), and adjust dependencies. See the [Board documentation](../../board/) for all available operations and keyboard shortcuts
- **Capture new ideas** — As ideas come up during the implementation (which they often do while watching the agent work), quickly switch to a tab with [`ait create`](../../commands/task-management/#ait-create) and write them down. The key shortcut `n` in [`ait board`](../../commands/board-stats/#ait-board) also launches task creation directly
- **Review progress** — Watch the current diff in another tab to understand what changes are being made. Warp's built-in diff viewer or a simple `git diff` in a separate tab works well for this

This parallel workflow means the human never becomes a bottleneck waiting for the AI agent to finish. You are always either reviewing the agent's output, managing your task backlog, or capturing the next set of ideas.

### Context Monitoring

One of the key advantages of decomposing work into small connected tasks is reduced context usage — Claude Code is effectively more capable when it has more room in its context window. Monitoring context usage in real time helps you understand when a task is getting too large and should be split.

**Recommended plugin:**

- [**claude-hud**](https://github.com/jarrodwatts/claude-hud) — Claude Code plugin that displays real-time context window usage directly in your terminal. Shows token count, percentage filled, and alerts when context is getting large
