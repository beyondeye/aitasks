---
title: "Fedora / RHEL / Rocky / Alma Installation (.rpm)"
linkTitle: "Fedora (.rpm)"
weight: 50
description: "Install aitasks on Fedora, RHEL, Rocky Linux, and AlmaLinux via the .rpm package"
---

Install aitasks on Fedora, RHEL, Rocky Linux, and AlmaLinux via the official `.rpm` package, distributed as a [GitHub Releases](https://github.com/beyondeye/aitasks/releases/latest) asset.

## Supported distros

- **Fedora 40+** — works directly. Fedora's main repos ship `python3 >= 3.12` and `fzf`, satisfying all aitasks dependencies.
- **Rocky Linux 9 / AlmaLinux 9 / RHEL 9** — supported, but require [EPEL](https://docs.fedoraproject.org/en-US/epel/) to be enabled first (see callout below).

> **Rocky / Alma / RHEL 9 users:** Enable EPEL before installing aitasks — `fzf` (a runtime dependency) lives in EPEL on these distros, not in their base repos:
> ```bash
> sudo dnf install epel-release
> ```
> Fedora ships `fzf` in its main repos; no EPEL needed there.

## What you get

`dnf install` places the **aitasks global shim** (a single ~3 KB shell script) at `/usr/bin/ait`. The shim is *not* the framework itself — when you run `ait setup` in a project, the shim downloads the appropriate framework version into that project. This means:

- The installed package stays tiny (~3 KB).
- Framework updates do NOT require re-installing the package; `ait upgrade latest` (or simply running `ait setup` in a fresh project) fetches the newest framework on demand.
- `ait --version` *outside* a project shows the shim version; *inside* a project it shows the framework version installed in that project. They are independent.

For the full design rationale, see [`aidocs/packaging_strategy.md`](https://github.com/beyondeye/aitasks/blob/main/aidocs/packaging_strategy.md).

## Install

Pick whichever path is easiest for you:

### With `gh` (GitHub CLI) — simplest

```bash
gh release download --repo beyondeye/aitasks --pattern '*.rpm'
sudo dnf install ./aitasks-*.noarch.rpm
```

### Without `gh` — curl one-liner

```bash
RPM_URL=$(curl -s https://api.github.com/repos/beyondeye/aitasks/releases/latest \
  | grep -o 'https://[^"]*aitasks-[^"]*\.noarch\.rpm' | head -1)
curl -fsSL "$RPM_URL" -o /tmp/aitasks.rpm
sudo dnf install /tmp/aitasks.rpm
```

### Manual download

Browse to [Releases](https://github.com/beyondeye/aitasks/releases/latest), download the `aitasks-<ver>-1.noarch.rpm` asset, then:

```bash
sudo dnf install ./aitasks-*.noarch.rpm
```

## First project

```bash
cd /path/to/your-project    # the git repository root
ait setup
```

`ait setup` installs framework dependencies (Python venv, agent integrations, etc.) and downloads the framework files into your project. Base CLI tools (`fzf`, `jq`, `git`, `zstd`, `tar`, `curl`) and `python3 >= 3.9` are already installed as dnf dependencies of the `.rpm`. `gh` and `glab` are recommended; install whichever your remote uses.

## Upgrade

Download the new `.rpm` (same path as install) and:

```bash
sudo dnf upgrade ./aitasks-*.noarch.rpm
```

## Uninstall

```bash
sudo dnf remove aitasks
```

> **Note:** Uninstalling removes the `ait` shim only. Per-project files in `aitasks/` and `aiplans/` remain in your repo (committed to git as normal).

## Roadmap

The `.rpm` is currently distributed only via GitHub Releases — there is no [Fedora COPR](https://copr.fedorainfracloud.org/) project or hosted DNF repo yet, so `dnf upgrade` will not pick up new versions automatically. See [Packaging Distribution Status & Roadmap](https://github.com/beyondeye/aitasks/blob/main/aidocs/packaging_distribution_status.md#dnf-rpm--fedora--rhel--rocky--alma--github-releases-asset) for the concrete steps toward COPR (the next planned channel) and (longer-term) official Fedora / EPEL inclusion.

## See also

- [GitHub Releases](https://github.com/beyondeye/aitasks/releases/latest) — `.rpm` artifacts.
- [Packaging Distribution Status & Roadmap](https://github.com/beyondeye/aitasks/blob/main/aidocs/packaging_distribution_status.md) — current state of the DNF channel and the roadmap toward COPR / official Fedora / EPEL.
- [`ait setup`](../commands/setup-install/) — what `ait setup` configures and how.
- [Getting Started]({{< relref "/docs/getting-started" >}}) — first task walkthrough.
