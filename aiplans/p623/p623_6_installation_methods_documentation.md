---
Task: t623_6_installation_methods_documentation.md
Parent Task: aitasks/t623_more_installation_methods.md
Sibling Tasks: aitasks/t623/t623_1_*.md, t623_2_*.md, t623_3_*.md, t623_4_*.md, t623_5_*.md
Archived Sibling Plans: aiplans/archived/p623/p623_1_*.md through p623_5_*.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Implementation Plan: t623_6 — Installation methods documentation

## Prerequisites

t623_2..t623_5 merged — the commands documented below must actually work.

## Steps

### 1. README.md rewrite

Replace the current "Quick Install" section (lines 57–93) with a per-platform table, then add a short paragraph explaining the shim-only model, then keep the `ait setup` next-step note.

Target contents (verbatim starting point — adjust exact wording to match README tone):

```markdown
## ⚡ Quick Install

Pick your platform:

| Platform | Install command |
|----------|-----------------|
| **macOS** | `brew install beyondeye/aitasks/aitasks` — see the [Homebrew guide](https://aitasks.io/docs/installation/macos-brew/) |
| **Arch / Manjaro** (AUR) | `yay -S aitasks` or `paru -S aitasks` — see the [AUR guide](https://aitasks.io/docs/installation/arch-aur/) |
| **Debian / Ubuntu / WSL** | Download the latest `.deb` from [releases](https://github.com/beyondeye/aitasks/releases/latest) and `sudo apt install ./aitasks_*.deb` — see the [Debian/Ubuntu guide](https://aitasks.io/docs/installation/debian-apt/) |
| **Fedora / RHEL / Rocky / Alma** | Download the latest `.rpm` from [releases](https://github.com/beyondeye/aitasks/releases/latest) and `sudo dnf install ./aitasks-*.noarch.rpm` — see the [Fedora guide](https://aitasks.io/docs/installation/fedora-dnf/) |
| **Other (any POSIX)** | `curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh \| bash` |

All install methods drop a single `ait` command on your `$PATH` — the **global shim**. The shim downloads the framework itself on demand when you run `ait setup` in your project, so the package you install is small (~3 KB) and remains current without re-installing the package. See the [installation guide](https://aitasks.io/docs/installation/) for details.

After installing, run `ait setup` in your project to bootstrap the framework.
```

### 2. `website/content/docs/installation/_index.md` rewrite

Mirror the README table; add the shim-only paragraph; add sub-page links that Docsy will render as child entries in the sidebar.

Preserve the existing Docsy frontmatter (title/linkTitle/weight/description).

### 3. Create per-platform sub-pages

Each page follows the same structure:

```markdown
---
title: "<Platform> Installation"
linkTitle: "<Platform>"
weight: <N>
description: "Install aitasks on <platform>"
---

## What you get

`<pm> install` installs the **aitasks global shim** (a single ~3 KB shell script) to `<path>`. The framework itself is downloaded on demand when you run `ait setup` in your project.

## Install

```bash
<install command>
```

## First project

```bash
cd my-project       # must be a git repository root
ait setup
```

## Upgrade

```bash
<upgrade command>
```

## Uninstall

```bash
<uninstall command>
```
```

Per-page specifics:

- **`macos-brew.md`** (weight: 20). Install: `brew install beyondeye/aitasks/aitasks`. Upgrade: `brew update && brew upgrade aitasks`. Uninstall: `brew uninstall aitasks`. Path: `$(brew --prefix)/bin/ait`.
- **`arch-aur.md`** (weight: 30). Install: `yay -S aitasks` OR `git clone https://aur.archlinux.org/aitasks.git && cd aitasks && makepkg -si`. **Must include the explicit note** that plain `pacman -S aitasks` does NOT work because aitasks is in the AUR, not official Arch repos. Upgrade: `yay -Syu aitasks`. Uninstall: `sudo pacman -R aitasks`. Path: `/usr/bin/ait`.
- **`debian-apt.md`** (weight: 40). Install: one-liner that resolves the latest release asset URL and installs:
  ```bash
  curl -fsSL $(curl -s https://api.github.com/repos/beyondeye/aitasks/releases/latest | grep -o 'https://.*/aitasks_.*_all.deb' | head -1) -o /tmp/ait.deb
  sudo apt install ./tmp/ait.deb
  ```
  Supported versions section: Ubuntu 22.04+, Debian 12+. Ubuntu 20.04 and Debian 11 are NOT supported (Python < 3.9). WSL section: same as native Ubuntu, nothing special. Upgrade: same as install (download new .deb, `sudo apt install ./new.deb`). Uninstall: `sudo apt remove aitasks`. Path: `/usr/bin/ait`.
- **`fedora-dnf.md`** (weight: 50). Install: similar one-liner via `dnf install`. Supported: Fedora 40+, Rocky Linux 9, AlmaLinux 9, RHEL 9. Upgrade: `sudo dnf upgrade ./new.rpm`. Uninstall: `sudo dnf remove aitasks`. Path: `/usr/bin/ait`.

### 4. `website/content/docs/installation/windows-wsl.md` update

Add a "Recommended: install via `.deb` inside WSL" section near the top that points to `debian-apt.md`. The existing curl-based content remains as a fallback lower in the page.

## Verification Checklist

- [ ] `cd website && npm install && ./serve.sh` — every new page renders; Docsy sidebar shows all 4 per-platform entries; no broken links.
- [ ] `markdown-link-check website/content/docs/installation/*.md` — all links resolve.
- [ ] Grep for `curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh` — only appears in the "Other" / fallback sections, never as the primary recommendation on macOS/Arch/Debian/Fedora pages.
- [ ] Every per-platform page has: What you get / Install / First project / Upgrade / Uninstall sections.
- [ ] `arch-aur.md` explicitly warns that plain `pacman -S aitasks` does NOT work and shows the `makepkg -si` alternative.
- [ ] Each page mentions the shim-only model (the "What you get" section).
- [ ] README.md renders correctly on GitHub (preview via PR or `gh api markdown`).
- [ ] No version-history prose anywhere; all content describes current state only.

## Final Implementation Notes (to be filled in post-implementation)

- **Actual work done:**
- **Deviations from plan:**
- **Issues encountered:**
- **Key decisions:**
