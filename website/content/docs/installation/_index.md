---
title: "Installation"
linkTitle: "Installation"
weight: 10
description: "Install aitasks and configure your development environment"
---

## Quick Install

> **macOS prerequisite:** [Homebrew](https://brew.sh) is required. Install it first if you haven't — `ait setup` uses it to install bash 5, Python 3, coreutils, and CLI tools.

Install into your project directory:

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

After installing, run `ait setup` to install dependencies and configure Claude Code permissions. See [`ait setup`](../commands/setup-install/) for details.

**Already have the global `ait` shim?** If you've previously run `ait setup` on another project, the global shim at `~/.local/bin/ait` is already installed. You can bootstrap aitasks in any new project directory by simply running:

```bash
cd /path/to/new-project
ait setup
```

The shim detects that no aitasks project exists, downloads the latest release, installs it, and then runs the full setup — all in one command.

**Windows/WSL users:** See the [Windows/WSL Installation Guide](windows-wsl/) for step-by-step instructions including WSL setup, Claude Code installation, and terminal configuration.

## Platform Support

| Platform | Status | Notes |
|----------|--------|-------|
| Arch Linux | Fully supported | Primary development platform |
| Ubuntu/Debian | Fully supported | Includes Pop!_OS, Linux Mint, Elementary |
| Fedora/RHEL | Fully supported | Includes CentOS, Rocky, Alma |
| macOS | Partial | `date -d` and bash 3.2 limitations (see [Known Issues](#known-issues)) |
| Windows (WSL) | Fully supported | Via WSL with Ubuntu/Debian (see [Windows guide](windows-wsl/)) |

## What Gets Installed

**Per-project files** (committed to your repo):

- `ait` — CLI dispatcher script
- `aiscripts/` — Framework scripts (task management, board, stats, etc.)
- `.claude/skills/aitask-*` — Claude Code skill definitions
- `aitasks/` — Task data directory (auto-created)
- `aiplans/` — Implementation plans directory (auto-created)

**Global dependencies** (installed once per machine via `ait setup`):

- CLI tools: `fzf`, `gh` (for GitHub), `glab` (for GitLab), or `bkt` (for Bitbucket), `jq`, `git`
- Python venv at `~/.aitask/venv/` with `textual`, `pyyaml`, `linkify-it-py`
- Global `ait` shim at `~/.local/bin/ait`
- Claude Code permissions in `.claude/settings.local.json` (see [Claude Code Permissions](../commands/setup-install/#claude-code-permissions))

## Known Issues

- **macOS `date -d`**: The `ait stats` and `ait issue-import` commands use GNU `date -d` which is not available with macOS BSD date. Install `coreutils` via Homebrew (`brew install coreutils`) to get `gdate` as a workaround.
- **macOS bash**: The system bash on macOS is v3.2; aitasks requires bash 4+. Running `ait setup` on macOS installs bash 5 via Homebrew.

## Authentication with Your Git Remote

Authenticating with your git remote enables full aitasks functionality including task locking (prevents two agents from picking the same task), push/pull sync across machines, and issue integration (`ait issue-import`, `ait issue-update`).

### GitHub

Authenticate the GitHub CLI:

```bash
gh auth login
```

Follow the prompts to authenticate via browser or token.

### GitLab

Authenticate the GitLab CLI:

```bash
glab auth login
```

Follow the prompts to authenticate via browser or token. This also configures
git credentials for pushing to GitLab remotes.

### Bitbucket

Authenticate the Bitbucket CLI:

```bash
bkt auth login https://bitbucket.org --kind cloud --web
```

Follow the browser prompts to authenticate with your Atlassian account. For token-based
authentication (e.g., in CI environments):

```bash
bkt auth login https://bitbucket.org --kind cloud --username <email> --token <app-password>
```

Create an app password at: Settings > Personal Bitbucket settings > App passwords.
Enable the "Issues: read" and "Issues: write" permissions.

Note: `bkt` requires a context to be configured. After authentication, create one:

```bash
bkt context create myproject --host "https://api.bitbucket.org/2.0" \
    --workspace <your-workspace> --repo <your-repo> --set-active
```

---

**Next:** [Getting Started]({{< relref "getting-started" >}})
