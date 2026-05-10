---
title: "Windows & WSL Installation"
linkTitle: "Windows/WSL"
weight: 20
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

Once your WSL Ubuntu/Debian shell is up, the cleanest install is the official `.deb` package — same as native Ubuntu. See the [Debian/Ubuntu guide](../debian-apt/) for the full walkthrough; the short version (with [GitHub CLI](https://cli.github.com/) installed):

```bash
gh release download --repo beyondeye/aitasks --pattern '*.deb'
sudo apt install ./aitasks_*.deb
ait setup
```

If you do not have `gh` installed, see the curl one-liner in the [Debian/Ubuntu guide](../debian-apt/).

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

## Install Claude Code

Claude Code must also be installed from within WSL to work with aitasks. Follow the [Claude Code quickstart guide](https://docs.anthropic.com/en/docs/claude-code/overview) for Linux installation instructions — WSL uses the Linux installation path.

```bash
# Install Node.js if not already present (Claude Code requires it)
curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
sudo apt-get install -y nodejs

# Install Claude Code
npm install -g @anthropic-ai/claude-code
```

---

## Terminal Options

### VS Code with WSL Extension

If you prefer an IDE-based workflow:

1. Install the [WSL extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-wsl) in VS Code
2. Open VS Code and connect to WSL (click the green icon in the bottom-left corner, or run `code .` from your WSL shell)
3. Use VS Code's integrated terminal for running `ait` commands and Claude Code

### Default WSL Terminal

The default WSL terminal (Windows Terminal) supports tabs and is fully functional for all aitasks features including `ait board`.

### Warp Terminal

[Warp](https://www.warp.dev/) offers built-in Claude Code integration, multi-tab support, and real-time diff viewing.

**Setup with WSL:**
1. Install Warp for Windows from [warp.dev](https://www.warp.dev/)
2. Configure your default shell to use WSL in Warp's settings
3. Warp will automatically connect to your WSL environment

---

## Known Issues

- **Legacy console:** The old Windows Console Host (conhost.exe) has limited TUI support. Use Windows Terminal, Warp, or VS Code's integrated terminal instead.

---

**Next:** [Terminal Setup]({{< relref "terminal-setup" >}})
