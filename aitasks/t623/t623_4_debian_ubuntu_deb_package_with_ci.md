---
priority: medium
effort: medium
depends: [t623_3]
issue_type: feature
status: Implementing
labels: [install_scripts, installation, packaging, debian, ubuntu, wsl, ci]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-22 18:58
updated_at: 2026-05-04 15:24
---

## Context

Fourth child of t623. Depends on t623_1 (shim extraction) and t623_2 (which introduces `release-packaging.yml`). Shares `packaging/nfpm/nfpm.yaml` config with t623_5 (RPM).

**Why.** `.deb` packaging covers Debian, Ubuntu, all their derivatives, AND WSL2 Ubuntu — the most common Linux user base by volume. Native `apt install ./aitasks_X.Y.Z_all.deb` is the expected install path for these users.

**Approach.** Use [nfpm](https://nfpm.goreleaser.com/) — a single YAML config → both `.deb` and `.rpm`. This child ships `.deb`; t623_5 extends the same config to `.rpm`.

**Maintainer registration.** None required — the `.deb` is built in CI and uploaded as a GitHub release asset using the default `GITHUB_TOKEN`. Users `apt install` it directly from the release page (`https://github.com/beyondeye/aitasks/releases`). No external account, no separate publishing endpoint, no extra GitHub Actions secret. (Hosted APT repo at `apt.aitasks.io` — which would require external infrastructure — is a deferred follow-up per `aidocs/packaging_strategy.md`.) Therefore: **no `aidocs/<pm>_maintainer_setup.md` walkthrough is needed for this child** (unlike t623_2 Homebrew and t623_3 AUR).

## Key Files to Modify

- `packaging/nfpm/nfpm.yaml` (new, shared with t623_5) — nfpm config.
- `.github/workflows/release-packaging.yml` (modified) — add `build-deb` + `test-deb` jobs.

## Reference Files for Patterns

- `aiplans/archived/p623/p623_1_*.md` and `p623_2_*.md` — shim path, release-asset URL, release-packaging.yml structure.
- `aidocs/packaging_strategy.md` — Debian/Ubuntu dep name mapping.
- **External:** `sinelaw/fresh/.github/workflows/linux-packages.yml` — install-test matrix pattern (ubuntu:22.04, ubuntu:24.04, debian:12).

## Implementation Plan

1. Create `packaging/nfpm/nfpm.yaml`:
   ```yaml
   name: aitasks
   arch: all
   platform: linux
   version: ${VERSION}
   version_schema: semver
   section: utils
   priority: optional
   maintainer: aitasks maintainers <noreply@aitasks.io>
   description: |
     File-based task management framework for AI coding agents.
     Installs the ait global shim. Run `ait setup` in your project
     to bootstrap the framework.
   vendor: aitasks
   homepage: https://aitasks.io/
   license: Apache-2.0

   contents:
     - src: ./packaging/shim/ait
       dst: /usr/bin/ait
       file_info:
         mode: 0755

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

   scripts:
     postinstall: ./packaging/nfpm/postinstall.sh
   ```
2. Create `packaging/nfpm/postinstall.sh`:
   ```bash
   #!/bin/sh
   echo "aitasks installed. Run 'ait setup' in your project to bootstrap the framework."
   ```
3. Add `build-deb` job to `.github/workflows/release-packaging.yml`:
   ```yaml
   build-deb:
     runs-on: ubuntu-latest
     env:
       VERSION: ${{ inputs.version }}
     steps:
       - uses: actions/checkout@v4
       - name: Install nfpm
         uses: goreleaser/nfpm-action@v1
       - name: Build .deb
         run: |
           VERSION="${VERSION}" nfpm package \
             --packager deb \
             --config packaging/nfpm/nfpm.yaml \
             --target aitasks_${VERSION}_all.deb
       - name: Upload to release
         env:
           GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
         run: |
           gh release upload "v${VERSION}" "aitasks_${VERSION}_all.deb" --clobber
   ```
4. Add `test-deb` job (matrix over distros):
   ```yaml
   test-deb:
     needs: build-deb
     strategy:
       fail-fast: false
       matrix:
         distro: [ubuntu:22.04, ubuntu:24.04, debian:12]
     runs-on: ubuntu-latest
     container: ${{ matrix.distro }}
     env:
       DEBIAN_FRONTEND: noninteractive
       VERSION: ${{ inputs.version }}
     steps:
       - name: Download .deb from release
         run: |
           apt-get update && apt-get install -y curl
           curl -fsSL "https://github.com/beyondeye/aitasks/releases/download/v${VERSION}/aitasks_${VERSION}_all.deb" -o ait.deb
       - name: Install
         run: apt-get install -y ./ait.deb
       - name: Verify
         run: |
           test -x /usr/bin/ait
           ait --help 2>&1 | head -5
           cd /tmp && git init testproj && cd testproj
           # ait setup expects interactive input; smoke-test with echo pipe
           echo "" | ait setup || true
       - name: Uninstall
         run: |
           apt-get remove -y aitasks
           test ! -e /usr/bin/ait
   ```

## Verification Steps

1. **Local build:**
   - Install nfpm (`brew install nfpm` on macOS, or download binary).
   - `VERSION=0.17.0 nfpm package --packager deb --config packaging/nfpm/nfpm.yaml --target /tmp/aitasks_0.17.0_all.deb`.
   - `lintian /tmp/aitasks_0.17.0_all.deb` — no errors.
   - `dpkg-deb --contents /tmp/aitasks_0.17.0_all.deb` lists only `/usr/bin/ait`.
2. **Local install test on Ubuntu/Debian container:**
   - `docker run --rm -it ubuntu:24.04 bash` → `apt-get update && apt-get install -y /tmp/aitasks_*.deb` → `ait --help`.
3. **CI matrix:** after push, `test-deb` job passes on ubuntu:22.04, ubuntu:24.04, debian:12.
4. **WSL sanity (manual):** on a WSL2 Ubuntu 24.04 install, download `.deb` from the release, `sudo apt install ./aitasks_X.Y.Z_all.deb`, run `ait setup`.
5. **Release asset:** after tagging, GitHub release has `aitasks_X.Y.Z_all.deb` visible in the release page UI.
