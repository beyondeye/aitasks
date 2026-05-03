---
priority: medium
effort: medium
depends: [t623_2]
issue_type: feature
status: Ready
labels: [install_scripts, installation, packaging, aur, arch, ci]
created_at: 2026-04-22 18:57
updated_at: 2026-05-03 18:56
---

## Context

Third child of t623. Depends on t623_1 (shim extraction) and t623_2 (which introduces `release-packaging.yml`).

**Why.** Arch Linux (+ Manjaro, EndeavourOS, etc.) users install third-party tools almost exclusively via the AUR using helpers like `yay` or `paru`. This child publishes `aitasks` to the AUR and automates re-publishing on every release.

**Note on `pacman`.** Plain `pacman -S aitasks` will NOT work — AUR packages are not in official repos. Users install via `yay -S aitasks`, `paru -S aitasks`, or manually via `git clone https://aur.archlinux.org/aitasks.git && makepkg -si`. Getting into official Arch repos (so plain pacman works) is a separate community-driven process, out of scope. Hosting our own unofficial pacman repo is a deferred follow-up (parallel to APT/DNF repo hosting).

## Key Files to Modify

- `aidocs/aur_maintainer_setup.md` (new) — comprehensive first-time-setup walkthrough mirroring `aidocs/homebrew_maintainer_setup.md` (shipped in t623_2). Covers: AUR account creation, ed25519 SSH key generation + AUR registration, first-time package-page bootstrap (clone `ssh://aur@aur.archlinux.org/aitasks.git`, push stub PKGBUILD), GitHub secrets provisioning, end-to-end local test on Arch / archlinux container, first-real-release walkthrough, troubleshooting.
- `packaging/aur/PKGBUILD.template` (new) — Arch PKGBUILD with `VERSION_PLACEHOLDER` and `SHA256_PLACEHOLDER`.
- `packaging/aur/README.md` (new) — slim directory-level reference (what's here, pointer to `aidocs/aur_maintainer_setup.md`, local-test snippet). NOT the comprehensive walkthrough.
- `.github/workflows/release-packaging.yml` (modified) — add `publish-aur` job, including the soft-skip guard pattern from t623_2's `publish-homebrew` (gate on `AUR_SSH_PRIVATE_KEY` presence so missing-secret tags warn-and-skip rather than fail).

## Reference Files for Patterns

- `aiplans/archived/p623/p623_1_*.md` and `p623_2_*.md` — primary references for shim path, release-asset URL, and the existing `release-packaging.yml` scaffolding.
- `aidocs/packaging_strategy.md` — AUR secret provisioning runbook.
- **External:** `sinelaw/fresh/.github/workflows/aur-publish.yml` — exact template we adapt. In particular the `KSXGitHub/github-actions-deploy-aur@v4.1.2` action and the PKGBUILD template substitution pattern.

## Implementation Plan

0. Author `aidocs/aur_maintainer_setup.md` — comprehensive first-time-setup walkthrough mirroring `aidocs/homebrew_maintainer_setup.md`. The structure should match (sections: what AUR is, create the AUR account + SSH key, register the package page, provision GitHub secrets, end-to-end local test on Arch / archlinux container, cut the first real release, troubleshooting). The `packaging/aur/README.md` (Step 2 below) becomes a slim pointer to this walkthrough plus the local-test snippet, NOT a comprehensive how-to.

1. Create `packaging/aur/PKGBUILD.template`:
   ```
   # Maintainer: aitasks maintainers <noreply@aitasks.io>
   pkgname=aitasks
   pkgver=VERSION_PLACEHOLDER
   pkgrel=1
   pkgdesc="File-based task management framework for AI coding agents"
   arch=('any')
   url="https://aitasks.io/"
   license=('Apache')
   depends=('bash>=4' 'python>=3.9' 'fzf' 'jq' 'git' 'zstd' 'tar' 'curl')
   optdepends=('github-cli: GitHub integration'
               'glab: GitLab integration')
   source=("ait::https://github.com/beyondeye/aitasks/releases/download/v$pkgver/ait")
   sha256sums=('SHA256_PLACEHOLDER')

   package() {
       install -Dm755 "$srcdir/ait" "$pkgdir/usr/bin/ait"
   }
   ```
2. Create `packaging/aur/README.md`:
   - One-time AUR account + SSH key setup (generate ed25519 key, add to AUR account settings).
   - `gh secret set AUR_USERNAME`, `AUR_EMAIL`, `AUR_SSH_PRIVATE_KEY` commands (the SSH key is the **private** key, whitespace-preserved).
   - First-time: clone `ssh://aur@aur.archlinux.org/aitasks.git`, push a stub PKGBUILD so the package page exists, THEN enable the CI job. Otherwise the action fails trying to push to a non-existent repo.
3. Add `publish-aur` job to `.github/workflows/release-packaging.yml`:
   ```yaml
   publish-aur:
     runs-on: ubuntu-latest
     env:
       VERSION: ${{ inputs.version }}
     steps:
       - uses: actions/checkout@v4
       - name: Download shim from release
         id: checksum
         run: |
           curl -fsSL "https://github.com/beyondeye/aitasks/releases/download/v${VERSION}/ait" -o ait
           SHA256=$(sha256sum ait | cut -d' ' -f1)
           echo "sha256=$SHA256" >> "$GITHUB_OUTPUT"
       - name: Render PKGBUILD
         run: |
           mkdir -p aur-out
           sed -e "s/VERSION_PLACEHOLDER/${VERSION}/g" \
               -e "s/SHA256_PLACEHOLDER/${{ steps.checksum.outputs.sha256 }}/g" \
               packaging/aur/PKGBUILD.template > aur-out/PKGBUILD
       - name: Publish AUR
         uses: KSXGitHub/github-actions-deploy-aur@v4.1.2
         with:
           pkgname: aitasks
           pkgbuild: ./aur-out/PKGBUILD
           commit_username: ${{ secrets.AUR_USERNAME }}
           commit_email: ${{ secrets.AUR_EMAIL }}
           ssh_private_key: ${{ secrets.AUR_SSH_PRIVATE_KEY }}
           commit_message: "Update to ${{ inputs.version }}"
           ssh_keyscan_types: ed25519
   ```

## Verification Steps

1. **Local PKGBUILD test (on Arch or in an `archlinux:base-devel` container):**
   - Render PKGBUILD from template with a known version/SHA256.
   - `namcap PKGBUILD` — no errors; warnings reviewed and documented.
   - `makepkg -si` succeeds; `which ait` resolves to `/usr/bin/ait`.
   - `ait setup` in a fresh empty git repo works.
2. **CI dry-run:** Tag a prerelease, verify `publish-aur` job pushes to AUR successfully.
3. **End-to-end:** After a real tag, verify:
   - AUR page at https://aur.archlinux.org/packages/aitasks shows the new `pkgver` within 2 min.
   - `yay -S aitasks` on a clean Manjaro VM installs cleanly.
   - `ait setup` works.
4. **Documentation accuracy check:** the AUR package description matches the pkgdesc field in PKGBUILD.template.
