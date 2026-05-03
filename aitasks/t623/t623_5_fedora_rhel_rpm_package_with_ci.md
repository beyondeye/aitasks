---
priority: medium
effort: low
depends: [t623_4]
issue_type: feature
status: Ready
labels: [install_scripts, installation, packaging, fedora, rhel, ci]
created_at: 2026-04-22 18:58
updated_at: 2026-05-03 18:56
---

## Context

Fifth child of t623. Depends on t623_4 (which creates `packaging/nfpm/nfpm.yaml`). This child extends that config with RPM-specific overrides and adds CI jobs — it does NOT create new packaging config from scratch.

**Why.** Fedora, Rocky Linux, AlmaLinux, and RHEL users expect `dnf install` of an `.rpm`. This child makes `sudo dnf install aitasks-<ver>-1.noarch.rpm` (downloaded from GitHub releases) work.

**Effort: low** — the shim-only model + shared nfpm config means this child is mostly YAML additions (an `overrides.rpm` block) + a symmetric CI job pair.

**Maintainer registration.** None required — the `.rpm` is built in CI and uploaded as a GitHub release asset using the default `GITHUB_TOKEN`. Users `dnf install` it directly from the release page. No external account, no separate publishing endpoint, no extra GitHub Actions secret. (Hosted DNF/RPM repo at `rpm.aitasks.io` is a deferred follow-up per `aidocs/packaging_strategy.md`.) Therefore: **no `aidocs/<pm>_maintainer_setup.md` walkthrough is needed for this child** (unlike t623_2 Homebrew and t623_3 AUR).

## Key Files to Modify

- `packaging/nfpm/nfpm.yaml` (modified — adds `overrides.rpm` block).
- `.github/workflows/release-packaging.yml` (modified — adds `build-rpm` + `test-rpm` jobs mirroring the .deb pair from t623_4).

## Reference Files for Patterns

- `aiplans/archived/p623/p623_1_*.md` through `p623_4_*.md` — strategy doc, shim path, existing packaging workflow.
- `aidocs/packaging_strategy.md` — Fedora/RHEL dep name mapping.
- **External:** `sinelaw/fresh/.github/workflows/linux-packages.yml` (lines with `test-rpm-package`) — matrix pattern (`fedora:40`, `fedora:41`, `rockylinux:9`).
- `packaging/nfpm/nfpm.yaml` (from t623_4) — existing structure. Extend, don't duplicate.

## Implementation Plan

1. Extend `packaging/nfpm/nfpm.yaml` with an `overrides.rpm` block alongside the existing `overrides.deb`:
   ```yaml
   overrides:
     deb:
       depends:
         - bash (>= 4.0)
         - python3 (>= 3.9)
         - fzf
         - jq
         - git
         - zstd
         - tar
         - curl
       recommends:
         - gh
         - glab
     rpm:
       depends:
         - bash >= 4.0
         - python3 >= 3.9
         - fzf
         - jq
         - git
         - zstd
         - tar
         - curl
       recommends:
         - gh
         - glab
       group: Development/Tools
   ```
   Note: `depends` syntax differs between deb (`pkg (>= ver)`) and rpm (`pkg >= ver`); nfpm handles this automatically.
2. Add `build-rpm` job to `.github/workflows/release-packaging.yml` mirroring `build-deb`:
   ```yaml
   build-rpm:
     runs-on: ubuntu-latest
     env:
       VERSION: ${{ inputs.version }}
     steps:
       - uses: actions/checkout@v4
       - name: Install nfpm
         uses: goreleaser/nfpm-action@v1
       - name: Build .rpm
         run: |
           VERSION="${VERSION}" nfpm package \
             --packager rpm \
             --config packaging/nfpm/nfpm.yaml \
             --target aitasks-${VERSION}-1.noarch.rpm
       - name: Upload to release
         env:
           GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
         run: |
           gh release upload "v${VERSION}" "aitasks-${VERSION}-1.noarch.rpm" --clobber
   ```
3. Add `test-rpm` job (matrix over Fedora/Rocky):
   ```yaml
   test-rpm:
     needs: build-rpm
     strategy:
       fail-fast: false
       matrix:
         distro: [fedora:40, fedora:41, rockylinux:9]
     runs-on: ubuntu-latest
     container: ${{ matrix.distro }}
     env:
       VERSION: ${{ inputs.version }}
     steps:
       - name: Download .rpm from release
         run: |
           dnf install -y curl
           curl -fsSL "https://github.com/beyondeye/aitasks/releases/download/v${VERSION}/aitasks-${VERSION}-1.noarch.rpm" -o ait.rpm
       - name: Install
         run: dnf install -y ./ait.rpm
       - name: Verify
         run: |
           test -x /usr/bin/ait
           ait --help 2>&1 | head -5
       - name: Uninstall
         run: |
           dnf remove -y aitasks
           test ! -e /usr/bin/ait
   ```

## Verification Steps

1. **Local build:**
   - `VERSION=0.17.0 nfpm package --packager rpm --config packaging/nfpm/nfpm.yaml --target /tmp/aitasks-0.17.0-1.noarch.rpm`.
   - `rpmlint /tmp/aitasks-*.rpm` — errors zero; warnings triaged.
   - `rpm -qpl /tmp/aitasks-*.rpm` lists only `/usr/bin/ait`.
2. **Local install test on Fedora container:**
   - `docker run --rm -it fedora:40 bash` → `dnf install -y /tmp/aitasks-*.rpm` → `ait --help`.
3. **CI matrix:** `test-rpm` job passes on fedora:40, fedora:41, rockylinux:9.
4. **Release asset:** after tagging, GitHub release has `aitasks-X.Y.Z-1.noarch.rpm`.
5. **Parity with .deb:** install sizes, file lists, and dependency declarations are symmetric with the .deb from t623_4 (except dep syntax).
