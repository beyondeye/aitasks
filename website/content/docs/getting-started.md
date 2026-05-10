---
title: "Getting Started"
linkTitle: "Getting Started"
weight: 20
description: "First-time setup and your first task workflow"
depth: [main-concept]
---

This guide walks you through aitasks from installation to completing your first task with Claude Code, Gemini CLI, OpenCode, or Codex CLI.

## 1. Install aitasks

Pick the install command for your platform (full per-platform walkthroughs in the [Installation guide](../installation/)):

| Platform | Install command |
|----------|-----------------|
| **macOS** | `brew install beyondeye/aitasks/aitasks` |
| **Arch / Manjaro** (AUR) | `yay -S aitasks` |
| **Debian / Ubuntu / WSL** | Download the `.deb` from [Releases](https://github.com/beyondeye/aitasks/releases/latest), then `sudo apt install ./aitasks_*.deb` |
| **Fedora / RHEL / Rocky / Alma** | Download the `.rpm` from [Releases](https://github.com/beyondeye/aitasks/releases/latest), then `sudo dnf install ./aitasks-*.noarch.rpm` |
| **Other (any POSIX)** | `curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh \| bash` |

> **Run `ait setup` from the project root.** aitasks expects to be invoked from the directory containing `.git/` — the root of your project's git repository. It uses git branches for task IDs, locking, and syncing, and task and plan files are committed to your repository.

In your project directory (the root of the git repository, where `.git/` lives), run the setup to install dependencies and configure supported agent integrations:

```bash
cd /path/to/your-project
ait setup
```

See the [Installation guide](../installation/) for platform-specific details and troubleshooting.

## 2. Start the ait IDE

From your terminal, go to the project you just set up and start the integrated aitasks workspace:

```bash
cd /path/to/your/project
ait ide
```

`ait ide` attaches to (or creates) a tmux session and opens the **monitor** TUI — the dashboard for all running code agents, open TUIs, and other panes in your session. Every command in the rest of this guide assumes you are running inside the tmux session started by `ait ide`.

Press **`j`** inside any main TUI to open the **TUI switcher** dialog and jump directly to `ait board`, `ait monitor`, `ait codebrowser`, `ait settings`, or a running code agent window without leaving tmux.

> Can't use tmux? See the [minimal / non-tmux workflow](../installation/terminal-setup/#minimal--non-tmux-workflow) in the Terminal Setup page for the fallback path.

## 3. Review Settings

From inside the `ait ide` session, press **`j`** in the monitor TUI and pick **settings** in the switcher. This opens `ait settings`, which provides centralized management of:

- **Agent Defaults** — Which code agent and model is used when launching tasks from the [Board](../tuis/board/) TUI and when running explain from the [Code Browser](../tuis/codebrowser/) TUI
- **Board** — Auto-refresh interval and sync behavior
- **Project Config** — Build verification commands, test/lint commands, co-author email domain
- **Models** — Browse available models and their verified performance scores
- **Execution Profiles** — Pre-configured answers to workflow prompts (e.g., skip confirmations, auto-create worktrees)

We recommend reviewing settings early — they affect how the Board and Code Browser TUIs invoke code agents and which models are used. See the [Settings documentation](../tuis/settings/) for details.

## 4. Create Your First Task

Open a new tmux window and launch the interactive task creator:

```bash
ait create
```

Walk through the prompts to set priority, effort, labels, and write a description. Don't worry about being precise — aitasks is designed for rough, stream-of-consciousness task descriptions that the planning phase can refine later.

Your task is saved as a local draft in `aitasks/new/`. Select "Finalize now" to assign it a permanent ID and commit to git.

## 5. View Tasks on the Board

Press **`j`** from any TUI and select **board** to open the kanban view of your tasks. Use the arrow keys to navigate, **Shift+arrows** to move tasks between columns, and **Enter** to view task details. See the [Board documentation](../tuis/board/) for the full guide.

## 6. Pick and Implement a Task

From the board, press **`p`** on a task to launch a code agent on it — a new tmux window is created for the agent and the picked task appears in the `ait monitor` dashboard. Press **`j`** → **monitor** at any point to watch the agent progress.

You can also start the pick skill directly from a code agent prompt in any tmux window:

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

## 7. Iterate

The core loop is: **create tasks** (with `ait create`, `/aitask-create`, or `$aitask-create`) → **triage** (with `ait board`) → **implement** (with `/aitask-pick` or `$aitask-pick`). All of it happens inside the single `ait ide` tmux session, with `j` as the one keystroke that moves you between TUIs.

As you work, explore these features:

- [Terminal Setup](../installation/terminal-setup/) — full `ait ide` command reference: flags, session naming, and the shared-session gotcha.
- [The IDE model]({{< relref "/docs/concepts/ide-model" >}}) — the conceptual overview of how `ait ide` organises tmux around the monitor TUI.
- [Workflow Guides](../workflows/) — Common patterns like capturing ideas fast, task decomposition, and parallel development
- [Code Agent Skills](../skills/) — All available agent skills (`/aitask-pick` in Claude Code, Gemini CLI, and OpenCode; `$aitask-pick` in Codex CLI, etc.)
- [Command Reference](../commands/) — Full CLI reference for all `ait` subcommands

---

**Next:** [Workflow Guides]({{< relref "workflows" >}})
