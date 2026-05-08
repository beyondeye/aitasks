# AUR Maintainer Setup

This is the comprehensive first-time-setup walkthrough for the project owner
(or maintainer) wiring up the **Arch User Repository (AUR) distribution
channel** for the `aitasks` framework. It is meant to be read once,
end-to-end, when first shipping the AUR package.

For day-to-day reference (PKGBUILD structure, how the CI is wired, where the
template lives) see:

- [`packaging/aur/README.md`](../packaging/aur/README.md) — directory-level
  reference for the PKGBUILD template.
- [`aidocs/packaging_strategy.md`](packaging_strategy.md) — cross-PM strategy
  (why we ship a shim only, dependency-name mapping across PMs,
  release-cadence policy).
- [`aidocs/homebrew_maintainer_setup.md`](homebrew_maintainer_setup.md) —
  sibling walkthrough for the Homebrew tap; shares the same overall shape.

## 1. What the AUR is

The [Arch User Repository](https://wiki.archlinux.org/title/Arch_User_Repository)
is a community-maintained collection of build scripts (`PKGBUILD` files)
hosted at `aur.archlinux.org`. Helpers like
[`yay`](https://github.com/Jguer/yay) or
[`paru`](https://github.com/Morganamilo/paru) fetch the PKGBUILD, run
`makepkg` to build the package, and install the resulting `.pkg.tar.zst`
through `pacman`. Distribution via the AUR is fully self-served — anyone with
an AUR account can publish a package, no review process.

**Plain `pacman -S aitasks` will NOT work.** `pacman` only installs from
official Arch repositories (`core`, `extra`, `multilib`). Getting accepted
into an official repository is a separate, gated community process and is
out of scope. AUR users install via:

```bash
yay -S aitasks       # or
paru -S aitasks      # or, by hand:
git clone https://aur.archlinux.org/aitasks.git && cd aitasks && makepkg -si
```

For aitasks, the AUR package page is at
**[`aur.archlinux.org/packages/aitasks`](https://aur.archlinux.org/packages/aitasks)**
(page to be created in section 4). The page is auto-bumped on every
`v*` release tag of `beyondeye/aitasks` by the `publish-aur` job in
`.github/workflows/release-packaging.yml`.

References:
- <https://wiki.archlinux.org/title/Arch_User_Repository>
- <https://wiki.archlinux.org/title/PKGBUILD>
- <https://wiki.archlinux.org/title/Makepkg>

## 2. Create an AUR account

Done **once**, by hand, before the first release after this task lands.

1. Visit <https://aur.archlinux.org/register>.

2. Pick a username — this will appear as the `Maintainer:` field on the
   `aur.archlinux.org/packages/aitasks` page, so choose something
   recognizable (e.g. `aitasks-bot` or your own handle).

3. Fill in a real email address (used for password recovery and AUR
   notifications), then submit.

4. Confirm the email when the verification message arrives.

5. Sign in to <https://aur.archlinux.org/login>.

## 3. Generate an ed25519 SSH key for the bot

The CI job authenticates to `aur.archlinux.org` over SSH. AUR only accepts
ed25519 keys for new uploads; do not generate an RSA key.

1. From any workstation, generate a fresh ed25519 keypair specific to AUR
   deployment:

   ```bash
   ssh-keygen -t ed25519 -f aur_key -C aur-deploy -N ""
   ```

   This creates `aur_key` (private) and `aur_key.pub` (public) in the
   current directory. The empty passphrase (`-N ""`) is required — the
   `KSXGitHub/github-actions-deploy-aur` action cannot prompt for a
   passphrase.

2. Print the public key:

   ```bash
   cat aur_key.pub
   ```

   Copy the entire single line (`ssh-ed25519 AAAA... aur-deploy`).

3. Sign in to your AUR account, click your username (top right) →
   "My Account", paste the public key into the **SSH Public Key** field,
   click "Update".

4. **Keep `aur_key` (the private file) on hand** — it will be uploaded to
   GitHub as a secret in section 5. Do NOT commit it to any repo.

## 4. Register the AUR package page (one-time)

This step is **mandatory** — the `KSXGitHub/github-actions-deploy-aur`
action used in CI fails with `Repository not found` if the AUR repo for
the package does not yet exist. The fix is to push a stub PKGBUILD by
hand, after which CI takes over for every subsequent release.

1. Accept the AUR host key once so SSH does not prompt:

   ```bash
   ssh-keyscan -t ed25519 aur.archlinux.org >> ~/.ssh/known_hosts
   ```

2. Tell SSH to use the bot key for `aur.archlinux.org` (temporary, just
   for the bootstrap push). Easiest way: pass `-i` via `GIT_SSH_COMMAND`:

   ```bash
   export GIT_SSH_COMMAND="ssh -i $(pwd)/aur_key -o IdentitiesOnly=yes"
   ```

3. Clone the (still-empty) AUR repo for `aitasks`:

   ```bash
   git clone ssh://aur@aur.archlinux.org/aitasks.git aur-aitasks
   cd aur-aitasks
   ```

   First-time clones of brand-new packages succeed even if no commits
   exist yet — AUR creates the empty repo on the first push.

4. Write a minimal valid stub `PKGBUILD`:

   ```bash
   cat > PKGBUILD <<'EOF'
   # Maintainer: aitasks maintainers <noreply@aitasks.io>
   pkgname=aitasks
   pkgver=0.0.0
   pkgrel=1
   pkgdesc="File-based task management framework for AI coding agents (placeholder)"
   arch=('any')
   url="https://aitasks.io/"
   license=('Apache')
   package() {
       :
   }
   EOF
   makepkg --printsrcinfo > .SRCINFO
   ```

   The empty `package()` function makes `makepkg` succeed without
   producing an installable artifact. AUR requires both `PKGBUILD` and
   `.SRCINFO` on every push; the `KSXGitHub/github-actions-deploy-aur`
   action will regenerate `.SRCINFO` automatically on later pushes.

5. Commit and push:

   ```bash
   git add PKGBUILD .SRCINFO
   git commit -m "Initial stub PKGBUILD (placeholder until first auto-bump)"
   git push origin master
   ```

   Note: the AUR uses `master` as the default branch, not `main`.

6. Visit <https://aur.archlinux.org/packages/aitasks> — the package page
   should now exist, showing your username as `Maintainer:` and the stub
   `pkgver=0.0.0`. The first real release will overwrite `PKGBUILD` and
   `.SRCINFO` via CI.

## 5. Provision GitHub Actions secrets

The `publish-aur` job needs three secrets to push to AUR. All three must
be present, otherwise the soft-skip guard in the workflow will skip the
job (see section 8 troubleshooting).

| Secret | Value |
|---|---|
| `AUR_USERNAME` | Your AUR account username (from section 2) |
| `AUR_EMAIL` | The email address you registered with AUR (used as `commit_email` for AUR pushes) |
| `AUR_SSH_PRIVATE_KEY` | The full contents of the **private** key file `aur_key` from section 3, including the leading `-----BEGIN OPENSSH PRIVATE KEY-----` and trailing `-----END OPENSSH PRIVATE KEY-----` lines and a final newline |

Run from any terminal where you are signed in to `gh`:

```bash
gh secret set AUR_USERNAME --repo beyondeye/aitasks
# (paste username at prompt)

gh secret set AUR_EMAIL --repo beyondeye/aitasks
# (paste email at prompt)

cat aur_key | gh secret set AUR_SSH_PRIVATE_KEY --repo beyondeye/aitasks
# (this pipes the entire private key file, whitespace preserved)
```

Verify all three are present:

```bash
gh secret list --repo beyondeye/aitasks
```

The output should include rows for `AUR_USERNAME`, `AUR_EMAIL`, and
`AUR_SSH_PRIVATE_KEY` with recent `Updated` timestamps.

After provisioning, **discard the local key files** so a leak from your
workstation does not give attackers AUR push rights:

```bash
rm -f aur_key aur_key.pub
unset GIT_SSH_COMMAND
```

(If the key ever leaks, regenerate per section 3, update the AUR account's
SSH Public Key, and re-run `gh secret set AUR_SSH_PRIVATE_KEY`.)

## 6. End-to-end local test

Sanity-check the PKGBUILD on an Arch host (or in an
`archlinux:base-devel` container) **before** tagging the first real
release. This validates the rendered template, deps, and shim install
without touching CI.

Run from the repo root — the `sed` step reads `packaging/aur/PKGBUILD.template`
as a relative path:

```bash
cd "$(git rev-parse --show-toplevel)"

# Pick the latest released aitasks version
VERSION=$(curl -fsSL https://api.github.com/repos/beyondeye/aitasks/releases/latest \
  | jq -r .tag_name | sed 's/^v//')
echo "Testing with v${VERSION}"

# Compute the shim's SHA256 from the release asset
SHA256=$(curl -fsSL "https://github.com/beyondeye/aitasks/releases/download/v${VERSION}/ait" \
  | sha256sum | cut -d' ' -f1)
echo "Shim SHA256: ${SHA256}"

# Render the template
sed -e "s/VERSION_PLACEHOLDER/${VERSION}/g" \
    -e "s/SHA256_PLACEHOLDER/${SHA256}/g" \
    packaging/aur/PKGBUILD.template > /tmp/PKGBUILD

# Static-check the PKGBUILD
cd /tmp
namcap PKGBUILD                            # expect: zero errors

# Build, install, run (requires base-devel)
makepkg -si --noconfirm                    # builds and installs via pacman -U
which ait                                  # → /usr/bin/ait
ait setup                                  # in a fresh empty git repo
```

**Notes:**

- `makepkg -si` requires a working `base-devel` toolchain. On a stock
  Arch host run `sudo pacman -S --needed base-devel` once.
- `namcap` is the Arch package linter; it catches missing deps,
  filesystem-layout violations, and PKGBUILD style issues.
  `sudo pacman -S namcap` if not already installed.
- For container-based testing:
  ```bash
  docker run -it --rm archlinux:base-devel bash
  pacman -Syu --noconfirm namcap git fzf jq zstd curl
  # then run the snippet above (skip sudo since you are root in the container)
  ```
- The PKGBUILD's `source=` line uses `pkgver` interpolation, so the
  template's `pkgver=VERSION_PLACEHOLDER` substitution flows into the
  release-asset URL automatically.

## 7. Cut the first real release

After sections 2-6 are complete:

1. **Bump VERSION and tag a release** on `beyondeye/aitasks`:

   ```bash
   echo "0.19.3" > .aitask-scripts/VERSION
   git add .aitask-scripts/VERSION
   git commit -m "chore: Bump version to 0.19.3"
   git push
   git tag v0.19.3
   git push origin v0.19.3
   ```

2. **Watch the GitHub Actions run** at
   <https://github.com/beyondeye/aitasks/actions>. The job graph fires:
   `plan` → `release` → `packaging` (which calls
   `release-packaging.yml`'s `publish-homebrew` and `publish-aur` jobs in
   parallel).

3. **Verify the AUR page** received the new PKGBUILD within ~2 minutes:
   - Visit <https://aur.archlinux.org/packages/aitasks>.
   - The "Package Details" panel should show `Package Version: 0.19.3-1`.
   - The "Sources" section should show `ait` pointing at the `v0.19.3`
     release asset URL.

4. **Verify end-user install** works (on an Arch / Manjaro host):

   ```bash
   yay -Syu               # refresh AUR cache
   yay -Ss aitasks        # confirm the new version is searchable
   yay -S aitasks         # build + install
   which ait              # → /usr/bin/ait
   ait setup              # in a fresh empty git repo
   ```

   If the version still shows the previous tag, AUR's database may not
   have refreshed yet — wait a minute or `yay -Syu --aur` to force-refresh.

## 8. Troubleshooting

| Symptom | Cause / Fix |
|---|---|
| `publish-aur` job is **skipped** with annotation "AUR_SSH_PRIVATE_KEY not set — skipping" | This is the soft-skip guard. The `release` job succeeded; only the AUR publish was skipped because the secret is empty/unset. Set the secret (section 5) — next tag will publish. |
| `publish-aur` fails with `Permission denied (publickey)` on first push | The SSH private key in `AUR_SSH_PRIVATE_KEY` does not match a key registered on the AUR account, or only the public key was uploaded. Re-run section 3, update the AUR account's SSH Public Key field, then `gh secret set AUR_SSH_PRIVATE_KEY` with the **private** key contents. |
| `publish-aur` fails with `Repository not found: ssh://aur@aur.archlinux.org/aitasks.git` | Section 4 was skipped — the AUR package page does not exist yet. Run the bootstrap push by hand, then re-run the failed workflow. |
| `namcap` warnings about `optdepends` style or `arch=('any')` for a binary | Cosmetic, won't block CI or `yay -S`. Worth cleaning up if convenient, but not blocking. |
| User reports `yay -S aitasks` fails with `signature is invalid` or `package corrupted` | The release asset for `ait` was re-uploaded after the AUR PKGBUILD was rendered, so the SHA256 in the PKGBUILD no longer matches. Re-tag the release to re-run `publish-aur`. |
| AUR page shows the old `pkgver` after the workflow ran | AUR's database refreshes asynchronously. Wait ~1 minute and reload. If still stale after 5 minutes, check the workflow logs — `publish-aur` may have skipped or failed silently. |
| Need to remove the package from AUR (e.g., for re-bootstrap) | Visit the package page → "Package Actions" → "Disown Package", then either let it be orphaned or re-claim it. To delete entirely, file a request with the AUR Trusted Users (rare). |
