---
Task: t623_3_arch_aur_package_with_ci_auto_bump.md
Parent Task: aitasks/t623_more_installation_methods.md
Sibling Tasks: aitasks/t623/t623_1_*.md, t623_2_*.md, t623_4_*.md, t623_5_*.md, t623_6_*.md
Archived Sibling Plans: aiplans/archived/p623/p623_1_*.md, p623_2_*.md (primary reference)
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Implementation Plan: t623_3 — Arch AUR package with CI auto-bump

## Prerequisites

1. t623_1 merged (provides `packaging/shim/ait`, release asset, strategy doc).
2. t623_2 merged (provides `.github/workflows/release-packaging.yml` scaffolding with a `publish-homebrew` job; this child adds a `publish-aur` job alongside).
3. Maintainer has created AUR account, generated ed25519 SSH key, registered the public key with AUR.
4. Maintainer has run `ssh aur@aur.archlinux.org` to accept the host key, then `git clone ssh://aur@aur.archlinux.org/aitasks.git`, pushed an initial stub PKGBUILD so the package page exists. This is required — the `KSXGitHub/github-actions-deploy-aur` action fails if the repo does not exist yet.
5. Secrets `AUR_USERNAME`, `AUR_EMAIL`, `AUR_SSH_PRIVATE_KEY` set on the GitHub repo.

## Steps

### 1. Create the PKGBUILD template

`packaging/aur/PKGBUILD.template`:

```bash
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

### 2. Create the maintainer runbook

`packaging/aur/README.md`:

- AUR account creation + ed25519 SSH key generation:
  ```bash
  ssh-keygen -t ed25519 -f aur_key -C aur-deploy
  cat aur_key.pub  # add this to https://aur.archlinux.org/account/
  ```
- First-time repo bootstrap (required before CI can push):
  ```bash
  ssh-keyscan -t ed25519 aur.archlinux.org >> ~/.ssh/known_hosts
  git clone ssh://aur@aur.archlinux.org/aitasks.git
  cd aitasks
  # Copy stub PKGBUILD + .SRCINFO
  git add PKGBUILD .SRCINFO
  git commit -m "Initial stub"
  git push
  ```
- GitHub Actions secrets:
  ```bash
  gh secret set AUR_USERNAME --repo beyondeye/aitasks
  gh secret set AUR_EMAIL --repo beyondeye/aitasks
  cat aur_key | gh secret set AUR_SSH_PRIVATE_KEY --repo beyondeye/aitasks
  ```
- Local test instructions:
  ```bash
  VERSION=0.17.0
  SHA=$(curl -fsSL https://.../v${VERSION}/ait | sha256sum | cut -d' ' -f1)
  sed -e "s/VERSION_PLACEHOLDER/${VERSION}/g" \
      -e "s/SHA256_PLACEHOLDER/${SHA}/g" \
      packaging/aur/PKGBUILD.template > /tmp/PKGBUILD
  cd /tmp && makepkg -si
  namcap /tmp/PKGBUILD
  ```

### 3. Add the `publish-aur` job to `release-packaging.yml`

Append to the `jobs:` section of `.github/workflows/release-packaging.yml` (added in t623_2):

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
          echo "--- Rendered PKGBUILD ---"
          cat aur-out/PKGBUILD

      - name: Publish to AUR
        uses: KSXGitHub/github-actions-deploy-aur@v4.1.2
        with:
          pkgname: aitasks
          pkgbuild: ./aur-out/PKGBUILD
          commit_username: ${{ secrets.AUR_USERNAME }}
          commit_email: ${{ secrets.AUR_EMAIL }}
          ssh_private_key: ${{ secrets.AUR_SSH_PRIVATE_KEY }}
          commit_message: "Update to v${{ inputs.version }}"
          ssh_keyscan_types: ed25519
```

Note: `KSXGitHub/github-actions-deploy-aur` auto-generates `.SRCINFO`, so we don't need to commit a template for it.

### 4. Validate

- `actionlint .github/workflows/release-packaging.yml` clean.
- On a local Arch container, render the PKGBUILD with a real version and verify `namcap PKGBUILD` has no errors.

## Verification Checklist

- [ ] `packaging/aur/PKGBUILD.template` exists.
- [ ] Local `makepkg -si` on Arch (or container) using rendered PKGBUILD succeeds; `which ait` resolves to `/usr/bin/ait`.
- [ ] `namcap PKGBUILD` errors zero.
- [ ] `actionlint .github/workflows/release-packaging.yml` clean.
- [ ] Prerelease tag → AUR page updates within 2 min; `yay -Ss aitasks` shows the new version.
- [ ] `yay -S aitasks` (or `paru -S aitasks`) on a fresh Manjaro VM installs cleanly; `ait setup` in a new project works.

## Final Implementation Notes (to be filled in post-implementation)

- **Actual work done:**
- **Deviations from plan:**
- **Issues encountered:**
- **Key decisions:**
- **Notes for sibling tasks:**
