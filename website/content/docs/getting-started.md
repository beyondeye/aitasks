---
title: "Getting Started"
linkTitle: "Getting Started"
weight: 20
description: "First-time setup and your first task workflow"
---

This guide walks you through aitasks from installation to completing your first task with Claude Code.

## 1. Install aitasks

In your project directory:

```bash
curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh | bash
```

Then run the setup to install dependencies and configure Claude Code permissions:

```bash
ait setup
```

See the [Installation guide](../installation/) for platform-specific details and troubleshooting.

## 2. Create Your First Task

Launch the interactive task creator:

```bash
ait create
```

Walk through the prompts to set priority, effort, labels, and write a description. Don't worry about being precise — aitasks is designed for rough, stream-of-consciousness task descriptions that Claude refines during planning.

Your task is saved as a local draft in `aitasks/new/`. Select "Finalize now" to assign it a permanent ID and commit to git.

## 3. View Tasks on the Board

Open the kanban board to see your tasks visually:

```bash
ait board
```

Use arrow keys to navigate, **Shift+arrows** to move tasks between columns, and **Enter** to view task details. See the [Board documentation](../board/) for the full guide.

## 4. Pick and Implement a Task

Start Claude Code and run the pick skill:

```
/aitask-pick
```

This launches the full development workflow:

1. **Select** a task from the prioritized list
2. **Plan** — Claude explores the codebase and creates an implementation plan for your approval
3. **Implement** — Claude follows the approved plan
4. **Review** — You review changes, request adjustments if needed, then commit
5. **Archive** — Task and plan files are archived automatically

## 5. Iterate

The core loop is: **create tasks** (with `ait create` or `/aitask-create`) → **triage** (with `ait board`) → **implement** (with `/aitask-pick`).

As you work, explore these features:

- [Workflow Guides](../workflows/) — Common patterns like capturing ideas fast, task decomposition, and parallel development
- [Claude Code Skills](../skills/) — All available slash commands (`/aitask-pick`, `/aitask-explore`, `/aitask-fold`, etc.)
- [Command Reference](../commands/) — Full CLI reference for all `ait` subcommands
