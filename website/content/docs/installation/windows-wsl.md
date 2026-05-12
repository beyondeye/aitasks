---
title: "Windows & WSL Installation"
linkTitle: "Windows/WSL"
weight: 26
description: "Guide for installing and running aitasks on Windows via WSL"
depth: [intermediate]
---

Step-by-step guide for installing and configuring aitasks on Windows via the Windows Subsystem for Linux (WSL).

## Prerequisites

- Windows 10 version 2004+ or Windows 11
- Administrator access (for WSL installation)

---

## Install WSL

aitasks runs inside WSL (Windows Subsystem for Linux). If you don't have WSL installed:

1. Open PowerShell as Administrator
2. Run:
   ```powershell
   wsl --install
   ```
3. Restart your computer when prompted
4. On first launch, create a Unix username and password

For detailed instructions, see the [official WSL installation guide](https://learn.microsoft.com/en-us/windows/wsl/install).

**Important:** All subsequent commands in this guide should be run from within the WSL shell (not PowerShell or CMD).

To open a WSL shell: search for "WSL" in the Windows search box, or type `wsl` in PowerShell.

---

## Install aitasks (recommended: `.deb` package)

Once your WSL Ubuntu/Debian shell is up, the cleanest install is the official `.deb` package — same as native Ubuntu. See the [Linux guide — .deb section](../linux/#debian--ubuntu--wsl-deb) for the full walkthrough; the short version (with [GitHub CLI](https://cli.github.com/) installed):

```bash
gh release download --repo beyondeye/aitasks --pattern '*.deb'
sudo apt install ./aitasks_*.deb
ait setup
```

If you do not have `gh` installed, see the curl one-liner in the [Linux guide — .deb section](../linux/#debian--ubuntu--wsl-deb).

> **Ubuntu 20.04 (Focal) on WSL:** the `.deb` install is blocked by apt's dependency solver (Focal ships `python3 = 3.8`, the `.deb` requires `>= 3.9`). Use the [Fallback: install via curl](#fallback-install-via-curl) section below — `ait setup` provisions a modern Python user-scoped via [uv](https://github.com/astral-sh/uv) and sidesteps the system-package dependency.

After setup completes, see [Authentication with Your Git Remote](../#authentication-with-your-git-remote) to configure GitHub access for task locking, sync, and issue integration.

---

## Fallback: install via curl

If you cannot use the `.deb` (e.g., a custom WSL distro without working `apt`, or Ubuntu 20.04 / Debian 11 with an older Python), install via the curl-based bootstrap:

```bash
cd /path/to/your-project
curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh | bash
ait setup
```

`ait setup` automatically detects WSL and installs dependencies via `apt`. It also installs a modern Python (3.11) user-scoped via [uv](https://github.com/astral-sh/uv) into `~/.aitask/python/` if your system Python is too old, so this path works on Ubuntu 20.04 / Debian 11 even when the `.deb` install would fail.

If you already have the global `ait` shim installed (from a previous project), you can skip the `curl` step and just run `ait setup` in the new project directory — it will auto-bootstrap the installation.

---

## Install Coding Agents

All supported coding agents — Claude Code, Gemini CLI, Codex CLI, and OpenCode — must be installed from within WSL to work with aitasks. Each agent's Linux install path applies; install whichever ones you plan to use.

Most of these agents require Node.js, so install it first (skip if already present):

```bash
# Install Node.js (required by Claude Code, Gemini CLI, Codex CLI, OpenCode)
curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
sudo apt-get install -y nodejs
```

Then install one or more agents:

```bash
# Claude Code — see https://docs.anthropic.com/en/docs/claude-code/overview
npm install -g @anthropic-ai/claude-code

# Gemini CLI — see https://github.com/google-gemini/gemini-cli
npm install -g @google/gemini-cli

# Codex CLI — see https://github.com/openai/codex
npm install -g @openai/codex

# OpenCode — see https://opencode.ai
npm install -g opencode-ai
```

Run `ait setup` in your project after installing — it auto-detects which agents are present and configures only the ones it finds.

---

## Terminal Options

### VS Code with WSL Extension

If you prefer an IDE-based workflow:

1. Install the [WSL extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-wsl) in VS Code
2. Open VS Code and connect to WSL (click the green icon in the bottom-left corner, or run `code .` from your WSL shell)
3. Use VS Code's integrated terminal for running `ait` commands and Claude Code

### Default WSL Terminal

The default WSL terminal (Windows Terminal) supports tabs and is fully functional for all aitasks features including `ait board`.

---

## Known Issues

- **Legacy console:** The old Windows Console Host (conhost.exe) has limited TUI support. Use Windows Terminal or VS Code's integrated terminal instead.

---

**Next:** [Terminal Setup]({{< relref "terminal-setup" >}})
