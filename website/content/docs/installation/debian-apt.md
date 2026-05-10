---
title: "Debian / Ubuntu / WSL Installation (.deb)"
linkTitle: "Debian/Ubuntu (.deb)"
weight: 40
description: "Install aitasks on Debian, Ubuntu, and WSL via the .deb package"
---

Install aitasks on Debian, Ubuntu, and WSL2 via the official `.deb` package, distributed as a [GitHub Releases](https://github.com/beyondeye/aitasks/releases/latest) asset.

## Supported versions

- **Works directly:** Debian 11 (Bullseye) and newer; Ubuntu 22.04 (Jammy) and newer. These ship `python3 >= 3.9`, which satisfies the `.deb`'s declared dependency.
- **Ubuntu 20.04 (Focal):** `apt install ./aitasks_*.deb` is **blocked by apt's dependency solver** because Focal ships `python3 = 3.8`. Two workarounds:
  1. Install a newer Python from the [deadsnakes PPA](https://launchpad.net/~deadsnakes/+archive/ubuntu/ppa) first, then proceed with the `.deb` install.
  2. **Skip the `.deb` and use the curl install path (recommended for Focal users).** `ait setup` will install a modern Python (3.11) user-scoped via [uv](https://github.com/astral-sh/uv) into `~/.aitask/python/`, independent of the system Python. No sudo needed beyond the base package install:
     ```bash
     cd /path/to/your-project
     curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh | bash
     ait setup
     ```

WSL2 (Ubuntu/Debian) uses the same install path as native — no extra steps.

## What you get

`apt install` places the **aitasks global shim** (a single ~3 KB shell script) at `/usr/bin/ait`. The shim is *not* the framework itself — when you run `ait setup` in a project, the shim downloads the appropriate framework version into that project. This means:

- The installed package stays tiny (~3 KB).
- Framework updates do NOT require re-installing the package; `ait upgrade latest` (or simply running `ait setup` in a fresh project) fetches the newest framework on demand.
- `ait --version` *outside* a project shows the shim version; *inside* a project it shows the framework version installed in that project. They are independent.

For the full design rationale, see [`aidocs/packaging_strategy.md`](https://github.com/beyondeye/aitasks/blob/main/aidocs/packaging_strategy.md).

## Install

Pick whichever path is easiest for you:

### With `gh` (GitHub CLI) — simplest

```bash
gh release download --repo beyondeye/aitasks --pattern '*.deb'
sudo apt install ./aitasks_*.deb
```

### Without `gh` — curl one-liner

```bash
DEB_URL=$(curl -s https://api.github.com/repos/beyondeye/aitasks/releases/latest \
  | grep -o 'https://[^"]*aitasks_[^"]*_all\.deb' | head -1)
curl -fsSL "$DEB_URL" -o /tmp/aitasks.deb
sudo apt install /tmp/aitasks.deb
```

### Manual download

Browse to [Releases](https://github.com/beyondeye/aitasks/releases/latest), download the `aitasks_<ver>_all.deb` asset, then:

```bash
sudo apt install ./aitasks_*.deb
```

## First project

```bash
cd /path/to/your-project    # the git repository root
ait setup
```

`ait setup` installs framework dependencies (Python venv, agent integrations, etc.) and downloads the framework files into your project. Base CLI tools (`fzf`, `jq`, `git`, `zstd`, `tar`, `curl`) and `python3 >= 3.9` are already installed as apt dependencies of the `.deb`. `gh` and `glab` are recommended; install whichever your remote uses.

## WSL notes

WSL2 with Ubuntu 22.04+ or Debian 12+ works identically to native Linux — the `.deb` install is the recommended path for WSL. Run all install commands inside your WSL shell, not PowerShell. See the [Windows/WSL guide](windows-wsl/) for WSL setup details.

## Upgrade

Same flow as install — download the new `.deb` and:

```bash
sudo apt install ./aitasks_*.deb
```

apt detects the existing install and upgrades in place.

## Uninstall

```bash
sudo apt remove aitasks
```

> **Note:** Uninstalling removes the `ait` shim only. Per-project files in `aitasks/` and `aiplans/` remain in your repo (committed to git as normal).

## Roadmap

The `.deb` is currently distributed only via GitHub Releases — there is no hosted apt repo yet, so `apt update` will not pick up new versions automatically. See [Packaging Distribution Status & Roadmap](https://github.com/beyondeye/aitasks/blob/main/aidocs/packaging_distribution_status.md#apt-deb--debian--ubuntu--wsl--github-releases-asset) for the concrete steps toward a hosted repo at `apt.aitasks.io` and (longer-term) inclusion in official Debian.

## See also

- [GitHub Releases](https://github.com/beyondeye/aitasks/releases/latest) — `.deb` artifacts.
- [Packaging Distribution Status & Roadmap](https://github.com/beyondeye/aitasks/blob/main/aidocs/packaging_distribution_status.md) — current state of the APT channel and the roadmap toward hosted-repo / official-Debian distribution.
- [`ait setup`](../commands/setup-install/) — what `ait setup` configures and how.
- [Windows/WSL Installation Guide](windows-wsl/) — WSL2 setup before this `.deb` install.
- [Getting Started]({{< relref "/docs/getting-started" >}}) — first task walkthrough.
