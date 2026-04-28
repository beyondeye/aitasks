---
priority: medium
effort: low
depends: []
issue_type: documentation
status: Implementing
labels: [macos, installation, web_site, tmux]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-29 00:11
updated_at: 2026-04-29 00:13
---

## Goal

Add a macOS-specific installation/setup subpage to the website covering terminal-emulator compatibility with the aitasks `ait ide` workflow (tmux-based TUIs), and surface the Apple Terminal caveats from existing pages.

## Background

The aitasks-recommended `~/.tmux.conf` (installed by `ait setup` from `seed/tmux.conf`) sets:

```tmux
set -g default-terminal "tmux-256color"
set -ag terminal-overrides ",*:RGB"
set -g mouse on
```

These work correctly on truecolor-capable terminals (Ghostty, iTerm2, Alacritty, kitty, WezTerm, modern Linux terminals) but break under macOS **Apple Terminal.app**:

- **Truecolor:** Apple Terminal does not support 24-bit RGB. With `*:RGB` advertised, tmux emits truecolor escapes that Apple Terminal silently quantizes (or mangles), causing TUIs (board, monitor, codebrowser, brainstorm) to render with washed-out / incorrect colors.
- **Mouse / right-click menu:** Apple Terminal does not deliver the right-mouse-button events that tmux's option menu (enabled via `set -g mouse on`) relies on, so the right-click context menu is non-functional.

These limitations are not currently documented anywhere on the website, and the Platform Support table in `installation/_index.md` only states "macOS — Fully supported. Requires Homebrew."

## Scope

### 1. Add `website/content/docs/installation/macos.md`

Create a new subpage parallel to `windows-wsl.md`:

- Frontmatter:
  - `title: "macOS Installation"`
  - `linkTitle: "macOS"`
  - `weight: 25` (between windows-wsl=20 and terminal-setup=30)
  - `description: "Guide for installing and running aitasks on macOS, including terminal-emulator choice"`
- Sections:
  - **Prerequisites** — Homebrew (link to brew.sh), recap that `ait setup` installs bash 5, Python 3, coreutils, etc.
  - **Install aitasks** — short pointer back to the main install command in `_index.md`.
  - **Terminal emulator choice (important)**
    - Explain that Apple Terminal.app does NOT support 24-bit truecolor and has limited mouse-event support (no right-click → tmux option menu).
    - Recommend a truecolor-capable emulator: **Ghostty** (`brew install --cask ghostty`), **iTerm2** (`brew install --cask iterm2`), **Alacritty**, **kitty**, **WezTerm**.
    - Briefly note that any of those is a drop-in replacement; no further config needed because the seed `~/.tmux.conf` already advertises RGB.
  - **Staying on Apple Terminal (fallback)**
    - If the user must stay on Apple Terminal, comment out or remove `set -ag terminal-overrides ",*:RGB"` in `~/.tmux.conf`.
    - Note that `set -g mouse on` will still partly work (drag-to-select, scroll), but the right-click option menu will not function.
    - After the edit, either `tmux kill-server` or `tmux source-file ~/.tmux.conf` plus closing/reopening panes so child shells inherit corrected `TERM`.
  - **Verification snippet** for a fresh pane:
    ```bash
    echo $TERM            # expect: tmux-256color
    tput colors           # expect: 256
    printf '\e[38;2;255;100;0mTRUECOLOR\e[0m\n'   # should be orange on truecolor terms
    ```
  - **Next:** link to `terminal-setup.md`.

### 2. Update `website/content/docs/installation/_index.md`

In the **Platform Support** table, change the macOS row's Notes from:

> Requires [Homebrew](https://brew.sh); `ait setup` installs bash 5, coreutils, and other dependencies

to include a pointer to the new page, e.g.:

> Requires [Homebrew](https://brew.sh); see the [macOS guide](macos/) for terminal-emulator recommendations.

Also add a `**macOS users:**` callout near the existing `**Windows users:**` line, mirroring the structure.

### 3. Update `website/content/docs/installation/terminal-setup.md`

In the "Requirements" section's terminal-emulator bullet, add a parenthetical note that on macOS the stock **Apple Terminal.app** is not recommended because it lacks truecolor and full mouse support (link to `macos.md` for details). Keep the existing list of good options unchanged.

## Out of scope

- Editing `seed/tmux.conf` itself. The current default (advertise RGB) is correct for the recommended terminal emulators; per-platform conditional config is a separate decision and would deserve its own task. This task is documentation-only.
- Adding runtime detection of Apple Terminal in `ait setup`. Out of scope.

## Acceptance criteria

- New `website/content/docs/installation/macos.md` exists with the sections above and renders cleanly in `cd website && ./serve.sh`.
- `installation/_index.md` Platform Support table macOS row links to the new page.
- `installation/terminal-setup.md` mentions the Apple Terminal caveat with a link to `macos.md`.
- Internal cross-references use `{{< relref ... >}}` (or relative links matching the existing convention in the file being edited).
- Hugo build succeeds: `cd website && hugo build --gc --minify` with no broken-link warnings related to the new page.
