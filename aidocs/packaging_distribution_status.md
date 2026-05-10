# Packaging Distribution Status & Roadmap

Maintainer-facing reference for the **current state** of every channel through which `aitasks` is distributed via package managers (PMs), the limitations users hit on each channel, where each limitation is mentioned in user-facing docs (so updates are mechanical when status changes), and concrete roadmap steps for moving each channel toward more "official" / first-party distribution.

For the *architectural* rationale behind the shim-only packaging model (why every PM ships only the `ait` global shim, not the framework itself), see [`packaging_strategy.md`](./packaging_strategy.md). This doc is operational/maintenance-shaped — it complements but does not duplicate the strategy doc.

## Snapshot

| PM | Where it lives (live link) | Channel type | Cross-distro reach |
|----|----------------------------|--------------|--------------------|
| Homebrew | <https://github.com/beyondeye/homebrew-aitasks> | Custom tap (NOT in `homebrew-core`) | macOS (any version brew supports) |
| AUR | <https://aur.archlinux.org/packages/aitasks> | Community-curated (NOT in official Arch `extra`/`core`) | Arch + Manjaro (any AUR-helper user) |
| APT (.deb) | <https://github.com/beyondeye/aitasks/releases/latest> (asset `aitasks_<ver>_all.deb`) | GitHub Releases asset (NOT a hosted apt repo, NOT in official Debian/Ubuntu archives) | Debian 11+, Ubuntu 22.04+ (Ubuntu 20.04 has caveats — see below) |
| DNF (.rpm) | <https://github.com/beyondeye/aitasks/releases/latest> (asset `aitasks-<ver>-1.noarch.rpm`) | GitHub Releases asset (NOT in COPR, NOT in official Fedora/EPEL/RHEL repos) | Fedora 40+, Rocky/Alma 9 (with EPEL), RHEL 9 (with EPEL) |

Every channel is auto-published on each release tag by [`.github/workflows/release-packaging.yml`](../.github/workflows/release-packaging.yml). Maintainer first-time setup is in [`homebrew_maintainer_setup.md`](./homebrew_maintainer_setup.md) and [`aur_maintainer_setup.md`](./aur_maintainer_setup.md).

---

## Per-channel limitations and roadmap

### Homebrew (macOS) — custom tap

**Where it lives:** <https://github.com/beyondeye/homebrew-aitasks>
**Install command:** `brew install beyondeye/aitasks/aitasks`
**Publish workflow:** [`.github/workflows/release-packaging.yml`](../.github/workflows/release-packaging.yml) → `publish-homebrew` job
**First-time setup:** [`homebrew_maintainer_setup.md`](./homebrew_maintainer_setup.md)

**Limitations:**

- Users must qualify the formula with the tap prefix (`beyondeye/aitasks/aitasks`). Cannot run plain `brew install aitasks`.
- Tap discoverability is lower than `homebrew-core` (no presence in `brew search` global index unless the user has tapped first).

**Surfaced in:**

- `README.md` — Quick Install table (macOS row)
- `website/content/docs/installation/_index.md` — Quick Install table (macOS row)
- `website/content/docs/installation/macos.md` — Install section

**Roadmap to `homebrew-core`:**

1. **Confirm policy fit.** Homebrew-core requires: open-source project, stable release URL, not a one-off, several prior releases, measurable user base. aitasks meets the open-source / stable-release / multi-release criteria; user-base demonstration is the gating factor.
2. **Generate analytics.** Track GitHub-release download counts for the `ait` shim asset (publicly visible via the GitHub API). Aim for sustained downloads (e.g., 50+/week) across at least 3 months as informal evidence.
3. **Audit the formula.** Run `brew audit --strict --new-formula` against a copy of `packaging/homebrew/aitasks.rb.template` (rendered with a real version) renamed `Formula/aitasks.rb` in a clone of `homebrew-core`. Fix any warnings.
4. **File a PR to `homebrew-core`.** Use the [Homebrew "submitting a new formula" guide](https://docs.brew.sh/Adding-Software-to-Homebrew). Expect review iteration; **keep the existing tap as upstream-of-record** during review (homebrew-core may decline; abandoning the tap mid-review would strand existing users).
5. **If accepted:** keep the tap as the fallback for prereleases / point-in-time pinning. Primary docs change to `brew install aitasks`. The tap remains useful for early-access channels.

**Effort:** Low-to-medium. Mostly waiting on review cycles.

---

### AUR (Arch / Manjaro) — community-curated, not official

**Where it lives:** <https://aur.archlinux.org/packages/aitasks>
**AUR clone URL:** `https://aur.archlinux.org/aitasks.git`
**Install commands:** `yay -S aitasks` or `paru -S aitasks` (or manual: `git clone https://aur.archlinux.org/aitasks.git && cd aitasks && makepkg -si`)
**Publish workflow:** [`.github/workflows/release-packaging.yml`](../.github/workflows/release-packaging.yml) → `publish-aur` job
**First-time setup:** [`aur_maintainer_setup.md`](./aur_maintainer_setup.md)

**Limitations:**

- `pacman -S aitasks` does NOT work — AUR is not in the official Arch repos (`core`/`extra`). Users must install an AUR helper (`yay`, `paru`) or use `makepkg -si` directly.
- AUR packages are unsigned by Arch maintainers. Users implicitly trust the AUR maintainer (the aitasks project) and the build runs on the user's machine.

**Surfaced in:**

- `README.md` — Quick Install table (Arch/Manjaro row)
- `website/content/docs/installation/_index.md` — Quick Install table (Arch/Manjaro row)
- `website/content/docs/installation/arch-aur.md` — explicit "**`pacman -S aitasks` does NOT work**" callout

**Roadmap to official Arch `extra` repo:**

1. **Demonstrate sustained AUR usage.** AUR vote count + comment volume on <https://aur.archlinux.org/packages/aitasks>. Trusted Users (TUs) look for stable, popular packages with active maintainers.
2. **Identify a Trusted User sponsor.** Find a TU willing to maintain the package in `extra`. The standard channels are the [`aur-general` mailing list](https://lists.archlinux.org/listinfo/aur-general) and the `arch-general` ML.
3. **Polish the PKGBUILD for upstream review.** Run `namcap` cleanly, ensure source artifacts are signed (becomes a hard requirement in `extra`), and keep the source URL on a maintenance-friendly path (release tarball, not a moving `master` branch).
4. **TU adopts and uploads to `extra`.** Done by the sponsor; aitasks maintainers respond to packaging review feedback.
5. **If accepted:** keep AUR as the bleeding-edge / latest-tag channel; primary docs change to `pacman -S aitasks`.

**Effort:** Medium-to-high. Sponsorship is the gating factor and depends on TU availability.

---

### APT (.deb) — Debian / Ubuntu / WSL — GitHub Releases asset

**Where it lives:** <https://github.com/beyondeye/aitasks/releases/latest>
**Asset name:** `aitasks_<VERSION>_all.deb` (architecture-independent; the shim is a shell script)
**Publish workflow:** [`.github/workflows/release-packaging.yml`](../.github/workflows/release-packaging.yml) → `build-deb` + `test-deb` jobs (uses `goreleaser/nfpm` Docker image)
**Source of truth (deps):** [`packaging/nfpm/nfpm.yaml`](../packaging/nfpm/nfpm.yaml) (`overrides.deb.depends` block, lines 24–33)

**Limitations:**

1. **No hosted apt repo.** Users download the `.deb` manually (or via `gh release download` / a curl one-liner). `apt update` does NOT see new releases automatically.
2. **Not in official Debian/Ubuntu archives.** Cannot `apt install aitasks` from default sources.
3. **Hard dep on `python3 (>= 3.9)`.** Ubuntu 20.04 (Focal) ships `python3 = 3.8`, so apt's dependency solver refuses the install on Focal. Workarounds: install a newer Python from the [deadsnakes PPA](https://launchpad.net/~deadsnakes/+archive/ubuntu/ppa) before the `.deb` install, OR use the curl install (which uses `ait setup`'s [uv](https://github.com/astral-sh/uv)-based Python provisioning and sidesteps the system-package solver entirely).

**Surfaced in:**

- `README.md` — Quick Install table (Debian/Ubuntu/WSL row)
- `website/content/docs/installation/_index.md` — Quick Install table
- `website/content/docs/installation/debian-apt.md` — Supported-versions section (Focal caveat) + Install instructions
- `website/content/docs/installation/windows-wsl.md` — recommended `.deb` section + curl fallback
- `packaging/nfpm/nfpm.yaml:27` — `python3 (>= 3.9)` hard-dep declaration (the *cause* of the Ubuntu 20.04 limitation)

**Roadmap to a hosted APT repo at `apt.aitasks.io`:**

1. **Provision a static-file host.** apt only needs `Release`, `Packages`, `Packages.gz`, and the actual `.deb` files at well-known paths under `dists/<suite>/main/binary-all/`. Lowest-effort backends: GitHub Pages, Cloudflare Pages, S3/R2.
2. **Generate a GPG signing key.** Create an `aitasks-archive` keypair for the apt repo. Distribute the public key via the website AND as a `aitasks-archive-keyring.deb` per Debian convention.
3. **Tooling.** Use `reprepro` or `aptly` to produce repo metadata. Run inside [`release-packaging.yml`](../.github/workflows/release-packaging.yml) after `build-deb`. The signing key lives as a GitHub Actions secret.
4. **Document the apt source line.** Users add `deb [signed-by=/usr/share/keyrings/aitasks-archive-keyring.gpg] https://apt.aitasks.io stable main` to `/etc/apt/sources.list.d/aitasks.list`. Then `apt update && apt install aitasks`.
5. **Update website docs.** Replace the manual-download flow on `debian-apt.md` with the apt-source-add flow once the repo is stable.

**Effort:** Medium. Mostly tooling + key management. No external sponsors required.

**Roadmap to official Debian (and Ubuntu downstream auto-sync):**

1. **Find a Debian Developer (DD) sponsor** (or apply to become a Maintainer/DD via the [New Maintainer process](https://www.debian.org/devel/join/newmaint)).
2. **File an Intent To Package (ITP) bug** against `wnpp` on Debian's BTS.
3. **Iterate the source package** to satisfy [Debian Policy](https://www.debian.org/doc/debian-policy/) (`lintian`-clean, `debian/copyright`, `debian/watch`, etc.). Some current packaging choices may need re-architecting for Debian's separation-of-concerns rules (e.g., bundled vendor scripts).
4. **Sponsor uploads to `unstable` (sid).** After sufficient time and no RC bugs, the package migrates to `testing` (and eventually `stable`).
5. **Ubuntu picks it up automatically** in the next cycle's auto-sync from Debian `unstable`.

**Effort:** High. Debian's review queues are slow; sponsorship is the gating factor; some packaging changes are non-trivial.

---

### DNF (.rpm) — Fedora / RHEL / Rocky / Alma — GitHub Releases asset

**Where it lives:** <https://github.com/beyondeye/aitasks/releases/latest>
**Asset name:** `aitasks-<VERSION>-1.noarch.rpm`
**Publish workflow:** [`.github/workflows/release-packaging.yml`](../.github/workflows/release-packaging.yml) → `build-rpm` + `test-rpm` jobs
**Source of truth (deps):** [`packaging/nfpm/nfpm.yaml`](../packaging/nfpm/nfpm.yaml) (`overrides.rpm.depends` block, lines 37–46)

**Limitations:**

1. **No COPR or hosted DNF repo.** Users download manually; no `dnf upgrade aitasks` against a repo.
2. **Not in official Fedora / EPEL / RHEL repos.** Cannot `dnf install aitasks` from default sources.
3. **EPEL prerequisite on Rocky / Alma / RHEL 9.** `fzf` (a hard runtime dep of the rpm) is in EPEL on those distros, not their base repos. Users must `sudo dnf install epel-release` before the aitasks rpm install. Fedora ships `fzf` in main repos; no EPEL needed there.

**Surfaced in:**

- `README.md` — Quick Install table (Fedora/RHEL/Rocky/Alma row)
- `website/content/docs/installation/_index.md` — Quick Install table
- `website/content/docs/installation/fedora-dnf.md` — Supported-distros section (EPEL callout) + Install instructions
- `packaging/nfpm/nfpm.yaml:37-46` — `overrides.rpm.depends` block (source of truth)
- `.github/workflows/release-packaging.yml` `test-rpm` job — has an `if: contains(matrix.distro, 'rocky') || ...` step that does `dnf install -y epel-release` to make CI tests pass on Rocky/Alma (mirrors what users have to do)

**Roadmap to COPR (`beyondeye/aitasks`):**

1. **Register a [Fedora COPR](https://copr.fedorainfracloud.org/) account** for the maintainer.
2. **Create the COPR project** `beyondeye/aitasks`. Configure source builds (point at GitHub Releases, or push spec files directly).
3. **Trigger initial builds** for Fedora 40, 41, 42; Rocky 9; RHEL 9 (epel-9 chroot).
4. **Update `fedora-dnf.md`** with the two-line install: `sudo dnf copr enable beyondeye/aitasks && sudo dnf install aitasks`.
5. **Maintain alongside Releases.** COPR can pull from a release webhook; keep GitHub Releases as the canonical artifact source.

**Effort:** Low. COPR is the easiest "more official" Fedora channel and the recommended next step.

**Roadmap to official Fedora repos:**

1. **Polish the .spec file** for [Fedora Packaging Guidelines](https://docs.fedoraproject.org/en-US/packaging-guidelines/) (`fedora-review`-clean).
2. **File a [Package Review Bug](https://bugzilla.redhat.com/enter_bug.cgi?product=Fedora&format=fedora-review)** on Red Hat Bugzilla.
3. **Find a sponsor** in the Fedora packaging community to perform the review.
4. **After approval, request `dist-git` access** for `aitasks`. Import the package into Fedora 41 / 42 / `rawhide` branches.
5. **Builds propagate** through `koji` to the standard Fedora repos.

**Effort:** High. Sponsor-gated. Fedora's review queue is faster than Debian's but still measured in weeks-to-months.

**Roadmap to EPEL (after Fedora inclusion lands):**

After official Fedora repo inclusion, request an EPEL branch via Fedora's `releng` workflow. Same source package, separate koji target. Effort: Low *after* Fedora inclusion.

---

## Cross-channel concerns

### Python 3.9+ requirement

Both `.deb` and `.rpm` declare `python3 >= 3.9` as a hard runtime dependency (`packaging/nfpm/nfpm.yaml:27` and `:39`). This is a **package-install-layer** limitation, not a framework runtime limitation:

- The framework runtime is fine on essentially any modern Linux. `ait setup` provisions a modern Python (3.11) user-scoped via [uv](https://github.com/astral-sh/uv) into `~/.aitask/python/` when the system Python is too old (see `.aitask-scripts/aitask_setup.sh`, `find_modern_python` / `_install_modern_python_linux`).
- The constraint is set by the packaging system (apt/dnf) refusing to install a package whose declared deps cannot be satisfied. Without the dep declaration, users on truly ancient systems would get a confusing `ait setup` failure instead of a clear apt error.

**Path to lower the floor:** Unlikely to be worth pursuing — Python 3.9 is end-of-life October 2025; future tightening is more likely than loosening. If we ever need to support a system stuck on Python 3.8, the recommendation is to use the curl install path, which sidesteps the package-system dep entirely.

### Asset signing

Currently `.deb` and `.rpm` artifacts are NOT signed by a project GPG key (only the GitHub Release tag itself is signed by the GitHub Actions runner key). Hosted-apt-repo, hosted-dnf-repo, and official-distro paths above ALL require GPG-signed packages.

**Path to signed artifacts:**

1. Generate an `aitasks-archive` GPG keypair (long-lived; rotation ≥ 4 years).
2. Store the private key as a GitHub Actions secret (`AITASKS_GPG_PRIVATE_KEY` + `AITASKS_GPG_PASSPHRASE`).
3. Sign packages in `release-packaging.yml` after `build-deb` / `build-rpm` — nfpm has built-in `--passphrase` + `--signing-key` flags.
4. Distribute the public key via the website (`https://aitasks.io/aitasks-archive-keyring.gpg`) and via a `aitasks-archive-keyring.deb` for apt users.

**Effort:** Low-to-medium. Mostly key management hygiene.

---

## Updating user-facing docs when status changes

When any limitation in this doc is removed (e.g., aitasks lands in `homebrew-core`, or a hosted apt repo goes live), update the corresponding sections in:

| User-facing file | Section to edit |
|------------------|-----------------|
| `README.md` | Quick Install table — update the platform's row |
| `website/content/docs/installation/_index.md` | Quick Install table — update the platform's row |
| `website/content/docs/installation/macos.md` | Install / Prerequisites |
| `website/content/docs/installation/arch-aur.md` | Install + "`pacman -S aitasks` does NOT work" callout (remove if it lands in `extra`) |
| `website/content/docs/installation/debian-apt.md` | Supported versions + Install (replace manual-download with apt-source-add when hosted repo lands; drop Focal caveat if Python policy changes) |
| `website/content/docs/installation/fedora-dnf.md` | Supported distros + EPEL callout (drop EPEL note if it lands in EPEL itself) + Install |
| `website/content/docs/installation/windows-wsl.md` | Recommended `.deb` section |

Then update this doc's **Snapshot** table and the relevant per-channel section (move limitations to a "Resolved on YYYY-MM-DD" subsection rather than deleting outright — useful for archeology).

---

## Related docs

- [`packaging_strategy.md`](./packaging_strategy.md) — design rationale for the shim-only model; dependency mapping; required GitHub Actions secrets; deferred follow-ups.
- [`homebrew_maintainer_setup.md`](./homebrew_maintainer_setup.md) — first-time setup of the Homebrew tap (PAT provisioning, local test, troubleshooting).
- [`aur_maintainer_setup.md`](./aur_maintainer_setup.md) — first-time setup of the AUR package (SSH key generation, AUR account, GitHub secrets, troubleshooting).
