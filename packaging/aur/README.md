# `packaging/aur/` — Arch User Repository (AUR) packaging

Slim directory-level reference for the AUR packaging assets shipped with
`beyondeye/aitasks`. **Setting up AUR distribution for the first time?**
See the comprehensive walkthrough at
[`aidocs/aur_maintainer_setup.md`](../../aidocs/aur_maintainer_setup.md).

## What's here

- **`PKGBUILD.template`** — Arch `PKGBUILD` with `VERSION_PLACEHOLDER` and
  `SHA256_PLACEHOLDER` markers. Rendered by the `publish-aur` job in
  [`.github/workflows/release-packaging.yml`](../../.github/workflows/release-packaging.yml)
  on every `v*` release tag, then pushed to
  `ssh://aur@aur.archlinux.org/aitasks.git` via the
  [`KSXGitHub/github-actions-deploy-aur`](https://github.com/KSXGitHub/github-actions-deploy-aur)
  action. The action regenerates `.SRCINFO` automatically — no template
  for it lives here.
- **This README.**

## First-time setup

If you are setting up AUR distribution for `aitasks` for the first time —
creating the AUR account, generating the ed25519 SSH key, registering the
package page on `aur.archlinux.org`, and provisioning the three GitHub
Actions secrets — see
[`aidocs/aur_maintainer_setup.md`](../../aidocs/aur_maintainer_setup.md).
That walkthrough covers the entire flow end-to-end with troubleshooting.

## Local-test snippet (Arch / `archlinux:base-devel` container)

Static-check and (optionally) build-install the rendered PKGBUILD against
the **local** shim file, without needing a published GitHub release:

```bash
VERSION=$(cat .aitask-scripts/VERSION)
SHA256=$(sha256sum packaging/shim/ait | cut -d' ' -f1)
sed -e "s/VERSION_PLACEHOLDER/${VERSION}/g" \
    -e "s/SHA256_PLACEHOLDER/${SHA256}/g" \
    packaging/aur/PKGBUILD.template > /tmp/PKGBUILD
cd /tmp && namcap PKGBUILD
```

`namcap PKGBUILD` runs the Arch package linter (zero errors expected;
warnings reviewed and documented in the maintainer guide).

For a full `makepkg -si` test against the local shim, replace the
`source=` URL in `/tmp/PKGBUILD` with `file://$(realpath packaging/shim/ait)`
before running `makepkg -si --noconfirm`. This bypasses the network fetch
even though the rendered PKGBUILD's `source=` field points at a release
asset that may not exist yet.

## Why shim-only

The PKGBUILD ships only the `ait` global shim (~4 KB). The shim, on first
invocation in any project, runs `ait setup` which downloads the rest of
the framework into the local repository. This keeps the AUR package
small, fast to build, and trivially auto-bumpable on every release. See
[`aidocs/packaging_strategy.md`](../../aidocs/packaging_strategy.md) for
the full cross-PM rationale.
