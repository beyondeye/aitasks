<div align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="imgs/aitasks_logo_dark_theme_im.png">
    <source media="(prefers-color-scheme: light)" srcset="imgs/aitasks_logo_light_theme_pil.png">
    <img alt="aitasks logo" src="imgs/aitasks_logo_light_theme_pil.png" width="400">
  </picture>

  <h3><em>A full agentic IDE in your terminal. File-based, git-native, multi-agent.</em></h3>

  <p>
    <a href="https://aitasks.io/"><img src="https://img.shields.io/badge/docs-website-blue" alt="Documentation"/></a>
    <a href="https://github.com/beyondeye/aitasks/stargazers"><img src="https://img.shields.io/github/stars/beyondeye/aitasks?style=social" alt="GitHub stars"/></a>
<a href="https://github.com/beyondeye/aitasks/commits/main"><img src="https://img.shields.io/github/last-commit/beyondeye/aitasks" alt="Last commit"/></a>
    <a href="https://github.com/beyondeye/aitasks/issues"><img src="https://img.shields.io/github/issues/beyondeye/aitasks" alt="GitHub issues"/></a>
  </p>
</div>

---

A full agentic IDE in your terminal — kanban board, code browser, agent monitoring, and AI-enhanced git workflows — integrated with AI code agents ([Claude Code](https://docs.anthropic.com/en/docs/claude-code), [Gemini CLI](https://github.com/google-gemini/gemini-cli), [Codex CLI](https://github.com/openai/codex), [OpenCode](https://github.com/opencode-ai/opencode)) via skills. Tasks are markdown files with YAML frontmatter stored in your repo alongside your code. No backend. No database. Just git.

Built for maximizing development speed 🚀 AND human-to-agent intent transfer efficiency 💬.

## 🎯 The Challenge
AI coding agents are proficient enough to handle real development tasks. The bottleneck is **intent transfer** — getting structured, contextual instructions to the agent without the human becoming the slowdown. **aitasks** optimizes both the context the agent sees and the speed at which a human can steer it.

## 💡 Core Philosophy
"Light Spec" engine: unlike rigid Spec-Driven Development, tasks here are **living documents**.
  - **Raw Intent:** a task starts as a simple Markdown file capturing the goal.
  - **Iterative Refinement:** an AI workflow refines task files in stages — expanding context, adding technical details, and verifying requirements — before code is written.

## 🏗️ Key Features & Architecture

- **🖥️ Agentic IDE in your terminal** — Board, Code Browser, Monitor, Brainstorm, and Settings TUIs in one tmux session via `ait ide`. Press `j` to hop between them.
- **🧠 Long-term memory for agents** — archived tasks and plans become queryable context; the Code Browser annotates each line back to the task/plan that introduced it.
- **🔀 Tight git coupling, AI-enhanced** — PR import/close, issue tracker integration, contribution flow, changelog generation, and AI-assisted reverts — all rooted in git commits and task metadata.
- **🧩 Task decomposition & parallelism** — auto-explode complex tasks into child tasks; sibling context propagates via archived plans; git worktrees + atomic locks for parallel agent work.
- **🔍 AI-enhanced code review** — per-language review guides, batched multi-file reviews producing follow-up tasks, QA workflow with test-coverage analysis.
- **🤖 Multi-agent support with verified scores** — unified `codeagent` wrapper over Claude Code / Gemini CLI / Codex CLI / OpenCode; per-model/per-operation scores accumulated from user feedback.

- **Dual-Mode CLI** — interactive mode for humans (optimized for flow, no context switching) and batch mode for agents (programmatic task/status updates).

- **Battle tested** — actively developed and used in real projects.

- **Fully customizable workflow** — scripts and skills live in your project repo; modify them for your needs and contribute back via `/aitask-contribute`. See the [Contribute and Manage Contributions workflow](https://aitasks.io/docs/workflows/contribute-and-manage/).

## 🖥️ Platform Support

| Platform | Status | Notes |
|----------|--------|-------|
| Arch Linux | Fully supported | Primary development platform |
| Ubuntu/Debian | Fully supported | Includes Pop!_OS, Linux Mint, Elementary |
| Fedora/RHEL | Fully supported | Includes CentOS, Rocky, Alma |
| macOS | Fully supported | Requires Homebrew for bash 5 and coreutils (auto-installed by `ait setup`) |
| Windows (WSL) | Fully supported | Via WSL with Ubuntu/Debian (see [Windows guide](https://aitasks.io/docs/installation/windows-wsl/)) |

## ⚡ Quick Install

Install into your project directory:

```bash
curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh | bash
ait setup
```

> **Windows users:** Run this inside a WSL shell, not PowerShell. See the [Windows/WSL guide](https://aitasks.io/docs/installation/windows-wsl/).

`ait setup` installs dependencies and configures Claude Code permissions. See [`ait setup`](https://aitasks.io/docs/commands/setup-install/) for details.

Upgrade an existing installation:

```bash
ait install latest
ait setup
```

Or for fresh installs without an existing `ait` dispatcher:

```bash
curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh | bash -s -- --force
ait setup
```

**Already have the global `ait` shim?** If you've previously run `install.sh` on another project, the global shim at `~/.local/bin/ait` is already installed. You can bootstrap aitasks in any new project directory by simply running:

```bash
cd /path/to/new-project
ait setup
```

The shim detects that no aitasks project exists, downloads the latest release, installs it, and then runs the full setup — all in one command.

**Windows/WSL users:** See the [Windows/WSL Installation Guide](https://aitasks.io/docs/installation/windows-wsl/) for step-by-step instructions including WSL setup, Claude Code installation, and terminal configuration.

## 📦 What Gets Installed

**Per-project files** (committed to your repo):

- `ait` — CLI dispatcher script
- `.aitask-scripts/` — Framework scripts (task management, board, stats, etc.)
- `.claude/skills/aitask-*` — Claude Code skill definitions
- `aitasks/` — Task data directory (auto-created)
- `aiplans/` — Implementation plans directory (auto-created)

**Global dependencies** (installed once per machine via `install.sh` and `ait setup`):

- CLI tools: `fzf`, `gh` (for GitHub), `glab` (for GitLab), or `bkt` (for Bitbucket), `jq`, `git`
- Python venv at `~/.aitask/venv/` with `textual`, `pyyaml`, `linkify-it-py`
- Global `ait` shim at `~/.local/bin/ait`
- Claude Code permissions in `.claude/settings.local.json` (see [Claude Code Permissions](https://aitasks.io/docs/commands/setup-install/#claude-code-permissions))

## 📖 Documentation

**[Documentation Website](https://aitasks.io/)** — Browse the full documentation online.

- **[Overview](https://aitasks.io/docs/overview/)** — The challenge aitasks addresses, its core philosophy, and key features of the agentic IDE.

- **[Installation](https://aitasks.io/docs/installation/)** — Quick install, platform support, setup, and git remote authentication.

- **[Getting Started](https://aitasks.io/docs/getting-started/)** — First-time walkthrough from install to completing your first task.

- **[Concepts](https://aitasks.io/docs/concepts/)** — What each building block is and why it exists: tasks, plans, parent/child, folded tasks, review guides, execution profiles, verified scores, agent attribution, locks, and the IDE model.

- **[TUI Applications](https://aitasks.io/docs/tuis/)** — The terminal IDE: Monitor, Minimonitor, Board, Code Browser, Settings, and Brainstorm — hop between them with a single keystroke via `ait ide`.

- **[Workflow Guides](https://aitasks.io/docs/workflows/)** — End-to-end guides for common usage patterns: capturing ideas fast, tmux IDE, complex task decomposition, parallel development, code review, QA, PR workflow, and more.

- **[Code Agent Skills](https://aitasks.io/docs/skills/)** — Reference for `/aitask-pick`, `/aitask-explore`, `/aitask-create`, and other skill integrations across Claude Code, Gemini CLI, Codex CLI, and OpenCode.

- **[Command Reference](https://aitasks.io/docs/commands/)** — Complete CLI reference for all `ait` subcommands.

- **[Development Guide](https://aitasks.io/docs/development/)** — Architecture overview, directory layout, library scripts, and release process.

## 📄 License
This project is licensed under the Apache License 2.0 with the Commons Clause condition.

What this means:
✅ You can: Use, copy, and modify the code for free, with an explicit patent grant from contributors.

✅ You can: Use aitasks as a library to power your own commercial products or SaaS applications.

❌ You cannot: Sell aitasks itself, or a derivative version of it, as a standalone product or service (e.g., selling a "Pro" version of the library or a managed aitasks hosting service) without prior written consent.

For the full legal text, please see the [LICENSE](LICENSE) file.
