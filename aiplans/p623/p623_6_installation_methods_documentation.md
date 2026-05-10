---
Task: t623_6_installation_methods_documentation.md
Parent Task: aitasks/t623_more_installation_methods.md
Sibling Tasks: aitasks/t623/t623_1_*.md, t623_2_*.md, t623_3_*.md, t623_4_*.md, t623_5_*.md
Archived Sibling Plans: aiplans/archived/p623/p623_1_*.md through p623_5_*.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-10 13:31
---

# Implementation Plan: t623_6 — Installation methods documentation

## Context

After siblings t623_1..t623_5 shipped Homebrew, AUR, `.deb`, and `.rpm` install channels (plus the shim-only packaging strategy), the user-facing docs (`README.md` and `website/content/docs/installation/`) still present `curl -fsSL .../install.sh | bash` as the only installation method. This task aligns the docs with the actual current state: per-platform PM commands as the primary recommendation; curl as the fallback for "Other POSIX". Each per-PM page also explains the **shim-only** model up front (otherwise users will be confused that brew-installed aitasks is ~3 KB regardless of version, and that `ait --version` in a project differs from `ait --version` outside one).

Convention reminder (from CLAUDE.md): user-facing docs describe the **current** state only. No "previously we only supported curl"; no version-history prose.

## Verification Findings (verify-mode pass, 2026-05-10)

- `README.md` "Quick Install" lives at lines 57–93 — matches the plan's expectation (curl-only block).
- `website/content/docs/installation/_index.md` already exists with sections beyond "Quick Install": **Cloning a Repo That Already Uses aitasks**, **Platform Support**, **What Gets Installed**. These must be preserved during the rewrite.
- `arch-aur.md`, `debian-apt.md`, `fedora-dnf.md` do not exist — new pages, no conflicts.
- `macos.md` **already exists** and covers terminal-emulator choice (Apple Terminal vs Ghostty/iTerm2/etc.) with the old curl install. Inbound links: `_index.md:22`, `_index.md:96`. **Decision: rewrite `macos.md` in place** (lead with brew install; keep terminal-emulator section as a subsection); do NOT create `macos-brew.md`.
- `windows-wsl.md` — exists; the plan's "prepend a `.deb`-recommended section" approach is correct.
- Package filenames (verified from `.github/workflows/release-packaging.yml`):
  - `.deb`: `aitasks_<VERSION>_all.deb` (e.g. `aitasks_0.20.1_all.deb`)
  - `.rpm`: `aitasks-<VERSION>-1.noarch.rpm` (e.g. `aitasks-0.20.1-1.noarch.rpm`)
- Homebrew tap: `beyondeye/homebrew-aitasks` → `brew install beyondeye/aitasks/aitasks` (the `homebrew-` prefix is stripped by the brew shorthand).
- AUR: package name `aitasks` per `aidocs/aur_maintainer_setup.md`. AUR-helper installs work; plain `pacman -S aitasks` does NOT (AUR is not in official Arch repos).
- EPEL prerequisite on Rocky/Alma/RHEL 9: per archived plan `p623_5`, `fzf` is in EPEL on those distros, so users must `sudo dnf install epel-release` before installing the aitasks rpm. Fedora ships `fzf` in main repos; no EPEL needed there.
- Bug in pre-verify plan's debian one-liner: `sudo apt install ./tmp/ait.deb` (relative `./tmp`) — the curl command writes to `/tmp/ait.deb` (absolute). Will use absolute path in the actual docs.
- **Supported-versions correction.** `ait setup` auto-provisions a modern Python (3.11) user-scoped via `uv` when the system Python is too old (see `.aitask-scripts/aitask_setup.sh:374-456`). So the *framework runtime* works on essentially any modern Linux. The constraint is purely at the **package-install layer**: `packaging/nfpm/nfpm.yaml:27` declares `python3 (>= 3.9)` as a hard apt/dnf dependency. Concretely:
  - Ubuntu 20.04 ships `python3=3.8.x` → `apt install ./aitasks_*.deb` is refused by the dependency solver. **Workaround**: install `python3.9+` from the deadsnakes PPA first, OR use the curl install path (`ait setup` provisions Python via uv regardless of system version).
  - Debian 11 ships `python3=3.9.2` → `.deb` install works directly.
  - Ubuntu 22.04+, Debian 12+ → no issue.
  - Fedora 40+ ships `python3=3.12+`; Rocky/Alma/RHEL 9 ship `python3=3.9.x` → all fine for the rpm.

  The previous plan's blanket "Not supported: Ubuntu 20.04 / Debian 11 (Python < 3.9)" is wrong on two counts: Debian 11 *does* ship Python 3.9, and Ubuntu 20.04 is recoverable via curl install or a deadsnakes PPA. Docs will now frame this accurately rather than as a hard "not supported".

## Steps

### 0. Create `aidocs/packaging_distribution_status.md` (new)

**Purpose.** A maintainer-facing reference that captures the *current* status of each PM distribution channel, the limitations users hit, **where each limitation is mentioned in user-facing docs** (so future updates are mechanical), and concrete roadmap steps for moving each channel toward more "official" / first-party distribution. Complements (does not duplicate) the design-oriented `aidocs/packaging_strategy.md`.

**Structure** (sections, in order):

1. **Snapshot table** — one row per PM, **with the live URL where the package currently lives**:
   | PM | Where it lives (live link) | Channel type | Cross-distro reach |
   - Homebrew → `https://github.com/beyondeye/homebrew-aitasks` (custom tap repo)
   - AUR → `https://aur.archlinux.org/packages/aitasks` (AUR package page)
   - APT (.deb) → `https://github.com/beyondeye/aitasks/releases/latest` (asset filename `aitasks_<ver>_all.deb`)
   - DNF (.rpm) → `https://github.com/beyondeye/aitasks/releases/latest` (asset filename `aitasks-<ver>-1.noarch.rpm`)
   The table makes the URL the first identifying field so a maintainer can click straight through to inspect package status / votes / open issues without spelunking through prose.

2. **Per-channel limitations and roadmap.** One subsection each for Homebrew, AUR, APT/.deb, DNF/.rpm. Each subsection contains:
   - **Current state** — exact channel + filename + workflow that publishes it. Each subsection MUST start with a direct link to the package's live location so maintainers can click through:
     - Homebrew: tap repo `https://github.com/beyondeye/homebrew-aitasks`; install command `brew install beyondeye/aitasks/aitasks`.
     - AUR: package page `https://aur.archlinux.org/packages/aitasks`; AUR clone URL `https://aur.archlinux.org/aitasks.git`.
     - APT: GitHub Releases `https://github.com/beyondeye/aitasks/releases/latest`; asset name `aitasks_<ver>_all.deb`.
     - DNF: GitHub Releases (same URL); asset name `aitasks-<ver>-1.noarch.rpm`.
     Plus the publishing workflow file path: `.github/workflows/release-packaging.yml` (and the maintainer-setup doc reference: `aidocs/homebrew_maintainer_setup.md` for brew, `aidocs/aur_maintainer_setup.md` for AUR).
   - **Limitation(s)** — bulleted, concrete (e.g. "Users must qualify with `beyondeye/aitasks/` tap prefix"; "`pacman -S aitasks` does NOT work"; "`.deb` declares `python3 (>= 3.9)`, blocking Ubuntu 20.04"; "no hosted apt/dnf repo"; "Rocky/Alma 9 need EPEL for `fzf`").
   - **Surfaced in (cross-ref)** — explicit list of user-facing files / sections where the limitation is mentioned: `README.md` Quick Install row, `website/content/docs/installation/_index.md`, the per-platform page (`macos.md` / `arch-aur.md` / `debian-apt.md` / `fedora-dnf.md`), and `windows-wsl.md` for the deb section. Include the source-of-truth file too (`packaging/nfpm/nfpm.yaml:27` for the python3 dep).
   - **Roadmap** — numbered, concrete steps to remove the limitation. For each PM:
     - **Homebrew → homebrew-core:** confirm policy fit (open-source, stable releases), generate download analytics, run `brew audit --strict`, file PR to `homebrew-core`, keep tap as fallback. Effort: low-to-medium.
     - **AUR → official Arch `extra`:** demonstrate sustained AUR usage (vote count, comments), identify a Trusted User sponsor (via `aur-general` ML), polish PKGBUILD for `namcap` + signed sources, sponsor adopts and uploads. Effort: medium-to-high (TU availability).
     - **APT/.deb → hosted `apt.aitasks.io`:** provision static-file host (GitHub Pages viable), generate GPG signing key, run `reprepro` or `aptly` in `release-packaging.yml`, distribute keyring via website + `aitasks-archive-keyring.deb`. Effort: medium.
     - **APT/.deb → official Debian (and Ubuntu downstream):** find a Debian Developer sponsor, file an ITP bug on `wnpp`, iterate source package to Debian Policy (lintian-clean, copyright, watch file), sponsor uploads to `sid`, migrates to `testing`. Effort: high.
     - **DNF/.rpm → COPR (`beyondeye/aitasks`):** register Fedora COPR account, create project, configure builds for Fedora 40+/Rocky 9/RHEL 9, document `dnf copr enable beyondeye/aitasks; dnf install aitasks`. Effort: low — easiest "more official" Fedora channel.
     - **DNF/.rpm → official Fedora repos:** polish .spec for Packaging Guidelines (`fedora-review` clean), file Package Review Bug, find sponsor, request `dist-git` access. Effort: high.
     - **DNF/.rpm → EPEL (after Fedora):** request EPEL branch via Fedora releng. Effort: low after Fedora inclusion.

3. **Cross-channel concerns** — sections for:
   - **Python 3.9+ requirement** — package-layer constraint, not runtime (since `ait setup` provisions Python via `uv`); refs `packaging/nfpm/nfpm.yaml:27` as source of truth; notes Python 3.9 EOL October 2025 makes loosening unlikely.
   - **Asset signing** — currently no GPG signing; outlines the keypair / GitHub-secret / `release-packaging.yml` integration needed for hosted-repo paths.

4. **Updating user-facing docs when status changes** — explicit table mapping each cross-channel doc surface to the section to edit:
   | User-facing file | Section to update |
   | `README.md` | Quick Install table |
   | `website/content/docs/installation/_index.md` | Quick Install table |
   | `website/content/docs/installation/macos.md` | Install / Prerequisites |
   | `website/content/docs/installation/arch-aur.md` | Install + "pacman does NOT work" callout |
   | `website/content/docs/installation/debian-apt.md` | Supported versions + Install |
   | `website/content/docs/installation/fedora-dnf.md` | Supported distros + EPEL callout + Install |
   | `website/content/docs/installation/windows-wsl.md` | Recommended `.deb` section |

5. **Related docs** — links to `packaging_strategy.md`, `homebrew_maintainer_setup.md`, `aur_maintainer_setup.md`.

**Why a separate file (vs. extending `packaging_strategy.md`):** `packaging_strategy.md` is the architectural-rationale doc (why shim-only, dependency mapping). The new file is operational/maintenance-shaped: status snapshot + cross-ref index + roadmap. Keeping them separate lets each evolve independently and prevents the strategy doc from accumulating churn every time a channel status changes.

Each per-platform sub-page (created in Step 3 below) gets a **"See also"** footer linking back to this doc. README's Quick Install paragraph also references it briefly so contributors discover it.

### 1. README.md — rewrite the "Quick Install" section (lines 57–93)

Replace the entire current block (from `## ⚡ Quick Install` through the "**Windows/WSL users:**" line at 93) with:

```markdown
## ⚡ Quick Install

Pick your platform:

| Platform | Install command |
|----------|-----------------|
| **macOS** | `brew install beyondeye/aitasks/aitasks` — see the [Homebrew guide](https://aitasks.io/docs/installation/macos/) |
| **Arch / Manjaro** (AUR) | `yay -S aitasks` or `paru -S aitasks` — see the [AUR guide](https://aitasks.io/docs/installation/arch-aur/) |
| **Debian / Ubuntu / WSL** | Download the latest `.deb` from [Releases](https://github.com/beyondeye/aitasks/releases/latest) and `sudo apt install ./aitasks_*.deb` — see the [Debian/Ubuntu guide](https://aitasks.io/docs/installation/debian-apt/) |
| **Fedora / RHEL / Rocky / Alma** | Download the latest `.rpm` from [Releases](https://github.com/beyondeye/aitasks/releases/latest) and `sudo dnf install ./aitasks-*.noarch.rpm` — see the [Fedora guide](https://aitasks.io/docs/installation/fedora-dnf/) |
| **Other (any POSIX)** | `curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh \| bash` |

All install methods drop a single `ait` command on your `$PATH` — the **global shim** (~3 KB). The shim downloads the framework on demand when you run `ait setup` in your project, so the package itself stays tiny and you do not need to re-install it to get framework updates. See the [installation guide](https://aitasks.io/docs/installation/) for the full picture.

After installing, `cd` into your project (the git repository root) and run `ait setup` to bootstrap the framework.

> **Windows users:** Run from a WSL shell, not PowerShell. See the [Windows/WSL guide](https://aitasks.io/docs/installation/windows-wsl/).
```

Keep the existing "Upgrade an existing installation" / "Already have the global ait shim?" paragraphs **immediately after** this block — they remain accurate (covering `ait upgrade latest` and the auto-bootstrap flow once the shim is on PATH). Do NOT delete those.

### 2. `website/content/docs/installation/_index.md` — rewrite Quick Install only

Replace the existing "## Quick Install" section (lines 8–49 in the current file, ending just before "## Cloning a Repo That Already Uses aitasks") with the same per-platform table from Step 1, adapted to Hugo Docsy relrefs.

**Preserve verbatim** (do not touch):

- The existing frontmatter (title/linkTitle/weight/description) at lines 1–6.
- The existing **Cloning a Repo That Already Uses aitasks** section.
- The existing **Platform Support** section.
- The existing **What Gets Installed** section.
- The existing **Next** link at the bottom.

The `_index.md` rewrite of Quick Install:

```markdown
## Quick Install

> **Run from the project root.** aitasks expects to be invoked from the directory containing `.git/` — the root of your project's git repository. All install methods below assume you `cd` into that directory first.

Pick your platform:

| Platform | Install command |
|----------|-----------------|
| **macOS** | `brew install beyondeye/aitasks/aitasks` — see the [Homebrew guide](macos/) |
| **Arch / Manjaro** (AUR) | `yay -S aitasks` or `paru -S aitasks` — see the [AUR guide](arch-aur/) |
| **Debian / Ubuntu / WSL** | Download the latest `.deb` from [Releases](https://github.com/beyondeye/aitasks/releases/latest) and `sudo apt install ./aitasks_*.deb` — see the [Debian/Ubuntu guide](debian-apt/) |
| **Fedora / RHEL / Rocky / Alma** | Download the latest `.rpm` from [Releases](https://github.com/beyondeye/aitasks/releases/latest) and `sudo dnf install ./aitasks-*.noarch.rpm` — see the [Fedora guide](fedora-dnf/) |
| **Other (any POSIX)** | `curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh \| bash` |

All install methods drop a single `ait` command on your `$PATH` — the **global shim** (~3 KB). The shim downloads the framework on demand when you run `ait setup` in your project, so the installed package stays tiny and you do not need to re-install it to get framework updates. For the full rationale, see the [packaging strategy reference](https://github.com/beyondeye/aitasks/blob/main/aidocs/packaging_strategy.md).

After installing, `cd` into your project root (where `.git/` lives) and run `ait setup` to install dependencies and configure agent integrations. See [`ait setup`](../commands/setup-install/) for details.

> **Windows users:** Run from a WSL shell, not PowerShell. See the [Windows/WSL guide](windows-wsl/).

> **Already have the global `ait` shim?** Once any install method has placed `ait` on your PATH, you can bootstrap aitasks in any new project directory by running `ait setup` there — the shim auto-downloads the framework on first run.
```

### 3. Create per-platform sub-pages

All four pages share the same skeleton:

```markdown
---
title: "<Platform> Installation"
linkTitle: "<Platform>"
weight: <N>
description: "Install aitasks on <platform> via <PM>"
---

## What you get

`<pm> install` places the **aitasks global shim** (a single ~3 KB shell script) at `<path>`. The shim is *not* the framework itself — when you run `ait setup` in a project, the shim downloads the appropriate framework version into that project. This means:

- The installed package stays tiny (~3 KB).
- Framework updates do NOT require re-installing the package; `ait upgrade latest` (or just `ait setup` in a fresh project) fetches the newest framework on demand.
- `ait --version` *outside* a project shows the shim version; *inside* a project it shows the framework version installed in that project. They are independent.

For the full design rationale, see [`aidocs/packaging_strategy.md`](https://github.com/beyondeye/aitasks/blob/main/aidocs/packaging_strategy.md).

## Install

```bash
<install command>
```

## First project

```bash
cd /path/to/your-project    # the git repository root
ait setup
```

`ait setup` installs framework dependencies (Python venv, CLI tools, agent integrations) and downloads the framework files into your project.

## Upgrade

```bash
<upgrade command>
```

## Uninstall

```bash
<uninstall command>
```

> **Note:** Uninstalling the package removes the `ait` shim only. Per-project files in `aitasks/` and `aiplans/` remain in your repo (committed to git as normal).
```

#### 3a. `macos.md` — REWRITE in place (URL stable)

Use the skeleton above with:

- **frontmatter** — preserve existing `weight: 25` and `linkTitle: "macOS"`. Update `description: "Install aitasks on macOS via Homebrew, with notes on terminal-emulator choice"`.
- **Install:** `brew install beyondeye/aitasks/aitasks`
- **Upgrade:** `brew update && brew upgrade aitasks`
- **Uninstall:** `brew uninstall aitasks`
- **Path:** `$(brew --prefix)/bin/ait`
- **Prerequisites note (above "What you get"):** macOS 12 (Monterey) or newer; [Homebrew](https://brew.sh) (the `brew install` command requires it).
- **Append the existing "Terminal emulator choice" section verbatim** (lines 30–78 of current `macos.md`) — Apple Terminal limitations, recommended `brew install --cask ghostty/iterm2/...`, fallback config, truecolor verify snippet. Add it as a top-level `## Terminal emulator choice (important)` section after the Uninstall section but before the Next-steps.
- Keep the existing **Next steps** / **Next** trailing block.

#### 3b. `arch-aur.md` — NEW (`weight: 30`)

Skeleton with:

- **Install:** `yay -S aitasks` (recommended) or `paru -S aitasks`. Both AUR helpers work identically.
- **Without an AUR helper (manual):**
  ```bash
  git clone https://aur.archlinux.org/aitasks.git
  cd aitasks
  makepkg -si
  ```
- **Explicit warning callout (above "What you get"):**
  > **`pacman -S aitasks` does NOT work.** aitasks lives in the [AUR](https://aur.archlinux.org/), not the official Arch repositories. You need an AUR helper (`yay`, `paru`) — or `git clone` + `makepkg -si` — to install it.
- **Upgrade:** `yay -Syu aitasks` (or `paru -Syu aitasks`).
- **Uninstall:** `sudo pacman -R aitasks`.
- **Path:** `/usr/bin/ait`.

#### 3c. `debian-apt.md` — NEW (`weight: 40`)

Skeleton with:

- **Supported versions section** (above "What you get"):
  - **Works directly:** Ubuntu 22.04+, Debian 11+ (Debian 11 ships Python 3.9, which satisfies the `.deb`'s `python3 >= 3.9` dependency).
  - **Ubuntu 20.04 (Focal):** the `.deb` install is blocked by apt's dependency solver because Ubuntu 20.04 ships `python3 3.8`. Two paths:
    1. Install a newer Python from the [deadsnakes PPA](https://launchpad.net/~deadsnakes/+archive/ubuntu/ppa) first, then proceed with the `.deb` install.
    2. **Skip the `.deb` and use the curl install path** — `ait setup` will install a modern Python (3.11) user-scoped via [uv](https://github.com/astral-sh/uv) into `~/.aitask/python/`, independent of the system Python. No sudo needed beyond `apt install` of base packages. This is the recommended path for Ubuntu 20.04 users:
       ```bash
       cd /path/to/your-project
       curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh | bash
       ait setup
       ```
- **Install** (two paths — pick one):

  **With `gh` (GitHub CLI), simplest:**
  ```bash
  gh release download --repo beyondeye/aitasks --pattern '*.deb'
  sudo apt install ./aitasks_*.deb
  ```

  **Without `gh`, curl one-liner:**
  ```bash
  DEB_URL=$(curl -s https://api.github.com/repos/beyondeye/aitasks/releases/latest \
    | grep -o 'https://[^"]*aitasks_[^"]*_all\.deb' | head -1)
  curl -fsSL "$DEB_URL" -o /tmp/aitasks.deb
  sudo apt install /tmp/aitasks.deb
  ```

  **Manual path** (browse [Releases](https://github.com/beyondeye/aitasks/releases/latest), download the `.deb`, then `sudo apt install ./aitasks_*.deb`).
- **WSL note** (subsection): WSL2 Ubuntu uses the same install path as native Ubuntu — no extra steps.
- **Upgrade:** Same flow as install — download the new `.deb` and `sudo apt install ./aitasks_*.deb`.
- **Uninstall:** `sudo apt remove aitasks`.
- **Path:** `/usr/bin/ait`.

#### 3d. `fedora-dnf.md` — NEW (`weight: 50`)

Skeleton with:

- **Supported distros section** (above "What you get"): Fedora 40+, Rocky Linux 9, AlmaLinux 9, RHEL 9.
- **EPEL prerequisite for Rocky/Alma/RHEL 9** (callout in Supported distros section):
  > **Rocky / Alma / RHEL 9 users:** Enable [EPEL](https://docs.fedoraproject.org/en-US/epel/) before installing aitasks — `fzf` (a runtime dependency) is in EPEL on these distros:
  > ```bash
  > sudo dnf install epel-release
  > ```
  > Fedora ships `fzf` in its main repos; no EPEL needed.
- **Install** (two paths):

  **With `gh`:**
  ```bash
  gh release download --repo beyondeye/aitasks --pattern '*.rpm'
  sudo dnf install ./aitasks-*.noarch.rpm
  ```

  **Without `gh`, curl:**
  ```bash
  RPM_URL=$(curl -s https://api.github.com/repos/beyondeye/aitasks/releases/latest \
    | grep -o 'https://[^"]*aitasks-[^"]*\.noarch\.rpm' | head -1)
  curl -fsSL "$RPM_URL" -o /tmp/aitasks.rpm
  sudo dnf install /tmp/aitasks.rpm
  ```

  **Manual path** (browse Releases, download the `.rpm`, then `sudo dnf install ./aitasks-*.noarch.rpm`).
- **Upgrade:** `sudo dnf upgrade ./new-aitasks-*.noarch.rpm` after downloading.
- **Uninstall:** `sudo dnf remove aitasks`.
- **Path:** `/usr/bin/ait`.

### 4. `windows-wsl.md` — prepend a `.deb`-recommended section

Insert immediately after the existing "Install WSL" section (i.e., before the current "## Install aitasks" heading at line 38) a new section:

```markdown
## Install aitasks (recommended: `.deb` package)

Once your WSL Ubuntu/Debian shell is up, the cleanest install is the `.deb` package — same as native Ubuntu. See the [Debian/Ubuntu guide](../debian-apt/) for the full walkthrough; the short version:

```bash
gh release download --repo beyondeye/aitasks --pattern '*.deb'
sudo apt install ./aitasks_*.deb
ait setup
```

If you do not have `gh` installed, use the curl one-liner from the [Debian/Ubuntu guide](../debian-apt/).

---
```

Then **rename the existing "Install aitasks" section** (lines 38–55 in current file) to **`## Fallback: install via curl`** — keep its body verbatim (the curl pipe + `ait setup` flow). This way the curl path remains documented for users without a working `apt` (rare in WSL but possible in custom WSL distros).

### 5. Cross-references and stylistic checks

- Each per-platform page links to `aidocs/packaging_strategy.md` (architectural rationale) from the "What you get" section.
- Each per-platform page also has a **"See also"** footer linking to `aidocs/packaging_distribution_status.md` (current limitations + roadmap, created in Step 0). Phrasing: "*See [Packaging Distribution Status & Roadmap](https://github.com/beyondeye/aitasks/blob/main/aidocs/packaging_distribution_status.md) for the current state of this channel and steps toward more official distribution.*"
- Each per-platform page links to `ait setup` docs at `../commands/setup-install/`.
- README quick-install table cell links use **absolute** URLs (`https://aitasks.io/...`) — README is rendered by GitHub, not Hugo.
- `_index.md` table cell links use **Hugo relative** paths (`macos/`, `arch-aur/`, etc.) — they live inside the Docsy site.
- Verify no `curl -fsSL .../install.sh | bash` survives as the *primary* recommendation on macOS / Arch / Debian / Fedora pages — only on `_index.md`/`README.md` "Other POSIX" rows and `windows-wsl.md` Fallback section.

## Verification Checklist

- [ ] `aidocs/packaging_distribution_status.md` exists. Has the snapshot table, per-channel limitations + cross-refs + roadmap (Homebrew, AUR, APT, DNF), cross-channel concerns (Python, signing), and the "Updating user-facing docs when status changes" cross-ref index.
- [ ] The snapshot table and each per-channel subsection of `packaging_distribution_status.md` include **clickable links to the live package locations**: Homebrew tap repo (`https://github.com/beyondeye/homebrew-aitasks`), AUR package page (`https://aur.archlinux.org/packages/aitasks`), and GitHub Releases (`https://github.com/beyondeye/aitasks/releases/latest`) for the .deb / .rpm assets. Verify the AUR page URL resolves (the package was created in t623_3); if it 404s, note that as a deferred follow-up rather than landing a broken link.
- [ ] Every per-platform page has a "See also" footer linking to `aidocs/packaging_distribution_status.md`.
- [ ] `cd website && npm install && ./serve.sh` — every new page renders; Docsy sidebar shows `macos`, `arch-aur`, `debian-apt`, `fedora-dnf`, `windows-wsl` under Installation; weights produce correct ordering (`macos`=25, `arch-aur`=30, `debian-apt`=40, `fedora-dnf`=50).
- [ ] No broken internal links: spot-check each per-platform page's "What you get" link to `aidocs/packaging_strategy.md`, and each page's `../commands/setup-install/` reference.
- [ ] `grep -rn "curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh" README.md website/` — only appears in: (a) README "Other (any POSIX)" row, (b) `_index.md` "Other (any POSIX)" row, (c) `windows-wsl.md` "Fallback: install via curl" section. Nowhere else.
- [ ] `arch-aur.md` includes the explicit "`pacman -S aitasks` does NOT work" callout.
- [ ] `fedora-dnf.md` includes the EPEL prerequisite callout for Rocky/Alma/RHEL 9.
- [ ] Each per-platform page has all six required sections: Prerequisites/Supported (where applicable), What you get, Install, First project, Upgrade, Uninstall.
- [ ] Each per-platform page has the shim-only paragraph in "What you get".
- [ ] `macos.md` retains the Terminal emulator choice subsection (Apple Terminal limitations + recommended Ghostty/iTerm2 etc.) — content unchanged from current.
- [ ] `_index.md` retains its **Cloning a Repo / Platform Support / What Gets Installed** sections unchanged.
- [ ] `README.md` — render via `gh api markdown --field text="$(cat README.md)"` (or PR preview) — install table renders correctly on GitHub; no version-history prose; "Upgrade an existing installation" / "Already have the global ait shim?" paragraphs preserved below the new table.
- [ ] No "previously…" / "earlier we…" / "this used to be" prose anywhere — current state only (CLAUDE.md doc convention).
- [ ] **t623_7 manual-verification sibling** still has actionable items — it covers human-eyes verification of the rendered docs (sidebar order, link clicks, etc.). No changes to that task; this child just produces the artefacts t623_7 inspects.

## Step 9 (Post-Implementation)

After review and approval in Step 8, follow the standard task-workflow Step 9: archive `t623_6` via `aitask_archive.sh 623_6`. Since `t623_7` (manual_verification sibling) remains pending, the parent `t623` will NOT auto-archive — that happens after t623_7 completes.

## Final Implementation Notes (to be filled in post-implementation)

- **Actual work done:**
- **Deviations from plan:**
- **Issues encountered:**
- **Key decisions:**
- **Upstream defects identified:**
- **Notes for sibling tasks:**
