---
title: "macOS Installation"
linkTitle: "macOS"
weight: 25
description: "Guide for installing and running aitasks on macOS, including terminal-emulator choice"
depth: [intermediate]
---

Step-by-step guide for installing aitasks on macOS, with notes on terminal-emulator compatibility for the recommended `ait ide` workflow.

## Prerequisites

- macOS 12 (Monterey) or newer
- [Homebrew](https://brew.sh) — required. `ait setup` uses it to install bash 5, Python 3, coreutils, `fzf`, `gh`/`glab`/`bkt`, `jq`, `git`, and `zstd`.

## Install aitasks

From your project's git-repository root:

```bash
cd /path/to/your-project
curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh | bash
ait setup
```

If you already have the global `ait` shim installed (from a previous project), you can skip the `curl` step and just run `ait setup` in the new project root — it auto-bootstraps.

After setup completes, see [Authentication with Your Git Remote]({{< relref "git-remotes" >}}) to configure GitHub access.

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

## Next steps

- [Terminal Setup]({{< relref "terminal-setup" >}}) — `ait ide` workflow, `tmux` overview, multi-project sessions.
- [Getting Started]({{< relref "/docs/getting-started" >}}) — first task walkthrough.

---

**Next:** [Terminal Setup]({{< relref "terminal-setup" >}})
