---
title: "Terminal Setup"
linkTitle: "Terminal Setup"
weight: 40
description: "Terminal emulator choice, tmux, and the ait ide workflow"
depth: [intermediate]
---

## Terminal emulator vs. terminal multiplexer

Two distinct pieces of software cooperate when you use aitasks from the terminal:

- A **terminal emulator** is the GUI application you run — Ghostty, WezTerm, Alacritty, kitty, iTerm2, Konsole, gnome-terminal, and so on.
- A **terminal multiplexer** runs *inside* a terminal emulator and splits your single terminal window into multiple independent sessions, windows, and panes. [**tmux**](https://github.com/tmux/tmux/wiki) is the multiplexer aitasks integrates with.

tmux is **not** a terminal emulator — it always runs inside one.

## Requirements

- **A terminal emulator** — any modern choice works. Good options include [Ghostty](https://ghostty.org/), [WezTerm](https://wezfurlong.org/wezterm/), [Alacritty](https://alacritty.org/), [kitty](https://sw.kovidgoyal.net/kitty/), [iTerm2](https://iterm2.com/), [Konsole](https://konsole.kde.org/), or [gnome-terminal](https://help.gnome.org/users/gnome-terminal/stable/). They are listed without ranking — pick whatever you already use. **macOS users:** the stock Apple Terminal.app is not recommended — it lacks truecolor and the tmux right-click menu does not work. See the [macOS guide]({{< relref "macos" >}}) for details.
- **[tmux](https://github.com/tmux/tmux/wiki) 3.x or newer** — required for the recommended workflow below. Install with your package manager (`brew install tmux`, `apt install tmux`, `pacman -S tmux`, etc.).
- **ait** — installed and `ait setup` already run in your project. See the [installation overview]({{< relref "_index" >}}) if you haven't done that yet.

## Recommended workflow — `ait ide`

The recommended way to start working on a project is a single command:

```bash
cd /path/to/your/project
ait ide
```

That's it. `ait ide` is the headline entry point into the aitasks "IDE" — a single command that opens tmux, creates the session, and launches `ait monitor` in one go.

Here's what happens under the hood:

1. `ait ide` reads the tmux session name from `aitasks/metadata/project_config.yaml` under `tmux.default_session` (defaults to `aitasks` if unset), then attaches to — or creates — a tmux session with that exact name **on the framework's dedicated tmux server** (named socket `ait`, kept separate from your personal default tmux server — see [the dedicated tmux server](#the-dedicated-tmux-server) below). Because the session name is always explicit, `ait monitor` never has to fall back to its interactive `SessionRenameDialog` on the happy path.
2. A `monitor` window is created (or focused) inside the session, running [`ait monitor`](../../tuis/monitor/). From the monitor you get a live dashboard of running code agents, open TUIs, and other panes in the session.
3. Press **`j`** inside any main aitasks TUI (`ait board`, `ait monitor`, `ait minimonitor`, `ait codebrowser`, `ait settings`, `ait brainstorm`, `ait syncer`) to open the **TUI switcher** dialog and jump to another TUI without leaving tmux.

<!-- TODO screenshot: aitasks_ait_ide_startup.svg — the monitor dashboard immediately after running `ait ide` -->

### Flags

`ait ide` is intentionally minimal:

- `--session NAME` — use `NAME` instead of the configured `tmux.default_session`. Useful for running multiple projects side-by-side (see the gotcha below).
- `-h`, `--help` — print usage and the shared-session note.

If you are already inside a tmux session whose name matches the configured one, `ait ide` just selects (or creates) the `monitor` window in your current session. If you are inside a tmux session whose name *differs*, `ait ide` refuses to nest — it prints a warning and exits non-zero rather than silently picking the wrong session.

### One gotcha: `ait ide` is one view of a shared session

This is the single most common source of confusion, so it is worth calling out on its own.

tmux sessions are **shared across terminal clients**. If you open a second terminal and run `ait ide` again, you do **not** get a separate IDE — you get another view of the same session, showing the same windows, panes, and TUIs. Opening a window, resizing a pane, or switching TUIs in one terminal is immediately visible in all the others.

To work on two projects in parallel, give each one its own session:

```bash
# Project A — uses the default session name
cd ~/code/project-a
ait ide

# Project B — different session
cd ~/code/project-b
ait ide --session project-b
```

Or, better, configure a distinct `tmux.default_session` per project in each project's `aitasks/metadata/project_config.yaml`. Then a plain `ait ide` in each project root just works.

## The dedicated tmux server

All `ait`-managed tmux sessions live on a **dedicated tmux server** on the named socket `ait`, isolated from your personal default tmux server. This means a stray `tmux kill-server` aimed at your own tmux cannot take down running agents, and your personal sessions never mix with framework sessions. To inspect the framework's server directly, add `-L ait` to any tmux command:

```bash
tmux -L ait ls               # list ait-managed sessions
tmux -L ait attach -t aitasks
```

The socket is controlled by the `AITASKS_TMUX_SOCKET` environment variable:

| `AITASKS_TMUX_SOCKET` | Behavior |
|---|---|
| unset | dedicated `ait` socket (the default) |
| a name (e.g. `mysock`) | that named socket |
| `default` | your personal default tmux server (explicit opt-out) |
| set but empty | no socket flag — tmux follows `$TMUX` (legacy behavior) |

**Migrating from an older version:** tmux cannot move sessions between servers, so a session created on your default server before the dedicated-socket change stays there. `ait ide` detects this and offers to attach to the legacy session one last time; you can also reach it any time with `AITASKS_TMUX_SOCKET=default ait ide` (or plain `tmux attach`). Finish or kill the legacy session at your convenience — new sessions are created on the dedicated server.

## Surviving a compositor restart on Linux/Wayland

All `ait`-managed sessions share **one** tmux server — a dedicated one on the named socket `ait` (`tmux -L ait`), kept separate from your personal default tmux server — so if that server is torn down, every session inside it is lost at once. On Linux desktops that launch graphical apps through transient systemd user scopes — most Wayland compositors (Hyprland, Sway) and session managers such as uwsm — that can happen when your graphical session restarts.

When you start the server with [`ait ide`](#recommended-workflow--ait-ide), the framework already guards against this: it spawns the server inside a persistent systemd-user service under `session.slice`, which survives a compositor restart, an `app.slice` teardown, or a logout *of the graphical session*, and ends only at full logout. No action is needed on your part.

The gap is a server you start **yourself** — for example from a compositor keybind or autostart entry that runs `tmux new-session …` directly. That server inherits your graphical session's transient `app.slice` scope; when the compositor restarts (or that scope is otherwise torn down), the scope dies as a unit and takes the tmux server — and all its sessions — with it.

To give a self-launched server the same survival guarantee, wrap the tmux invocation in a persistent systemd-user service under `session.slice`:

```bash
systemd-run --user --slice=session.slice \
    --property=Type=forking --property=KillMode=none --collect \
    -- tmux -L ait new-session -d -s aitasks -c /path/to/your/project -n monitor 'ait monitor'
```

`--slice=session.slice` is the load-bearing flag — it moves the server out of the transient `app.slice` scope into a unit that survives compositor / `app.slice` teardown and ends only at full logout. `--property=Type=forking` matches tmux's double-fork so systemd tracks the daemon, and `--property=KillMode=none` keeps systemd from signalling the server when the launching command returns (tmux owns its own lifecycle via `kill-server`). `-L ait` lands the session on the framework's dedicated server so `ait` tooling can see it. Run it once, then attach as usual with `ait ide` or `tmux -L ait attach -t aitasks`.

> **Omarchy / uwsm users:** uwsm launches apps into `app.slice`, so a `tmux-spawn` keybind that runs `tmux` directly inherits that scope and dies with the compositor. Point the keybind at the `systemd-run --user --slice=session.slice` form above — or simply start your session with `ait ide`, which already does this — so the server persists across compositor restarts.

## Minimal / non-tmux workflow

If you cannot or do not want to use tmux, aitasks still runs. Open your terminal, `cd` to the project, and invoke each `ait` command directly in whichever terminal window or tab you prefer:

```bash
cd /path/to/your/project
ait board      # or: ait monitor, ait codebrowser, ait settings, ...
```

This path is a fallback, not a recommendation. Without tmux you lose:

- The TUI switcher (`j` key) — you cannot jump between TUIs in one keystroke.
- Persistent agent windows — agents launched from the board terminate when you close their terminal, instead of surviving inside a persistent tmux session.
- The unified `ait monitor` dashboard view of all running agents and TUIs.

## Next steps

- [Getting Started](../../getting-started/) — a walkthrough of a first task.
- [Monitor TUI](../../tuis/monitor/) — full details of `ait monitor`, including the agent window list and the TUI switcher.

---

**Next:** [Known Issues]({{< relref "known-issues" >}})
