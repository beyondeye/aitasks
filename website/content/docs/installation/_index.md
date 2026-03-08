---
title: "Installation"
linkTitle: "Installation"
weight: 10
description: "Install aitasks and configure your development environment"
---

## Quick Install

> **macOS prerequisite:** [Homebrew](https://brew.sh) is required. Install it first if you haven't — `ait setup` uses it to install bash 5, Python 3, coreutils, and CLI tools.

> **Important: Run from your project root.** The curl command (and `ait setup`) must be run from the root directory of your project — the directory that contains the `.git` folder. aitasks stores task files, plans, and configuration inside your repository, and relies on git for task IDs, locking, syncing, and archival. Installing in a subdirectory or a non-git directory will not work correctly.

Install into your project directory (the git repository root):

```bash
curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh | bash
```

> **Windows users:** Run this inside a WSL shell, not PowerShell. See the [Windows/WSL guide](windows-wsl/).

Upgrade an existing installation:

```bash
ait install latest
```

Or for fresh installs without an existing `ait` dispatcher:

```bash
curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh | bash -s -- --force
```

After installing, run `ait setup` to install dependencies and configure supported agent integrations. See [`ait setup`](../commands/setup-install/) for details.

**Already have the global `ait` shim?** If you've previously run `ait setup` on another project, the global shim at `~/.local/bin/ait` is already installed. You can bootstrap aitasks in any new project directory by simply running:

```bash
cd /path/to/new-project    # Must be the git repository root
ait setup
```

The shim detects that no aitasks project exists, downloads the latest release, installs it, and then runs the full setup — all in one command. Make sure you are at the root of the git repository (where `.git/` lives), not in a subdirectory.

**Windows/WSL users:** See the [Windows/WSL Installation Guide](windows-wsl/) for step-by-step instructions including WSL setup, agent installation examples, and terminal configuration.

**Agent caveats:** See [Known Agent Issues](known-issues/) for current Claude Code and Codex CLI workflow limitations.

## Platform Support

| Platform | Status | Notes |
|----------|--------|-------|
| Arch Linux | Fully supported | Primary development platform |
| Ubuntu/Debian | Fully supported | Includes Pop!_OS, Linux Mint, Elementary |
| Fedora/RHEL | Fully supported | Includes CentOS, Rocky, Alma |
| macOS | Fully supported | Requires [Homebrew](https://brew.sh); `ait setup` installs bash 5, coreutils, and other dependencies |
| Windows (WSL) | Fully supported | Via WSL with Ubuntu/Debian (see [Windows guide](windows-wsl/)) |

## What Gets Installed

**Per-project files** (committed to your repo):

- `ait` — CLI dispatcher script
- `.aitask-scripts/` — Framework scripts (task management, board, stats, etc.)
- `.claude/skills/aitask-*` — Primary skill definitions (used directly by Claude Code and as the source for wrappers)
- `aitasks/` — Task data directory (auto-created)
- `aiplans/` — Implementation plans directory (auto-created)

**Optional: Codex CLI support** (when `ait setup` detects Codex CLI):

- `.agents/skills/` — Codex CLI skill wrappers
- `.codex/instructions.md` — aitasks instructions for Codex
- `.codex/config.toml` — created or merged with aitask settings

**Optional: OpenCode support** (when `ait setup` detects OpenCode):

- `.opencode/skills/` — OpenCode skill wrappers
- `.opencode/commands/` — OpenCode command wrappers
- `.opencode/instructions.md` — aitasks instructions for OpenCode
- `opencode.json` — merged with aitask settings

**Optional: Gemini CLI support** (when `ait setup` detects Gemini CLI):

- `.gemini/skills/` — Gemini CLI skill wrappers
- `.gemini/commands/` — Gemini CLI command wrappers
- `GEMINI.md` — aitasks instructions for Gemini CLI

**Global dependencies** (installed once per machine via `ait setup`):

- CLI tools: `fzf`, `gh` (for GitHub), `glab` (for GitLab), or `bkt` (for Bitbucket), `jq`, `git`
- Python venv at `~/.aitask/venv/` with `textual`, `pyyaml`, `linkify-it-py` (plus optional `plotext` when enabled for `ait stats --plot`)
- Global `ait` shim at `~/.local/bin/ait`
- Claude Code permissions in `.claude/settings.local.json` (see [Claude Code Permissions](../commands/setup-install/#claude-code-permissions))

---

**Next:** [Getting Started]({{< relref "getting-started" >}})
