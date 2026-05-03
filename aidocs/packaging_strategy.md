# Packaging Strategy

This is the single source of truth for all aitasks package-manager (PM)
distribution decisions: Homebrew (macOS / Linux), AUR (Arch Linux),
APT-style `.deb` (Debian / Ubuntu), and DNF-style `.rpm` (Fedora / RHEL).

Every PM packaging child task (t623_2..t623_5) consumes the decisions made
here. Update this document **before** changing the corresponding manifests.

## Packaging model: shim-only

Every PM ships **only the global shim** — the standalone executable file at
`packaging/shim/ait` (87 lines of bash). PM packages do **not** bundle the
aitasks framework itself. When the user runs `ait setup` for the first time
in a project, the shim downloads the framework tarball into the project,
exactly as the existing `curl | bash` install path does today.

### Rationale: release-cycle decoupling

The shim's surface is tiny and changes rarely. The framework changes
constantly (new scripts, refactors, skill updates). Bundling the framework
into PM packages would mean:

- Every framework release forces a PM bump across four PMs (and waiting on
  each PM's review/build pipeline).
- Users on slow-moving distros (Debian stable, RHEL) would lag arbitrary
  amounts behind master.
- Per-distro patching diverges (every distro needs a patch for path
  conventions, dep names, etc.).

Shim-only inverts the trade-off: PMs ship a stable interface (the shim)
once per minor revision; the framework stays current via a single canonical
source (`github.com/beyondeye/aitasks/install.sh`). Each tag bumps every PM
in lockstep, but the tarball logic lives in one place.

### What each PM ships

A single executable file at `/usr/local/bin/ait` (Homebrew / Linux PMs) or
`/usr/bin/ait` (system path on Linux), with the four runtime dependencies
declared as `dependencies` and `gh`/`glab` as `recommended`.

### Per-PM manifest skeletons

#### Homebrew (`Formula/aitasks.rb`)

```ruby
class Aitasks < Formula
  desc "File-based task framework for AI coding agents"
  homepage "https://github.com/beyondeye/aitasks"
  url "https://github.com/beyondeye/aitasks/releases/download/vX.Y.Z/ait"
  sha256 "<sha256 of the shim>"
  version "X.Y.Z"

  depends_on "bash"
  depends_on "fzf"
  depends_on "jq"
  depends_on "git"
  depends_on "zstd"

  def install
    bin.install "ait"
  end

  test do
    system "#{bin}/ait", "--version"
  end
end
```

#### AUR (`PKGBUILD`)

```bash
pkgname=aitasks
pkgver=X.Y.Z
pkgrel=1
pkgdesc="File-based task framework for AI coding agents"
arch=('any')
url="https://github.com/beyondeye/aitasks"
license=('MIT')
depends=('bash>=4' 'python>=3.9' 'fzf' 'jq' 'git' 'zstd' 'tar' 'curl')
optdepends=('github-cli: GitHub integration (issues, PRs)'
            'glab: GitLab integration (issues, MRs)')
source=("ait::https://github.com/beyondeye/aitasks/releases/download/v$pkgver/ait")
sha256sums=('<sha256 of the shim>')
package() {
  install -Dm755 "$srcdir/ait" "$pkgdir/usr/bin/ait"
}
```

#### Debian / Ubuntu (`debian/control` excerpt)

```
Package: aitasks
Version: X.Y.Z
Architecture: all
Depends: bash (>= 4.0), python3 (>= 3.9), fzf, jq, git, zstd, tar, curl
Recommends: gh | glab
Description: File-based task framework for AI coding agents
 aitasks ships the global `ait` shim. On first run, `ait setup` downloads
 the framework tarball into the active project.
```

The `debian/install` file places `ait` at `/usr/bin/ait`.

#### Fedora / RHEL (`aitasks.spec` excerpt)

```spec
Name:    aitasks
Version: X.Y.Z
Release: 1%{?dist}
Summary: File-based task framework for AI coding agents
License: MIT
URL:     https://github.com/beyondeye/aitasks
Source0: https://github.com/beyondeye/aitasks/releases/download/v%{version}/ait
BuildArch: noarch

Requires: bash >= 4.0, python3 >= 3.9, fzf, jq, git, zstd, tar, curl
Recommends: (gh or glab)

%install
install -Dm755 %{SOURCE0} %{buildroot}/usr/bin/ait
```

## Dependency name mapping

| Dependency | Homebrew | Arch (AUR) | Debian/Ubuntu | Fedora/RHEL |
|------------|----------|------------|---------------|-------------|
| bash | `bash` | `bash>=4` | `bash (>= 4.0)` | `bash >= 4.0` |
| python (≥3.9) | `python@3.12` | `python>=3.9` | `python3 (>= 3.9)` | `python3 >= 3.9` |
| fzf | `fzf` | `fzf` | `fzf` | `fzf` |
| jq | `jq` | `jq` | `jq` | `jq` |
| git | `git` | `git` | `git` | `git` |
| zstd | `zstd` | `zstd` | `zstd` | `zstd` |
| tar | (built-in) | `tar` | `tar` | `tar` |
| curl | `curl` | `curl` | `curl` | `curl` |
| gh¹ | — | `github-cli` | `gh` | `gh` |
| glab¹ | — | `glab` | `glab` | `glab` |

¹ `gh` and `glab` are individually optional, but **at least one is strongly
recommended**: aitasks integrates with the user's git host for issue / PR
flows, and a fresh install with neither tool present degrades several
features (e.g., `aitask-contribute`, archival's auto-issue-update) to
manual-only. Choose by host: GitHub users → `gh`, GitLab users → `glab`;
users with both hosts may install both. Each PM declares them as
`recommended` (apt) / `Recommends` (dnf) / `optdepends` (AUR), never as
hard requirements.

Homebrew omits `gh` / `glab` from the formula because Homebrew has no
"recommends" tier — users on macOS install those tools separately (and
typically already have them via `brew install gh`).

## Required GitHub Actions secrets

Each PM auto-bump CI flow needs credentials to push to its publishing
target. Set these once in the `beyondeye/aitasks` repo:

```bash
gh secret set HOMEBREW_TAP_TOKEN --repo beyondeye/aitasks  # PAT with `repo` scope on beyondeye/homebrew-aitasks
gh secret set AUR_USERNAME       --repo beyondeye/aitasks  # AUR account username
gh secret set AUR_EMAIL          --repo beyondeye/aitasks  # AUR account email
gh secret set AUR_SSH_PRIVATE_KEY --repo beyondeye/aitasks # ed25519 private key registered on AUR account
```

### Generating the AUR SSH key

```bash
ssh-keygen -t ed25519 -f aur_key -C aur-deploy
# Add the .pub key under your account:
#   https://aur.archlinux.org/account/
# Then load the private key into the secret:
cat aur_key | gh secret set AUR_SSH_PRIVATE_KEY --repo beyondeye/aitasks
# Discard the local key files when done:
rm -f aur_key aur_key.pub
```

For `.deb` and `.rpm` (children t623_4 and t623_5), the publishing flow
during the initial implementation phase produces release-attached package
files (`ait_X.Y.Z_all.deb`, `aitasks-X.Y.Z-1.noarch.rpm`) — no extra
secrets are needed beyond the default `GITHUB_TOKEN`. Hosted-repo
publishing (`apt.aitasks.io`, `rpm.aitasks.io`) is a deferred follow-up.

## Release-cadence policy

**Every aitasks tag bumps every PM**, regardless of whether the shim
content changed. Reasoning:

- Visibility: the user-facing version on each PM stays in sync with the
  framework version, so installation instructions in the docs always work.
- Predictability: CI logic stays trivial — "on tag, regenerate every
  manifest, push" — without a hash-comparison gate.
- Cost: the shim rebuild is essentially free for each PM (a checksum
  recompute and a one-line manifest patch).

A future hash-based skip ("if `packaging/shim/ait` SHA-256 unchanged,
don't bump") is listed under deferred follow-ups. It would reduce noise
on releases that touch only the framework, not the shim — but at the cost
of complicating CI and producing version-skew between framework releases
and PM versions. We will revisit only if the noise is observed to bother
maintainers.

## Version vs. behavior note (for user docs)

> The PM version label identifies the **shim** release. The actual
> aitasks framework version installed in your project is whatever
> `ait setup` downloads from GitHub at bootstrap time — usually the
> latest tagged release. To pin a specific framework version, run
> `ait upgrade --version vX.Y.Z` from the project root.

This note appears verbatim in t623_6's user-facing docs page.

## Deferred follow-ups

| Item | Notes |
|------|-------|
| Official Arch repo submission | For plain `pacman -S aitasks` (no AUR helper). Requires Arch maintainer sponsorship — defer until the AUR package has stabilized. |
| Hosted APT repo at `apt.aitasks.io` | `deb https://apt.aitasks.io stable main` — requires server hosting + signing-key infra. |
| Hosted DNF/RPM repo at `rpm.aitasks.io` | Same shape as the APT repo, different metadata format. |
| Hosted pacman repo at `pacman.aitasks.io` | Mirror of the official repo for users who don't want AUR. |
| Nix flake | Ship a `flake.nix` at repo root; works for both NixOS and nix-on-Linux/macOS users. |
| Scoop (Windows) | JSON manifest for Scoop bucket; needs Windows-friendly shim variant first (out of scope of t623). |
| Chocolatey (Windows) | Similar — needs Windows shim. |
| Snap / Flatpak | Sandbox-aware variants; cross-cutting work, defer until non-sandbox PMs are stable. |
| Hash-based skip-if-unchanged | "Bump only when the shim hash changed." See release-cadence section. |

Each deferred item should land as its own future child task or standalone
task with a reference back to this document.
