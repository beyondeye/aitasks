---
Task: t623_4_debian_ubuntu_deb_package_with_ci.md
Parent Task: aitasks/t623_more_installation_methods.md
Sibling Tasks: aitasks/t623/t623_1_*.md, t623_2_*.md, t623_3_*.md, t623_5_*.md, t623_6_*.md
Archived Sibling Plans: aiplans/archived/p623/p623_1_*.md, p623_2_*.md, p623_3_*.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-04 15:31
---

# Implementation Plan: t623_4 — Debian/Ubuntu .deb packaging

## Context

Fourth child of t623 (more installation methods). Adds `.deb` packaging so that
Debian, Ubuntu, all their derivatives, and WSL2 Ubuntu users can `apt install`
aitasks instead of curl-piping the install script. Uses [nfpm](https://nfpm.goreleaser.com/)
so the same YAML config can be extended by t623_5 to also produce `.rpm`.

The `.deb` is built in CI on tag, uploaded as a GitHub release asset, and verified
by an install-test matrix on real distro containers. No external maintainer
account is needed — the default `GITHUB_TOKEN` is sufficient. Hosted APT repo
at `apt.aitasks.io` is a deferred follow-up per `aidocs/packaging_strategy.md`.

## Verification baseline (confirmed against current codebase)

- `packaging/shim/ait` exists (87-line bash shim, executable). ✓
- `.github/workflows/release-packaging.yml` exists with `publish-homebrew` and
  `publish-aur` jobs (`build-deb` + `test-deb` will be appended). ✓
- `.github/workflows/release.yml` invokes `release-packaging.yml` from the
  `packaging` job, which `needs: [plan, release]` — so the GitHub release
  exists by the time `build-deb` runs and `gh release upload` succeeds. ✓
- `release.yml` already attaches `packaging/shim/ait` as the asset named `ait`
  at `https://github.com/beyondeye/aitasks/releases/download/v${VERSION}/ait`. ✓
- `aidocs/packaging_strategy.md` declares the deb dep set as
  `bash (>= 4.0), python3 (>= 3.9), fzf, jq, git, zstd, tar, curl` plus
  `Recommends: gh | glab` — matches this plan. ✓
- The shim's no-project error is `"Error: No ait project found in any parent
  directory of $PWD"` (`packaging/shim/ait:84`) — the test-deb verification
  grep `"No ait project"` matches. ✓

## Prerequisites

1. t623_1 merged (shim extracted to `packaging/shim/ait`, release asset available).
2. t623_2 merged (`release-packaging.yml` scaffolding + `plan` job in `release.yml`
   exposes version output).

Both prerequisites are confirmed satisfied on the current branch.

## Steps

### 1. Create the shared nfpm config

`packaging/nfpm/nfpm.yaml` (shared with t623_5; this child creates it with deb
overrides):

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
  Installs the ait global shim. Run 'ait setup' in your project to
  bootstrap the framework.
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

### 2. Create the postinstall script

`packaging/nfpm/postinstall.sh`:

```sh
#!/bin/sh
echo "aitasks installed. Run 'ait setup' in your project to bootstrap the framework."
```

`chmod +x packaging/nfpm/postinstall.sh`.

### 3. Add `build-deb` job to `release-packaging.yml`

Append after the existing `publish-aur` job (jobs run in parallel — no `needs:`
linkage to `publish-homebrew`/`publish-aur` because the .deb path is independent):

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

### 4. Add `test-deb` job matrix

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
      - name: Install curl
        run: |
          apt-get update
          apt-get install -y --no-install-recommends curl ca-certificates

      - name: Download .deb from release
        run: |
          curl -fsSL "https://github.com/beyondeye/aitasks/releases/download/v${VERSION}/aitasks_${VERSION}_all.deb" -o /tmp/ait.deb
          ls -la /tmp/ait.deb

      - name: Install
        run: |
          apt-get install -y /tmp/ait.deb

      - name: Verify
        run: |
          test -x /usr/bin/ait
          ait --help 2>&1 | head -10 || true
          # Shim should report "No ait project found" in an empty dir
          cd /tmp
          ait some-command 2>&1 | grep -i "No ait project" || \
            (echo "Shim did not emit expected no-project message"; exit 1)

      - name: Uninstall
        run: |
          apt-get remove -y aitasks
          test ! -e /usr/bin/ait
```

### 5. Validate locally

- Install nfpm (`brew install nfpm` on macOS, or download binary from
  https://github.com/goreleaser/nfpm/releases).
- Build:
  ```bash
  VERSION=0.17.0 nfpm package \
    --packager deb \
    --config packaging/nfpm/nfpm.yaml \
    --target /tmp/ait.deb
  ```
- Inspect:
  - `dpkg-deb --contents /tmp/ait.deb` lists `/usr/bin/ait` + metadata only.
  - `dpkg-deb --info /tmp/ait.deb` shows the correct deps and recommends.
  - `lintian /tmp/ait.deb` — errors zero; warnings triaged.
- Lint workflow YAML: `actionlint .github/workflows/release-packaging.yml` clean.

## Verification Checklist

- [ ] `packaging/nfpm/nfpm.yaml` and `packaging/nfpm/postinstall.sh` exist.
- [ ] Local nfpm build produces a valid `.deb` with `ait` shim at `/usr/bin/ait`.
- [ ] `lintian` on the built .deb — errors zero.
- [ ] CI matrix passes on ubuntu:22.04, ubuntu:24.04, debian:12 after tagging
      a prerelease.
- [ ] Manual test on WSL2 Ubuntu 24.04: download `.deb` from release,
      `sudo apt install ./aitasks_*.deb`, `ait setup` in fresh project.
- [ ] After uninstall via `apt remove aitasks`, `/usr/bin/ait` is gone.

## Step 9: Post-Implementation

After review and approval, the standard archival flow applies:

- Code commit using `feature: <description> (t623_4)` format.
- Plan-file commit using `./ait git`.
- Run `./.aitask-scripts/aitask_archive.sh 623_4` to mark Done, move task and
  plan into archived/, release the lock, and commit. Push with `./ait git push`.

## Final Implementation Notes (to be filled in post-implementation)

- **Actual work done:**
- **Deviations from plan:**
- **Issues encountered:**
- **Key decisions:**
- **Upstream defects identified:**
- **Notes for sibling tasks:** (t623_5 extends this child's nfpm.yaml — document
  any postinstall conventions, group/section quirks, or nfpm version pin
  decisions).
