---
title: "macOS Installation"
linkTitle: "macOS"
weight: 22
description: "Install aitasks on macOS via Homebrew, with notes on terminal-emulator choice"
depth: [intermediate]
---

Install aitasks on macOS via the official Homebrew tap, then configure your terminal emulator for the best `ait ide` experience.

## Prerequisites

- macOS 12 (Monterey) or newer.
- [Homebrew](https://brew.sh) — required. The `brew install` command below will not run without it.

## What you get

`brew install` places the **aitasks global shim** (a single ~3 KB shell script) at `$(brew --prefix)/bin/ait`. The shim is *not* the framework itself — when you run `ait setup` in a project, the shim downloads the appropriate framework version into that project. This means:

- The installed package stays tiny (~3 KB).
- Framework updates do NOT require re-installing the package; `ait upgrade latest` (or simply running `ait setup` in a fresh project) fetches the newest framework on demand.
- `ait --version` *outside* a project shows the shim version; *inside* a project it shows the framework version installed in that project. They are independent.

For the full design rationale, see [`aidocs/packaging_strategy.md`](https://github.com/beyondeye/aitasks/blob/main/aidocs/packaging_strategy.md).

## Install

```bash
brew install beyondeye/aitasks/aitasks
```

This installs the formula from the [`beyondeye/homebrew-aitasks`](https://github.com/beyondeye/homebrew-aitasks) tap (auto-tapped by the qualified install command).

## First project

```bash
cd /path/to/your-project    # the git repository root
ait setup
```

`ait setup` installs framework dependencies (Python venv, `fzf`, `gh`/`glab`, `jq`, `git`, `zstd`, etc. — pulled in via Homebrew) and downloads the framework files into your project.

## Upgrade

Framework upgrades are per-project. Inside any project that already has aitasks set up, run:

```bash
ait upgrade latest
```

## Uninstall

```bash
brew uninstall aitasks
```

> **Note:** Uninstalling the formula removes the `ait` shim only. Per-project files in `aitasks/` and `aiplans/` remain in your repo (committed to git as normal). To stop using aitasks in a specific project, simply remove those directories from the repo and commit.

## Terminal emulator choice (important)

The `ait ide` workflow runs aitasks TUIs (board, monitor, codebrowser, brainstorm, …) inside tmux. The starter `~/.tmux.conf` installed by `ait setup` enables 24-bit truecolor and mouse / right-click context menus. **macOS's stock Apple Terminal.app does not support either**:

- **No 24-bit truecolor.** Apple Terminal silently quantizes 24-bit color escapes to 256 colors (or ignores them), so TUI panes render with washed-out or incorrect colors.
- **No tmux right-click option menu.** Apple Terminal does not pass the right-mouse-button events tmux needs, so right-clicking inside a pane does nothing.

### Recommended: use a truecolor terminal

Any modern terminal emulator works as a drop-in replacement. Install one of:

```bash
brew install --cask ghostty     # Ghostty — fast, modern (recommended)
brew install --cask iterm2      # iTerm2 — closest to Apple Terminal in feel
brew install --cask alacritty   # Alacritty
brew install --cask kitty       # kitty
brew install --cask wezterm     # WezTerm
```

No further configuration is needed: the seed `~/.tmux.conf` already advertises RGB, and these terminals support it.

### Fallback: staying on Apple Terminal

If you must keep using Apple Terminal, edit `~/.tmux.conf` and remove (or comment out) the truecolor advertise:

```tmux
# set -ag terminal-overrides ",*:RGB"
```

Then either restart the tmux server (`tmux kill-server`) or reload and recreate panes:

```bash
tmux source-file ~/.tmux.conf
# Then close and reopen each tmux pane so child shells re-inherit TERM.
```

The right-click tmux option menu will still not work — Apple Terminal limitation. Other tmux mouse features (drag-to-select, scroll) will continue to function.

### Verify truecolor in a pane

Open a fresh pane and run:

```bash
echo $TERM            # expect: tmux-256color
tput colors           # expect: 256
printf '\e[38;2;255;100;0mTRUECOLOR\e[0m\n'   # should render in orange on truecolor terminals
```

If the third line shows orange, truecolor is working. If it shows the literal escape, or a quantized color that is clearly not orange, the outer terminal does not support truecolor.

## See also

- [Packaging Distribution Status & Roadmap](https://github.com/beyondeye/aitasks/blob/main/aidocs/packaging_distribution_status.md) — current state of the Homebrew tap and the roadmap toward `homebrew-core`.
- [`ait setup`](../commands/setup-install/) — what `ait setup` configures and how.
- [Terminal Setup]({{< relref "terminal-setup" >}}) — `ait ide` workflow, `tmux` overview, multi-project sessions.
- [Getting Started]({{< relref "/docs/getting-started" >}}) — first task walkthrough.

---

**Next:** [Terminal Setup]({{< relref "terminal-setup" >}})
