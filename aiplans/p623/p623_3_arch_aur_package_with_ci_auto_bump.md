---
Task: t623_3_arch_aur_package_with_ci_auto_bump.md
Parent Task: aitasks/t623_more_installation_methods.md
Sibling Tasks: aitasks/t623/t623_1_*.md, t623_2_*.md, t623_4_*.md, t623_5_*.md, t623_6_*.md
Archived Sibling Plans: aiplans/archived/p623/p623_1_*.md, p623_2_*.md (primary reference)
Worktree: (none — working on current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-03 19:07
---

# Implementation Plan: t623_3 — Arch AUR package with CI auto-bump

## Prerequisites

1. t623_1 merged (provides `packaging/shim/ait`, release asset, strategy doc).
2. t623_2 merged (provides `.github/workflows/release-packaging.yml` scaffolding with a `publish-homebrew` job; this child adds a `publish-aur` job alongside).
3. Maintainer has created AUR account, generated ed25519 SSH key, registered the public key with AUR.
4. Maintainer has run `ssh aur@aur.archlinux.org` to accept the host key, then `git clone ssh://aur@aur.archlinux.org/aitasks.git`, pushed an initial stub PKGBUILD so the package page exists. This is required — the `KSXGitHub/github-actions-deploy-aur` action fails if the repo does not exist yet.
5. Secrets `AUR_USERNAME`, `AUR_EMAIL`, `AUR_SSH_PRIVATE_KEY` set on the GitHub repo.

## Steps

### 0. Author the maintainer first-time-setup walkthrough

`aidocs/aur_maintainer_setup.md` (new) — comprehensive walkthrough mirroring
`aidocs/homebrew_maintainer_setup.md` (shipped in t623_2). Required sections,
in order:

1. **What the AUR is.** Two-paragraph orientation: AUR (Arch User Repository)
   is a community-maintained collection of build scripts (PKGBUILDs);
   helpers like `yay` / `paru` automate the build+install. Plain
   `pacman -S aitasks` will NOT work — that's only for official Arch repos
   (separate, gated process). Cross-link <https://wiki.archlinux.org/title/Arch_User_Repository>.

2. **Create an AUR account.** Visit <https://aur.archlinux.org/register>;
   pick a username (will appear as `Maintainer:` field on the package
   page); confirm email.

3. **Generate ed25519 SSH key for the bot:**
   ```bash
   ssh-keygen -t ed25519 -f aur_key -C aur-deploy
   cat aur_key.pub  # paste into AUR account settings → SSH Public Key
   ```
   Discard `aur_key` and `aur_key.pub` after section 4 is done.

4. **Register the package page (one-time).** This step is mandatory — the
   `KSXGitHub/github-actions-deploy-aur` action used in CI fails if the
   AUR repo doesn't exist yet:
   ```bash
   ssh-keyscan -t ed25519 aur.archlinux.org >> ~/.ssh/known_hosts
   git clone ssh://aur@aur.archlinux.org/aitasks.git
   cd aitasks
   # (paste a stub PKGBUILD that builds — minimal valid `pkgname=aitasks`,
   # `pkgver=0.0.0`, `pkgrel=1`, an empty `package(){:;}`)
   makepkg --printsrcinfo > .SRCINFO
   git add PKGBUILD .SRCINFO
   git commit -m "Initial stub"
   git push
   ```
   The package page is now visible at
   `https://aur.archlinux.org/packages/aitasks`. The first real release
   will overwrite the stub PKGBUILD via CI.

5. **Provision GitHub Actions secrets:**
   ```bash
   gh secret set AUR_USERNAME --repo beyondeye/aitasks   # AUR account username
   gh secret set AUR_EMAIL --repo beyondeye/aitasks      # AUR account email
   cat aur_key | gh secret set AUR_SSH_PRIVATE_KEY --repo beyondeye/aitasks
   rm -f aur_key aur_key.pub                             # discard local copies
   ```
   Verify with `gh secret list --repo beyondeye/aitasks` — three new entries
   (`AUR_USERNAME`, `AUR_EMAIL`, `AUR_SSH_PRIVATE_KEY`).

6. **End-to-end local test (on Arch host or `archlinux:base-devel` container).**
   Render the PKGBUILD against the latest released shim, build, install,
   verify:
   ```bash
   VERSION=$(curl -fsSL https://api.github.com/repos/beyondeye/aitasks/releases/latest \
     | jq -r .tag_name | sed 's/^v//')
   SHA256=$(curl -fsSL "https://github.com/beyondeye/aitasks/releases/download/v${VERSION}/ait" \
     | sha256sum | cut -d' ' -f1)
   sed -e "s/VERSION_PLACEHOLDER/${VERSION}/g" \
       -e "s/SHA256_PLACEHOLDER/${SHA256}/g" \
       packaging/aur/PKGBUILD.template > /tmp/PKGBUILD
   cd /tmp && makepkg -si
   namcap PKGBUILD                       # zero errors
   which ait                             # → /usr/bin/ait
   ait setup                             # in a fresh empty git repo
   ```

7. **Cut the first real release.** Same procedure as Homebrew (bump
   `.aitask-scripts/VERSION`, tag `v0.X.Y`, watch the `packaging` job
   fire). Verify the AUR page (`aur.archlinux.org/packages/aitasks`)
   shows the new `pkgver` within 2 min, then `yay -S aitasks` on a
   Manjaro VM installs cleanly.

8. **Troubleshooting** (table covering each error mode):
   - `publish-aur` skipped with "AUR_SSH_PRIVATE_KEY not set — skipping" → set
     the secret per section 5; rerun next tag.
   - `Permission denied (publickey)` on first push → SSH key not registered
     on AUR account, or wrong key in secret.
   - `Repository not found: ssh://aur@aur.archlinux.org/aitasks.git` → section
     4 was skipped (package page never created).
   - `namcap` warnings about `optdepends` style → cosmetic, won't block CI.

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

### 2. Create the directory-level README

`packaging/aur/README.md` — slim reference for someone browsing
`packaging/aur/`. NOT the first-time-setup walkthrough (that lives in
`aidocs/aur_maintainer_setup.md`, Step 0). Sections:

1. **What's here:**
   - `PKGBUILD.template` — Arch PKGBUILD with `VERSION_PLACEHOLDER` /
     `SHA256_PLACEHOLDER` markers. Rendered by the `publish-aur` job in
     `.github/workflows/release-packaging.yml` on every `v*` release tag,
     then pushed to `ssh://aur@aur.archlinux.org/aitasks.git`.
   - This README.

2. **First-time setup:** Pointer to `aidocs/aur_maintainer_setup.md` (one
   paragraph: "If you are setting up AUR distribution for aitasks for the
   first time — creating the AUR account, registering the package page,
   provisioning the SSH-key secret — see
   [aidocs/aur_maintainer_setup.md].").

3. **Local-test snippet (Arch / `archlinux:base-devel` container):**
   ```bash
   VERSION=$(cat .aitask-scripts/VERSION)
   SHA256=$(sha256sum packaging/shim/ait | cut -d' ' -f1)
   sed -e "s/VERSION_PLACEHOLDER/${VERSION}/g" \
       -e "s/SHA256_PLACEHOLDER/${SHA256}/g" \
       packaging/aur/PKGBUILD.template > /tmp/PKGBUILD
   cd /tmp && namcap PKGBUILD
   # makepkg -si requires the source `ait` to be reachable; for fully-local
   # testing, replace the source URL with `file://$(pwd)/packaging/shim/ait`
   # in the rendered PKGBUILD before `makepkg -si`.
   ```

4. **Why shim-only:** one paragraph plus pointer to
   `aidocs/packaging_strategy.md`.

### 3. Add the `publish-aur` job to `release-packaging.yml`

Append to the `jobs:` section of `.github/workflows/release-packaging.yml` (added in t623_2):

```yaml
  publish-aur:
    runs-on: ubuntu-latest
    env:
      VERSION: ${{ inputs.version }}
      AUR_KEY: ${{ secrets.AUR_SSH_PRIVATE_KEY }}
    steps:
      - name: Soft-skip if AUR_SSH_PRIVATE_KEY is not set
        id: gate
        run: |
          if [ -z "${AUR_KEY}" ]; then
            echo "::warning::AUR_SSH_PRIVATE_KEY not set — skipping AUR publish."
            echo "::warning::See aidocs/aur_maintainer_setup.md for first-time setup."
            echo "skip=true" >> "$GITHUB_OUTPUT"
          else
            echo "skip=false" >> "$GITHUB_OUTPUT"
          fi

      - uses: actions/checkout@v4
        if: steps.gate.outputs.skip == 'false'

      - name: Download shim from release
        if: steps.gate.outputs.skip == 'false'
        id: checksum
        run: |
          curl -fsSL "https://github.com/beyondeye/aitasks/releases/download/v${VERSION}/ait" -o ait
          SHA256=$(sha256sum ait | cut -d' ' -f1)
          echo "sha256=$SHA256" >> "$GITHUB_OUTPUT"

      - name: Render PKGBUILD
        if: steps.gate.outputs.skip == 'false'
        run: |
          mkdir -p aur-out
          sed -e "s/VERSION_PLACEHOLDER/${VERSION}/g" \
              -e "s/SHA256_PLACEHOLDER/${{ steps.checksum.outputs.sha256 }}/g" \
              packaging/aur/PKGBUILD.template > aur-out/PKGBUILD
          echo "--- Rendered PKGBUILD ---"
          cat aur-out/PKGBUILD

      - name: Publish to AUR
        if: steps.gate.outputs.skip == 'false'
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

Notes:
- `KSXGitHub/github-actions-deploy-aur` auto-generates `.SRCINFO`, so we
  don't need to commit a template for it.
- The soft-skip `gate` step mirrors the pattern from t623_2's
  `publish-homebrew`. Gate on `AUR_SSH_PRIVATE_KEY` (the only mandatory
  secret — `AUR_USERNAME` / `AUR_EMAIL` are required by the action but
  the SSH key is what fails first if missing). When the secret is unset,
  the job emits a `::warning::` and exits 0; the parent release flow stays
  green even before the maintainer registers the AUR package page.

### 4. Validate

- `actionlint .github/workflows/release-packaging.yml` clean.
- On a local Arch container, render the PKGBUILD with a real version and verify `namcap PKGBUILD` has no errors.

## Verification Checklist

- [ ] `aidocs/aur_maintainer_setup.md` exists, covers all 8 sections from Step 0.
- [ ] `packaging/aur/PKGBUILD.template` exists.
- [ ] `packaging/aur/README.md` exists, covers all 4 sections from Step 2 and points at `aidocs/aur_maintainer_setup.md`.
- [ ] `.github/workflows/release-packaging.yml` parses as valid YAML and includes the `publish-aur` job with the soft-skip `gate` step.
- [ ] Local `makepkg -si` on Arch (or container) using rendered PKGBUILD succeeds; `which ait` resolves to `/usr/bin/ait`.
- [ ] `namcap PKGBUILD` errors zero.
- [ ] (Optional) `actionlint .github/workflows/release-packaging.yml` clean if installed.
- [ ] (Manual, deferred to t623_7) Prerelease tag → AUR page updates within 2 min; `yay -Ss aitasks` shows the new version.
- [ ] (Manual, deferred to t623_7) `yay -S aitasks` (or `paru -S aitasks`) on a fresh Manjaro VM installs cleanly; `ait setup` in a new project works.

## Final Implementation Notes (to be filled in post-implementation)

- **Actual work done:**
- **Deviations from plan:**
- **Issues encountered:**
- **Key decisions:**
- **Notes for sibling tasks:**
