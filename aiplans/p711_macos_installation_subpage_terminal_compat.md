---
Task: t711_macos_installation_subpage_terminal_compat.md
Base branch: main
plan_verified: []
---

# Plan — t711: macOS Installation Subpage Covering Terminal Compatibility

## Context

The aitasks `ait ide` workflow runs on tmux with a recommended `~/.tmux.conf` (installed by `ait setup` from `seed/tmux.conf`) that advertises 24-bit truecolor (`set -ag terminal-overrides ",*:RGB"`) and enables tmux's mouse / right-click option menu (`set -g mouse on`). On macOS, the default **Apple Terminal.app** does not support 24-bit color and does not deliver right-click events to tmux, so the aitasks TUIs (board, monitor, codebrowser, brainstorm, …) render with washed-out / wrong colors and the right-click menu is non-functional.

This is currently undocumented. The `installation/_index.md` Platform Support row for macOS only mentions Homebrew; `installation/terminal-setup.md` lists good terminals (Ghostty, iTerm2, Alacritty, kitty, WezTerm, Konsole, gnome-terminal) but is silent on Apple Terminal. There is a `windows-wsl.md` platform-specific subpage but no parallel macOS one.

This task is **documentation only**. It adds a new `installation/macos.md` subpage and surfaces the Apple Terminal caveat from the existing pages. It does NOT modify `seed/tmux.conf` itself — that's a separate decision.

## Files to modify / create

| File | Change |
|------|--------|
| `website/content/docs/installation/macos.md` | **Create new.** Platform subpage parallel to `windows-wsl.md`. |
| `website/content/docs/installation/_index.md` | Update Platform Support table macOS row + add a `**macOS users:**` callout below the existing `**Windows users:**` line. |
| `website/content/docs/installation/terminal-setup.md` | Add a brief Apple Terminal caveat in the Requirements section's terminal-emulator bullet, with a link to `macos.md`. |

No code changes. No `seed/`, no scripts, no skill files.

## Step-by-step

### 1. Create `website/content/docs/installation/macos.md`

Frontmatter and structure mirror `windows-wsl.md` (weight: 25, slotting between windows-wsl=20 and terminal-setup=30):

```markdown
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
```

### 2. Update `website/content/docs/installation/_index.md`

#### 2a. Update Platform Support table macOS row (line 94)

Current:
```
| macOS | Fully supported | Requires [Homebrew](https://brew.sh); `ait setup` installs bash 5, coreutils, and other dependencies |
```

Replace with:
```
| macOS | Fully supported | Requires [Homebrew](https://brew.sh); see the [macOS guide](macos/) for terminal-emulator recommendations |
```

#### 2b. Add `**macOS users:**` callout under the existing Windows callout (after line 20)

Current:
```markdown
> **Windows users:** Run this inside a WSL shell, not PowerShell. See the [Windows/WSL guide](windows-wsl/).
```

Add directly after:
```markdown
> **macOS users:** Apple Terminal.app has limited tmux support (no truecolor, no right-click menu). See the [macOS guide](macos/) for recommended terminal emulators.
```

### 3. Update `website/content/docs/installation/terminal-setup.md`

#### Update the Requirements section's terminal-emulator bullet (line 20)

Current:
```markdown
- **A terminal emulator** — any modern choice works. Good options include [Ghostty](https://ghostty.org/), [WezTerm](https://wezfurlong.org/wezterm/), [Alacritty](https://alacritty.org/), [kitty](https://sw.kovidgoyal.net/kitty/), [iTerm2](https://iterm2.com/), [Konsole](https://konsole.kde.org/), or [gnome-terminal](https://help.gnome.org/users/gnome-terminal/stable/). They are listed without ranking — pick whatever you already use.
```

Replace with (only the trailing sentence changes — append a macOS caveat):
```markdown
- **A terminal emulator** — any modern choice works. Good options include [Ghostty](https://ghostty.org/), [WezTerm](https://wezfurlong.org/wezterm/), [Alacritty](https://alacritty.org/), [kitty](https://sw.kovidgoyal.net/kitty/), [iTerm2](https://iterm2.com/), [Konsole](https://konsole.kde.org/), or [gnome-terminal](https://help.gnome.org/users/gnome-terminal/stable/). They are listed without ranking — pick whatever you already use. **macOS users:** the stock Apple Terminal.app is not recommended — it lacks truecolor and the tmux right-click menu does not work. See the [macOS guide]({{< relref "macos" >}}) for details.
```

## Verification

1. **Hugo build succeeds with no broken-link warnings:**
   ```bash
   cd website
   hugo build --gc --minify
   ```
   Watch for warnings related to `macos`, `windows-wsl`, `terminal-setup`, or `_index`.

2. **Local dev server renders the new page:**
   ```bash
   cd website
   ./serve.sh
   ```
   Open http://localhost:1313/docs/installation/macos/ and confirm:
   - Page renders with all sections
   - Cross-references resolve (Homebrew link, internal `git-remotes`/`terminal-setup` relrefs)
   - The page appears in the left-side nav under Installation, between "Windows/WSL" and "Terminal Setup" (weight 25)

3. **Verify cross-links from neighbour pages:**
   - `/docs/installation/` — Platform Support table macOS row links to `macos/`; `**macOS users:**` callout shows under `**Windows users:**`
   - `/docs/installation/terminal-setup/` — Requirements bullet now contains the Apple Terminal caveat with a working link to the macOS page

4. **No regressions on existing pages** — open `windows-wsl/`, `git-remotes/`, `known-issues/`, `terminal-setup/` and confirm they still render correctly.

## Notes

- All cross-references use `{{< relref ... >}}` for absolute robustness, except the Platform Support table cell and the callouts which use the existing convention of a relative path (e.g., `macos/`, `windows-wsl/`) to match the file's existing style.
- Do not modify `seed/tmux.conf`. The current `*:RGB` line is correct for the recommended terminal emulators; making it conditional on the outer terminal would be a runtime-detection feature and is explicitly out of scope.
- After edits, follow Step 8 of the standard workflow: present `git status` / `git diff --stat`, then commit with a `documentation: …` message tagged `(t711)`.

## Step 9 reference

After commit, the standard task-workflow Step 9 archival applies: no separate worktree was created, so just run `./.aitask-scripts/aitask_archive.sh 711` and `./ait git push`.

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned. Created `website/content/docs/installation/macos.md` with the full structure from the plan (Prerequisites, Install, Terminal emulator choice with Recommended/Fallback subsections, Verify-truecolor snippet, Next steps). Updated `_index.md` Platform Support macOS row + added `**macOS users:**` callout below the `**Windows users:**` line. Updated `terminal-setup.md` Requirements bullet with a one-sentence Apple Terminal caveat linking back to `macos.md`.
- **Deviations from plan:** None.
- **Issues encountered:** None.
- **Key decisions:** Cross-link convention follows the per-file style — `_index.md` uses bare relative paths (`macos/`, `windows-wsl/`); `terminal-setup.md` uses `{{< relref "macos" >}}`; `macos.md` itself uses `{{< relref ... >}}` for outbound links to neighbour pages.
- **Verification:** `cd website && hugo build --gc --minify` succeeded (179 pages, no warnings). The rendered page exists at `website/public/docs/installation/macos/index.html` with the correct title and meta description.
