---
title: "Getting Started"
linkTitle: "Getting Started"
weight: 20
description: "First-time setup and your first task workflow"
---

This guide walks you through aitasks from installation to completing your first task with Claude Code, Gemini CLI, OpenCode, or Codex CLI.

## 1. Install aitasks

> **macOS:** [Homebrew](https://brew.sh) must be installed before running `ait setup`.

In your project directory (the root of the git repository, where `.git/` lives):

```bash
curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh | bash
```

> **Why the project root?** aitasks is tightly integrated with git — it uses git branches for task IDs, locking, and syncing. Task and plan files are committed to your repository. Always run the installer and `ait setup` from the root directory of the git repo where you want to manage tasks.

Then run the setup to install dependencies and configure supported agent integrations:

```bash
ait setup
```

See the [Installation guide](../installation/) for platform-specific details and troubleshooting.

## 2. Review Settings

After setup, review and configure framework settings with the interactive TUI:

```bash
ait settings
```

The Settings TUI provides centralized management of:

- **Agent Defaults** — Which code agent and model is used when launching tasks from the [Board](../tuis/board/) TUI and when running explain from the [Code Browser](../tuis/codebrowser/) TUI
- **Board** — Auto-refresh interval and sync behavior
- **Project Config** — Build verification commands, test/lint commands, co-author email domain
- **Models** — Browse available models and their verified performance scores
- **Execution Profiles** — Pre-configured answers to workflow prompts (e.g., skip confirmations, auto-create worktrees)

We recommend reviewing settings early — they affect how the Board and Code Browser TUIs invoke code agents and which models are used. See the [Settings documentation](../tuis/settings/) for details.

## 3. Create Your First Task

Launch the interactive task creator:

```bash
ait create
```

Walk through the prompts to set priority, effort, labels, and write a description. Don't worry about being precise — aitasks is designed for rough, stream-of-consciousness task descriptions that the planning phase can refine later.

Your task is saved as a local draft in `aitasks/new/`. Select "Finalize now" to assign it a permanent ID and commit to git.

## 4. View Tasks on the Board

Open the kanban board to see your tasks visually:

```bash
ait board
```

Use arrow keys to navigate, **Shift+arrows** to move tasks between columns, and **Enter** to view task details. See the [Board documentation](../tuis/board/) for the full guide.

## 5. Pick and Implement a Task

Start your code agent and run the pick skill:

```
/aitask-pick
```

Use the same command in Claude Code, Gemini CLI, and OpenCode. In Codex CLI, use:

```
$aitask-pick
```

> Interactive Codex skill flows require **plan mode** because `request_user_input` is only available in plan mode.

This launches the full development workflow:

1. **Select** a task from the prioritized list
2. **Plan** — Your code agent explores the codebase and creates an implementation plan for your approval
3. **Implement** — Your code agent follows the approved plan
4. **Review** — You review changes, request adjustments if needed, then commit
5. **Archive** — Task and plan files are archived automatically

## 6. Iterate

The core loop is: **create tasks** (with `ait create`, `/aitask-create`, or `$aitask-create`) → **triage** (with `ait board`) → **implement** (with `/aitask-pick` or `$aitask-pick`).

As you work, explore these features:

- [Workflow Guides](../workflows/) — Common patterns like capturing ideas fast, task decomposition, and parallel development
- [Code Agent Skills](../skills/) — All available agent skills (`/aitask-pick` in Claude Code, Gemini CLI, and OpenCode; `$aitask-pick` in Codex CLI, etc.)
- [Command Reference](../commands/) — Full CLI reference for all `ait` subcommands

---

**Next:** [TUI Applications]({{< relref "tuis" >}})
