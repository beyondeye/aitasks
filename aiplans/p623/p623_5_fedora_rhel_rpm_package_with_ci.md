---
Task: t623_5_fedora_rhel_rpm_package_with_ci.md
Parent Task: aitasks/t623_more_installation_methods.md
Sibling Tasks: aitasks/t623/t623_1_*.md, t623_2_*.md, t623_3_*.md, t623_4_*.md, t623_6_*.md
Archived Sibling Plans: aiplans/archived/p623/p623_1_*.md, p623_2_*.md, p623_3_*.md, p623_4_*.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-04 16:13
---

# Implementation Plan: t623_5 — Fedora/RHEL .rpm packaging

## Context

Fifth child of t623 (more installation methods). Adds `.rpm` packaging on top
of the shared nfpm config introduced by sibling t623_4, so Fedora, Rocky,
AlmaLinux, and RHEL users can `dnf install` the aitasks shim instead of
piping `install.sh`. Shim-only model — package contents are just
`/usr/bin/ait`; framework downloads on first `ait setup`.

The `.rpm` is built in CI on tag, uploaded as a GitHub release asset, and
verified by an install-test matrix on real distro containers. No external
maintainer account is needed — the default `GITHUB_TOKEN` is sufficient.
Hosted DNF repo at `rpm.aitasks.io` is a deferred follow-up per
`aidocs/packaging_strategy.md`.

## Verification baseline (confirmed against current codebase, 2026-05-04)

- `packaging/nfpm/nfpm.yaml` exists with `overrides.deb` block from t623_4 ✓
  (this child appends `overrides.rpm` alongside it).
- `packaging/nfpm/postinstall.sh` exists, executable, single `echo` line ✓
  — reusable as-is by the rpm packager (nfpm dispatches the same script
  to deb postinst and rpm `%post`).
- `packaging/shim/ait` exists (87-line bash shim, executable) ✓.
- `.github/workflows/release-packaging.yml` exists with `publish-homebrew`,
  `publish-aur`, `build-deb`, `test-deb` jobs ✓ — `build-rpm` + `test-rpm`
  will be appended after `test-deb`.
- `.github/workflows/release.yml` invokes `release-packaging.yml` with
  `version` input from `plan` job → GitHub release exists by the time
  `build-rpm` runs and `gh release upload` succeeds ✓.
- Shim's no-project error at `packaging/shim/ait:84` is `"Error: No ait
  project found in any parent directory of $PWD"` — the test-rpm
  verification grep `"No ait project"` matches ✓.
- `aidocs/packaging_strategy.md:117` declares the rpm dep set as
  `bash >= 4.0, python3 >= 3.9, fzf, jq, git, zstd, tar, curl` plus
  `Recommends: (gh or glab)` — matches this plan ✓.
- `aidocs/packaging_strategy.md:124-138` Dependency name mapping table
  confirms rpm-syntax pins (no parens) match the plan ✓.

## Prerequisites

1. t623_1 merged (shim extracted to `packaging/shim/ait`).
2. t623_2 merged (`release-packaging.yml` scaffolding + `plan` job in
   `release.yml` exposes version output).
3. t623_4 merged (created `packaging/nfpm/nfpm.yaml` with deb overrides;
   this child adds rpm overrides alongside).

All three prerequisites are confirmed satisfied on the current branch.

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

Notes:
- `depends:` syntax differs from deb (`pkg (>= ver)` for deb vs.
  `pkg >= ver` for rpm); nfpm translates appropriately per-packager.
- `recommends:` listed as separate `gh` and `glab` rather than the
  `(gh or glab)` boolean syntax from `packaging_strategy.md` —
  consistent with t623_4's deb decision (nfpm serializes each list
  entry verbatim with comma separators; the boolean form would have
  to be a single literal string and is functionally equivalent for
  end-users since neither is a hard requirement).
- `group: Development/Tools` is rpm-specific (deb uses top-level
  `section: utils`).
- Reuses the existing top-level `scripts.postinstall:
  ./packaging/nfpm/postinstall.sh` — nfpm dispatches it to the rpm
  `%post` scriptlet automatically.

### 2. Add `build-rpm` job to `release-packaging.yml`

Append after the existing `test-deb` job. Mirror `build-deb` from t623_4:

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

- `goreleaser/nfpm-action@v1` is the same major-version pin used by
  `build-deb` — keep deb/rpm builds in lockstep.
- `--clobber` makes the upload idempotent across re-runs of the same
  tag, matching deb behavior.
- Asset naming `aitasks-${VERSION}-1.noarch.rpm` follows rpm convention
  (`<name>-<version>-<release>.<arch>.rpm`); the deb sibling uses
  `aitasks_${VERSION}_all.deb`.

### 3. Add `test-rpm` job matrix

```yaml
  test-rpm:
    needs: build-rpm
    strategy:
      fail-fast: false
      matrix:
        distro: [fedora:41, fedora:42, rockylinux:9]
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
          ait --help 2>&1 | head -10 || true
          # Shim should report "No ait project found" in an empty dir
          cd /tmp
          ait some-command 2>&1 | grep -i "No ait project" || \
            (echo "Shim did not emit expected no-project message"; exit 1)

      - name: Uninstall
        run: |
          dnf remove -y aitasks
          test ! -e /usr/bin/ait
```

**Matrix versions (verification-time refresh):** original plan used
`fedora:40, fedora:41, rockylinux:9`. Bumped to `fedora:41, fedora:42,
rockylinux:9` because Fedora 40 reached EOL ~Nov 2025 and the official
`fedora:40` Docker tag will not receive security updates. Both
`fedora:41` and `fedora:42` are currently supported releases (per
Fedora's N + N-1 policy as of 2026-05-04). `rockylinux:9` retained
because RHEL 9 is supported until 2032 and is the closest enterprise
proxy. Implementer should sanity-check current support state at
implementation time and bump again if Fedora 41 has rolled off.

### 4. Validate locally

- Build:
  ```bash
  VERSION=0.17.0 nfpm package \
    --packager rpm \
    --config packaging/nfpm/nfpm.yaml \
    --target /tmp/ait.rpm
  ```
  (Use `docker run --rm -v "$PWD:/tmp/src" -w /tmp/src goreleaser/nfpm:latest
  package …` if nfpm not installed natively, mirroring t623_4 approach.)
- Inspect:
  - `rpm -qpl /tmp/ait.rpm` lists only `/usr/bin/ait`.
  - `rpm -qpR /tmp/ait.rpm` shows the expected deps with rpm-style pins.
  - `rpm -qpi /tmp/ait.rpm` shows `Group: Development/Tools` and the
    description.
  - `rpmlint /tmp/ait.rpm` — errors zero; warnings triaged.
- Container round-trip on `fedora:42`:
  ```bash
  docker run --rm -v /tmp:/host fedora:42 bash -c \
    "dnf install -y /host/ait.rpm && /usr/bin/ait some-command 2>&1 | grep -i 'No ait project' && dnf remove -y aitasks"
  ```
- Lint workflow YAML: `actionlint .github/workflows/release-packaging.yml`
  clean.

## Verification Checklist

- [ ] `packaging/nfpm/nfpm.yaml` `overrides.rpm` block present alongside
      `overrides.deb`.
- [ ] Local nfpm build produces a valid `.rpm` with `ait` shim at
      `/usr/bin/ait`.
- [ ] `rpm -qpR` shows rpm-style version pins (`bash >= 4.0`, etc.).
- [ ] `rpmlint` errors zero.
- [ ] CI matrix passes on fedora:41, fedora:42, rockylinux:9 after
      tagging a prerelease.
- [ ] Manual test on a Fedora VM/container: download `.rpm` from
      release, `sudo dnf install ./aitasks-*.rpm`, `ait setup` works in
      a fresh project.
- [ ] After `dnf remove aitasks`, `/usr/bin/ait` is gone.

## Step 9: Post-Implementation

After review and approval, the standard archival flow applies:

- Code commit using `feature: <description> (t623_5)` format.
- Plan-file commit using `./ait git`.
- Run `./.aitask-scripts/aitask_archive.sh 623_5` to mark Done, move
  task and plan into archived/, release the lock, and commit. Push
  with `./ait git push`.

## Final Implementation Notes

- **Actual work done:**
  - Extended `packaging/nfpm/nfpm.yaml` with `overrides.rpm` block
    (8 deps with rpm-style version pins, 2 recommends).
  - Added a top-level `rpm:` block carrying `group: Development/Tools`
    (see Deviations).
  - Reused the existing `scripts.postinstall: ./packaging/nfpm/postinstall.sh`
    — nfpm dispatches it to the rpm `%post` scriptlet automatically.
  - Appended `build-rpm` and `test-rpm` jobs to
    `.github/workflows/release-packaging.yml`. `test-rpm` matrix covers
    `fedora:41`, `fedora:42`, `rockylinux:9` with `fail-fast: false`.
  - Added a conditional EPEL-enablement step in `test-rpm` for
    Rocky/RHEL/Alma matrix entries (see Deviations).
  - Cleaned shellcheck-via-actionlint warnings on `build-deb` and
    `build-rpm` (redundant `VERSION="${VERSION}"` prefix removed,
    `--target` argument quoted) — symmetric cleanup so the new rpm
    job and the existing deb job stay consistent.

- **Deviations from plan:**
  - `group: Development/Tools` could NOT live inside `overrides.rpm` —
    nfpm rejects it with `field group not found in type
    nfpm.Overridables`. Moved to a top-level `rpm:` block (the
    rpm-only extensions dictionary). Verified via `rpm -qpi` that the
    built package shows `Group: Development/Tools`.
  - **Added EPEL-enablement step** in `test-rpm` that the original
    plan did not anticipate. Rocky Linux 9 base repos do not ship
    `fzf`, so the install fails on `rockylinux:9` without EPEL
    enabled. Step is gated by `if: contains(matrix.distro, 'rocky') ||
    contains(matrix.distro, 'almalinux') || contains(matrix.distro,
    'rhel')` so it does not run on Fedora (which has fzf in main
    repos). End-users on Rocky/RHEL/Alma will need EPEL too — see
    Notes for sibling tasks.
  - **Pre-existing shellcheck warning cleanup on `build-deb`** —
    out-of-strict-scope but symmetric with the new rpm fix and a
    one-character-per-line change. Documented under Upstream defects
    identified in case scope-discipline preferred isolating it.

- **Issues encountered:**
  - First nfpm build failed with `field group not found in type
    nfpm.Overridables` — fixed by relocating `group:` to top-level
    `rpm:` block (Deviations).
  - First `rockylinux:9` round-trip failed with `nothing provides fzf
    needed by aitasks-0.17.0-1.noarch` — fixed by adding the EPEL
    enablement step (Deviations).
  - No issues on `fedora:41` or `fedora:42` round-trip — install,
    shim invocation (`No ait project` message), and uninstall all
    succeed.

- **Key decisions:**
  - `group:` placement at top-level `rpm:` rather than inside
    `overrides.rpm:` — schema-required, not optional.
  - EPEL enablement scoped to Rocky/RHEL/Alma matrix entries via
    `contains(matrix.distro, ...)` rather than running unconditionally
    on Fedora — keeps the Fedora install path closer to a vanilla
    end-user experience and shaves a few seconds off the matrix
    entry that does not need it.
  - EPEL install uses fallback chain: `dnf install -y epel-release ||
    dnf install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm` —
    handles both RHEL (where `epel-release` requires the
    codeready-builder repo) and Rocky/Alma (where it ships in
    `extras`).
  - `Recommends: gh, glab` (separate entries) rather than the
    boolean `(gh or glab)` syntax — same trade-off as t623_4 deb,
    nfpm does not emit boolean recommends; functionally equivalent
    for end-users.

- **Upstream defects identified:**
  - `.github/workflows/release-packaging.yml:130` (pre-fix line
    number; from t623_4) — `VERSION="${VERSION}" nfpm package …
    --target aitasks_${VERSION}_all.deb` had three pre-existing
    shellcheck-via-actionlint warnings (SC2086 unquoted, SC2097
    forked-process assignment, SC2098 expansion-vs-assignment). I
    cleaned this in the same commit because it is the same pattern
    as the new build-rpm job and a non-cleanup would have left the
    workflow asymmetrically warning. If a stricter scope was wanted,
    the deb-side fix could have been deferred to a follow-up bug
    aitask, but inlining it here was strictly less code than two
    commits.

- **Notes for sibling tasks:**
  - **t623_6 (installation methods documentation):** must mention
    that Rocky/RHEL/AlmaLinux users need EPEL enabled before
    `dnf install ./aitasks-*.rpm`. Suggested wording: "On Rocky,
    AlmaLinux, or RHEL, first enable EPEL: `sudo dnf install -y
    epel-release` (or follow your distro's EPEL setup guide)."
    Fedora users do not need this. Also document the asset-URL
    pattern: `https://github.com/beyondeye/aitasks/releases/download/v<X.Y.Z>/aitasks-<X.Y.Z>-1.noarch.rpm`.
  - **Matrix versions:** as of 2026-05-04 the test-rpm matrix uses
    `fedora:41, fedora:42, rockylinux:9`. When Fedora 43+ becomes
    standard, bump the matrix accordingly — keep two consecutive
    Fedora versions plus rockylinux:9 as the enterprise proxy.
  - **postinst convention:** unchanged — `packaging/nfpm/postinstall.sh`
    works as-is for both deb and rpm packagers.
  - **Version pin on nfpm-action:** kept `@v1` major-version pin in
    sync with `build-deb`. Future bumps should be coordinated.
