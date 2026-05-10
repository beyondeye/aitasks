---
title: "Arch / Manjaro Installation (AUR)"
linkTitle: "Arch (AUR)"
weight: 30
description: "Install aitasks on Arch Linux and Manjaro via the AUR"
---

Install aitasks on Arch Linux, Manjaro, and other Arch derivatives via the [`aitasks`](https://aur.archlinux.org/packages/aitasks) AUR package.

> **`pacman -S aitasks` does NOT work.** aitasks lives in the [Arch User Repository (AUR)](https://aur.archlinux.org/), not in the official Arch repositories (`core` / `extra`). You need an AUR helper (`yay`, `paru`) — or `git clone` + `makepkg -si` — to install it. See the [Roadmap section below](#roadmap) for the path toward an official Arch repo entry.

## What you get

The AUR install places the **aitasks global shim** (a single ~3 KB shell script) at `/usr/bin/ait`. The shim is *not* the framework itself — when you run `ait setup` in a project, the shim downloads the appropriate framework version into that project. This means:

- The installed package stays tiny (~3 KB).
- Framework updates do NOT require re-installing the package; `ait upgrade latest` (or simply running `ait setup` in a fresh project) fetches the newest framework on demand.
- `ait --version` *outside* a project shows the shim version; *inside* a project it shows the framework version installed in that project. They are independent.

For the full design rationale, see [`aidocs/packaging_strategy.md`](https://github.com/beyondeye/aitasks/blob/main/aidocs/packaging_strategy.md).

## Install

### With an AUR helper (recommended)

```bash
yay -S aitasks
# or
paru -S aitasks
```

Both helpers handle the AUR clone + `makepkg` build + dependency resolution automatically.

### Without an AUR helper (manual)

```bash
git clone https://aur.archlinux.org/aitasks.git
cd aitasks
makepkg -si
```

`makepkg -si` builds the package, installs runtime dependencies via `pacman`, and installs the resulting `aitasks-*.pkg.tar.zst`.

## First project

```bash
cd /path/to/your-project    # the git repository root
ait setup
```

`ait setup` installs framework dependencies (Python venv, agent integrations, etc.) and downloads the framework files into your project. The base CLI tools (`fzf`, `jq`, `git`, `zstd`, etc.) are already installed as `pacman` dependencies of the AUR package.

## Upgrade

```bash
yay -Syu aitasks
# or
paru -Syu aitasks
```

The AUR package is auto-bumped on every aitasks release.

## Uninstall

```bash
sudo pacman -R aitasks
```

> **Note:** Uninstalling the package removes the `ait` shim only. Per-project files in `aitasks/` and `aiplans/` remain in your repo (committed to git as normal).

## Roadmap

The AUR is community-curated and unsigned by Arch maintainers. Moving aitasks into the official Arch `extra` repo (so plain `pacman -S aitasks` would work) requires a Trusted User sponsor. See [Packaging Distribution Status & Roadmap](https://github.com/beyondeye/aitasks/blob/main/aidocs/packaging_distribution_status.md#aur-arch--manjaro--community-curated-not-official) for the concrete steps and current status.

## See also

- [AUR package page](https://aur.archlinux.org/packages/aitasks)
- [Packaging Distribution Status & Roadmap](https://github.com/beyondeye/aitasks/blob/main/aidocs/packaging_distribution_status.md) — current state of the AUR channel and the roadmap toward official Arch `extra`.
- [`ait setup`](../commands/setup-install/) — what `ait setup` configures and how.
- [Getting Started]({{< relref "/docs/getting-started" >}}) — first task walkthrough.
