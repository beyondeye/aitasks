---
Task: t623_5_fedora_rhel_rpm_package_with_ci.md
Parent Task: aitasks/t623_more_installation_methods.md
Sibling Tasks: aitasks/t623/t623_1_*.md, t623_2_*.md, t623_3_*.md, t623_4_*.md, t623_6_*.md
Archived Sibling Plans: aiplans/archived/p623/p623_1_*.md, p623_2_*.md, p623_3_*.md, p623_4_*.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Implementation Plan: t623_5 — Fedora/RHEL .rpm packaging

## Prerequisites

- t623_1 merged (shim + strategy).
- t623_2 merged (release-packaging.yml scaffolding).
- t623_4 merged (created `packaging/nfpm/nfpm.yaml` with deb overrides; this child adds rpm overrides).

## Steps

### 1. Extend `packaging/nfpm/nfpm.yaml` with rpm overrides

Add a sibling block under `overrides:` (alongside the existing `deb:` block):

```yaml
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

Note: `depends` syntax differs (`pkg (>= ver)` for deb vs. `pkg >= ver` for rpm); nfpm translates appropriately per-packager.

### 2. Add `build-rpm` job to `release-packaging.yml`

Mirror `build-deb` from t623_4:

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

### 3. Add `test-rpm` job matrix

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
      - name: Install curl
        run: dnf install -y curl ca-certificates

      - name: Download .rpm from release
        run: |
          curl -fsSL "https://github.com/beyondeye/aitasks/releases/download/v${VERSION}/aitasks-${VERSION}-1.noarch.rpm" -o /tmp/ait.rpm

      - name: Install
        run: dnf install -y /tmp/ait.rpm

      - name: Verify
        run: |
          test -x /usr/bin/ait
          cd /tmp
          ait some-command 2>&1 | grep -i "No ait project" || \
            (echo "Shim did not emit expected no-project message"; exit 1)

      - name: Uninstall
        run: |
          dnf remove -y aitasks
          test ! -e /usr/bin/ait
```

### 4. Validate

- Local: `VERSION=0.17.0 nfpm package --packager rpm --config packaging/nfpm/nfpm.yaml --target /tmp/ait.rpm`.
  - `rpm -qpl /tmp/ait.rpm` lists only `/usr/bin/ait`.
  - `rpm -qpR /tmp/ait.rpm` shows the expected deps.
  - `rpmlint /tmp/ait.rpm` — errors zero; warnings triaged.
- `actionlint .github/workflows/release-packaging.yml` clean.

## Verification Checklist

- [ ] `packaging/nfpm/nfpm.yaml` `overrides.rpm` block present.
- [ ] Local nfpm build produces a valid `.rpm`.
- [ ] `rpmlint` errors zero.
- [ ] CI matrix passes on fedora:40, fedora:41, rockylinux:9.
- [ ] Manual test on a Fedora VM: `sudo dnf install aitasks-*.rpm`, `ait setup` works.
- [ ] After `dnf remove aitasks`, `/usr/bin/ait` is gone.

## Final Implementation Notes (to be filled in post-implementation)

- **Actual work done:**
- **Deviations from plan:**
- **Issues encountered:**
- **Key decisions:**
- **Notes for sibling tasks:** (t623_6 consumes URLs / version ranges).
