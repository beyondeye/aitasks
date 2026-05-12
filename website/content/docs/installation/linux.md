---
title: "Linux Installation"
linkTitle: "Linux"
weight: 24
description: "Install aitasks on Arch, Debian/Ubuntu, Fedora/RHEL, and other Linux distros"
---

Install aitasks on Linux. Pick the section matching your distro family — Arch/Manjaro (AUR), Debian/Ubuntu/WSL (.deb), or Fedora/RHEL/Rocky/Alma (.rpm). All three paths install the same ~3 KB global `ait` shim; the framework itself is downloaded on demand by `ait setup` when you run it in a project.

## What you get

Each distro install path places the **aitasks global shim** (a single ~3 KB shell script) at `/usr/bin/ait`. The shim is *not* the framework itself — when you run `ait setup` in a project, the shim downloads the appropriate framework version into that project. This means:

- The installed package stays tiny (~3 KB).
- Framework updates do NOT require re-installing the package; `ait upgrade latest` (or simply running `ait setup` in a fresh project) fetches the newest framework on demand.
- `ait --version` *outside* a project shows the shim version; *inside* a project it shows the framework version installed in that project. They are independent.

For the full design rationale, see [`aidocs/packaging_strategy.md`](https://github.com/beyondeye/aitasks/blob/main/aidocs/packaging_strategy.md).

---

## Arch / Manjaro (AUR)

Install aitasks on Arch Linux, Manjaro, and other Arch derivatives via the [`aitasks`](https://aur.archlinux.org/packages/aitasks) AUR package.

> **`pacman -S aitasks` does NOT work.** aitasks lives in the [Arch User Repository (AUR)](https://aur.archlinux.org/), not in the official Arch repositories (`core` / `extra`). You need an AUR helper (`yay`, `paru`) — or `git clone` + `makepkg -si` — to install it. See the [Roadmap subsection below](#arch--manjaro-roadmap) for the path toward an official Arch repo entry.

### Install — with an AUR helper (recommended)

```bash
yay -S aitasks
# or
paru -S aitasks
```

Both helpers handle the AUR clone + `makepkg` build + dependency resolution automatically.

### Install — without an AUR helper (manual)

```bash
git clone https://aur.archlinux.org/aitasks.git
cd aitasks
makepkg -si
```

`makepkg -si` builds the package, installs runtime dependencies via `pacman`, and installs the resulting `aitasks-*.pkg.tar.zst`.

### First project (Arch)

```bash
cd /path/to/your-project    # the git repository root
ait setup
```

`ait setup` installs framework dependencies (Python venv, agent integrations, etc.) and downloads the framework files into your project. The base CLI tools (`fzf`, `jq`, `git`, `zstd`, etc.) are already installed as `pacman` dependencies of the AUR package.

### Upgrade (Arch)

```bash
yay -Syu aitasks
# or
paru -Syu aitasks
```

The AUR package is auto-bumped on every aitasks release.

### Uninstall (Arch)

```bash
sudo pacman -R aitasks
```

> **Note:** Uninstalling the package removes the `ait` shim only. Per-project files in `aitasks/` and `aiplans/` remain in your repo (committed to git as normal).

### Arch / Manjaro roadmap

The AUR is community-curated and unsigned by Arch maintainers. Moving aitasks into the official Arch `extra` repo (so plain `pacman -S aitasks` would work) requires a Trusted User sponsor. See [Packaging Distribution Status & Roadmap](https://github.com/beyondeye/aitasks/blob/main/aidocs/packaging_distribution_status.md#aur-arch--manjaro--community-curated-not-official) for the concrete steps and current status.

---

## Debian / Ubuntu / WSL (.deb)

Install aitasks on Debian, Ubuntu, and WSL2 via the official `.deb` package, distributed as a [GitHub Releases](https://github.com/beyondeye/aitasks/releases/latest) asset.

### Supported versions

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

### Install — with `gh` (GitHub CLI), simplest

```bash
gh release download --repo beyondeye/aitasks --pattern '*.deb'
sudo apt install ./aitasks_*.deb
```

### Install — without `gh` (curl one-liner)

```bash
DEB_URL=$(curl -s https://api.github.com/repos/beyondeye/aitasks/releases/latest \
  | grep -o 'https://[^"]*aitasks_[^"]*_all\.deb' | head -1)
curl -fsSL "$DEB_URL" -o /tmp/aitasks.deb
sudo apt install /tmp/aitasks.deb
```

### Install — manual download

Browse to [Releases](https://github.com/beyondeye/aitasks/releases/latest), download the `aitasks_<ver>_all.deb` asset, then:

```bash
sudo apt install ./aitasks_*.deb
```

### First project (Debian/Ubuntu)

```bash
cd /path/to/your-project    # the git repository root
ait setup
```

`ait setup` installs framework dependencies (Python venv, agent integrations, etc.) and downloads the framework files into your project. Base CLI tools (`fzf`, `jq`, `git`, `zstd`, `tar`, `curl`) and `python3 >= 3.9` are already installed as apt dependencies of the `.deb`. `gh` and `glab` are recommended; install whichever your remote uses.

### WSL notes

WSL2 with Ubuntu 22.04+ or Debian 12+ works identically to native Linux — the `.deb` install is the recommended path for WSL. Run all install commands inside your WSL shell, not PowerShell. See the [Windows/WSL guide](windows-wsl/) for WSL setup details.

### Upgrade (Debian/Ubuntu)

Same flow as install — download the new `.deb` and:

```bash
sudo apt install ./aitasks_*.deb
```

apt detects the existing install and upgrades in place.

### Uninstall (Debian/Ubuntu)

```bash
sudo apt remove aitasks
```

> **Note:** Uninstalling removes the `ait` shim only. Per-project files in `aitasks/` and `aiplans/` remain in your repo (committed to git as normal).

### Debian / Ubuntu roadmap

The `.deb` is currently distributed only via GitHub Releases — there is no hosted apt repo yet, so `apt update` will not pick up new versions automatically. See [Packaging Distribution Status & Roadmap](https://github.com/beyondeye/aitasks/blob/main/aidocs/packaging_distribution_status.md#apt-deb--debian--ubuntu--wsl--github-releases-asset) for the concrete steps toward a hosted repo at `apt.aitasks.io` and (longer-term) inclusion in official Debian.

---

## Fedora / RHEL / Rocky / Alma (.rpm)

Install aitasks on Fedora, RHEL, Rocky Linux, and AlmaLinux via the official `.rpm` package, distributed as a [GitHub Releases](https://github.com/beyondeye/aitasks/releases/latest) asset.

### Supported distros

- **Fedora 40+** — works directly. Fedora's main repos ship `python3 >= 3.12` and `fzf`, satisfying all aitasks dependencies.
- **Rocky Linux 9 / AlmaLinux 9 / RHEL 9** — supported, but require [EPEL](https://docs.fedoraproject.org/en-US/epel/) to be enabled first (see callout below).

> **Rocky / Alma / RHEL 9 users:** Enable EPEL before installing aitasks — `fzf` (a runtime dependency) lives in EPEL on these distros, not in their base repos:
> ```bash
> sudo dnf install epel-release
> ```
> Fedora ships `fzf` in its main repos; no EPEL needed there.

### Install — with `gh` (GitHub CLI), simplest

```bash
gh release download --repo beyondeye/aitasks --pattern '*.rpm'
sudo dnf install ./aitasks-*.noarch.rpm
```

### Install — without `gh` (curl one-liner)

```bash
RPM_URL=$(curl -s https://api.github.com/repos/beyondeye/aitasks/releases/latest \
  | grep -o 'https://[^"]*aitasks-[^"]*\.noarch\.rpm' | head -1)
curl -fsSL "$RPM_URL" -o /tmp/aitasks.rpm
sudo dnf install /tmp/aitasks.rpm
```

### Install — manual download

Browse to [Releases](https://github.com/beyondeye/aitasks/releases/latest), download the `aitasks-<ver>-1.noarch.rpm` asset, then:

```bash
sudo dnf install ./aitasks-*.noarch.rpm
```

### First project (Fedora)

```bash
cd /path/to/your-project    # the git repository root
ait setup
```

`ait setup` installs framework dependencies (Python venv, agent integrations, etc.) and downloads the framework files into your project. Base CLI tools (`fzf`, `jq`, `git`, `zstd`, `tar`, `curl`) and `python3 >= 3.9` are already installed as dnf dependencies of the `.rpm`. `gh` and `glab` are recommended; install whichever your remote uses.

### Upgrade (Fedora)

Download the new `.rpm` (same path as install) and:

```bash
sudo dnf upgrade ./aitasks-*.noarch.rpm
```

### Uninstall (Fedora)

```bash
sudo dnf remove aitasks
```

> **Note:** Uninstalling removes the `ait` shim only. Per-project files in `aitasks/` and `aiplans/` remain in your repo (committed to git as normal).

### Fedora roadmap

The `.rpm` is currently distributed only via GitHub Releases — there is no [Fedora COPR](https://copr.fedorainfracloud.org/) project or hosted DNF repo yet, so `dnf upgrade` will not pick up new versions automatically. See [Packaging Distribution Status & Roadmap](https://github.com/beyondeye/aitasks/blob/main/aidocs/packaging_distribution_status.md#dnf-rpm--fedora--rhel--rocky--alma--github-releases-asset) for the concrete steps toward COPR (the next planned channel) and (longer-term) official Fedora / EPEL inclusion.

## See also

- [GitHub Releases](https://github.com/beyondeye/aitasks/releases/latest) — `.deb` and `.rpm` artifacts.
- [AUR package page](https://aur.archlinux.org/packages/aitasks)
- [Packaging Distribution Status & Roadmap](https://github.com/beyondeye/aitasks/blob/main/aidocs/packaging_distribution_status.md) — current state of every Linux channel and roadmap toward official repos.
- [`ait setup`](../commands/setup-install/) — what `ait setup` configures and how.
- [Windows/WSL Installation Guide](windows-wsl/) — WSL2 host-side setup preceding the Debian/Ubuntu `.deb` path.
- [Getting Started]({{< relref "/docs/getting-started" >}}) — first task walkthrough.
