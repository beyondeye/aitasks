---
title: "Installation"
linkTitle: "Installation"
weight: 10
description: "Install aitasks and configure your development environment"
---

## Quick Install

> **Run from the project root.** aitasks expects to be invoked from the directory containing `.git/` — the root of your project's git repository. All install methods below assume you `cd` into that directory first. aitasks stores task files, plans, and configuration inside your repository and relies on git for task IDs, locking, syncing, and archival. Installing in a subdirectory or a non-git directory will not work correctly.

## Operating systems

Pick your platform:

| Platform | Install command |
|----------|-----------------|
| **macOS** | `brew install beyondeye/aitasks/aitasks` — see the [Homebrew guide](macos/) |
| **Linux** (Arch / Debian / Ubuntu / Fedora / RHEL / Rocky / Alma / WSL) | Distro-specific install paths — see the [Linux guide](linux/) |
| **Windows / WSL** | Use a WSL2 Ubuntu/Debian shell, then follow the Linux `.deb` path — see the [Windows / WSL guide](windows-wsl/) |
| **Other (any POSIX)** | `curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh \| bash` |

All install methods drop a single `ait` command on your `$PATH` — the **global shim** (~3 KB). The shim downloads the framework on demand when you run `ait setup` in your project, so the installed package stays tiny and you do not need to re-install the package to get framework updates. For the design rationale see the [packaging strategy reference](https://github.com/beyondeye/aitasks/blob/main/aidocs/packaging_strategy.md); for current limitations of each channel and the roadmap toward more official repos see the [packaging distribution status & roadmap](https://github.com/beyondeye/aitasks/blob/main/aidocs/packaging_distribution_status.md).

After installing, `cd` into your project root (where `.git/` lives) and run `ait setup` to install dependencies and configure agent integrations. See [`ait setup`](../commands/setup-install/) for details.

Upgrade an existing installation:

```bash
ait upgrade latest
```

> **Windows users:** Run from a WSL shell, not PowerShell. See the [Windows/WSL guide](windows-wsl/).

> **macOS users:** Apple Terminal.app has limited tmux support (no truecolor, no right-click menu). See the [macOS guide](macos/) for recommended terminal emulators.

> **Already have the global `ait` shim?** Once any install method has placed `ait` on your PATH, you can bootstrap aitasks in any new project directory by running `ait setup` there — the shim auto-downloads the framework on first run. Make sure you are at the root of the git repository (where `.git/` lives), not in a subdirectory.

## Setup topics

After installing, see these guides for the rest of the environment:

- [Terminal Setup]({{< relref "terminal-setup" >}}) — terminal emulator + tmux, `ait ide` workflow.
- [Git Remotes]({{< relref "git-remotes" >}}) — auth for GitHub / GitLab / Bitbucket (required for locking, sync, issues).
- [PyPy Runtime]({{< relref "pypy" >}}) — optional faster runtime for long-running TUIs.
- [Updating Model Lists]({{< relref "updating-model-lists" >}}) — refresh the supported model lists used by `ait codeagent` and the Settings TUI.
- [Known Agent Issues]({{< relref "known-issues" >}}) — current Claude Code / Gemini CLI / Codex CLI / OpenCode caveats.

## Cloning a Repo That Already Uses aitasks

If you `git clone` a repository that already has aitasks installed in
data-branch mode (the default for projects bootstrapped with current
versions), the working tree will look "empty" until you run setup:

```bash
cd /path/to/cloned-repo    # the git repository root
./ait setup
```

> **Use `./ait`, not `ait`.** On a fresh clone the global `ait` shim at
> `~/.local/bin/ait` may not be installed yet, or may not be on `PATH`.
> The project-local `./ait` dispatcher is always present in the repo root.

`./ait setup` detects the existing remote `aitask-data` branch and:

1. Fetches the `aitask-data` branch from the remote.
2. Creates the `.aitask-data/` git worktree checked out at that branch.
3. Replaces the empty `aitasks/` and `aiplans/` directories with symlinks
   into the worktree, so task and plan files appear in the usual places.
4. Initializes per-user state (`aitasks/metadata/userconfig.yaml`, etc.).

### Symptoms before running setup

If you see any of these on a fresh clone, run `./ait setup`:

- `aitasks/` exists but contains only an empty `metadata/` subdirectory —
  no task files visible.
- `ait board` (or `./ait board`) shows no tasks.
- `./ait git-health` reports:
  `Mode: legacy (no separate .aitask-data worktree) — nothing to check.`
- `git branch -a` shows a remote `aitask-data` branch that is not checked
  out anywhere locally.

For background on why task data lives on a separate branch, see the
[Git branching model]({{< relref "/docs/concepts/git-branching-model" >}}).

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

- CLI tools: `fzf`, `gh` (for GitHub), `glab` (for GitLab), or `bkt` (for Bitbucket), `jq`, `git`, `zstd`
- Python venv at `~/.aitask/venv/` with `textual` (>=8.1), `pyyaml`, `linkify-it-py`, `tomli` (plus optional `plotext` when enabled for `ait stats-tui` chart panes). Versions are pinned — see `ait setup` for details
- Optional: PyPy 3.11 venv at `~/.aitask/pypy_venv/` for faster long-running TUIs — see [PyPy Runtime]({{< relref "pypy" >}})
- Global `ait` shim at `~/.local/bin/ait`
- Claude Code permissions in `.claude/settings.local.json` (see [Claude Code Permissions](../commands/setup-install/#claude-code-permissions))

---

**Next:** [Getting Started]({{< relref "getting-started" >}})
