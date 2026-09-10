---
Task: t1772_install_sh_deletes_project_changelog_on_every_upgrade.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1772 — Stop `install.sh` destroying the project's root `CHANGELOG.md`

## Context

`install.sh` runs on every `ait upgrade` (via `aitask_upgrade.sh:152`,
`install.sh --force --dir "$AIT_DIR"`) and on every fresh install. Two adjacent
lines in `main()` destroy a project-owned file:

- `install.sh:1359` — `tar -xzf "$tarball_path" -C "$INSTALL_DIR"` extracts the
  **framework's** `CHANGELOG.md` over the project's own (the release tarball
  carries it at the root — `.github/workflows/release.yml:87-97`).
- `install.sh:1362` — `rm -f "$INSTALL_DIR/CHANGELOG.md"` then deletes the result.

The file is written and maintained by the framework's *own* tooling
(`aitask_changelog.sh`, the `aitask-changelog` skill), and is tracked in consumer
projects — so the loss surfaces as an unstaged ` D CHANGELOG.md` that blocks the
merge broker's clean-tree check. Observed downstream on 2026-09-09 after
upgrading to v0.35.0 (262 lines / 29 KB lost from the working tree).

`install.sh:1364` — `rm -f "$INSTALL_DIR/VERSION"` — is the same bug class,
currently unconditional and undocumented, and must be settled in the same change.

**Intended outcome:** a project's root `CHANGELOG.md` (and root `VERSION`)
survives install and upgrade byte-identical, while the framework's own tarball
copy is still not left behind, and `show_upgrade_changelog` still displays the
framework changelog.

## Approach chosen (and one rejected)

**Rejected — `tar --exclude`.** Measured on this box: both GNU tar 1.35 and
bsdtar 3.8.9 treat `--exclude=NAME` as **non-anchored**, so `--exclude=VERSION`
would also drop `.aitask-scripts/VERSION` — the file the whole version-detection
path depends on (`install.sh:1095,1257`). Neither tar has a portable anchoring
flag (`--anchored` is GNU-only). Disqualified.

**Chosen — stash-and-restore around the extraction**, mirroring the shape of the
existing `cleanup_packaging_leftover()` guard (`install.sh:1325-1331`): the
installer only removes a root file it can prove the framework owns.

## Changes

### 1. `install.sh` — `main()`, replacing lines 1358-1364

Probe **before** extraction (the discriminator disappears once the tarball
lands), stash, extract, restore:

```bash
    # The release tarball carries a root CHANGELOG.md purely so
    # show_upgrade_changelog can display the framework changelog before an
    # upgrade — and that function extracts its own copy into a private temp
    # dir (:1003-1008), never reading INSTALL_DIR. A consumer project owns the
    # root CHANGELOG.md at that path (`ait changelog` writes it), so the
    # extraction must not clobber it and the cleanup must not delete it (t1772).
    local preserve_dir="$tmpdir/preserve"
    mkdir -p "$preserve_dir"

    # A root VERSION is a pre-v0.3.0 framework artefact ONLY when this is an
    # existing install whose version has not yet migrated to
    # .aitask-scripts/VERSION. Probed here because extraction creates that
    # file. Anything else at that path belongs to the project.
    local legacy_root_version=false
    if [[ -f "$INSTALL_DIR/VERSION" && -d "$INSTALL_DIR/.aitask-scripts" \
          && ! -f "$INSTALL_DIR/.aitask-scripts/VERSION" ]]; then
        legacy_root_version=true
    fi

    local f
    for f in CHANGELOG.md VERSION; do
        if [[ -f "$INSTALL_DIR/$f" ]]; then
            cp -p "$INSTALL_DIR/$f" "$preserve_dir/$f"
        fi
    done

    info "Extracting to $INSTALL_DIR..."
    tar -xzf "$tarball_path" -C "$INSTALL_DIR"

    # Put back what the project owned; remove what only the tarball supplied.
    for f in CHANGELOG.md VERSION; do
        if [[ -f "$preserve_dir/$f" ]]; then
            cp -p "$preserve_dir/$f" "$INSTALL_DIR/$f"
        else
            rm -f "$INSTALL_DIR/$f"
        fi
    done
    if [[ "$legacy_root_version" == true ]]; then
        rm -f "$INSTALL_DIR/VERSION"     # migrated to .aitask-scripts/VERSION
    fi
```

Explicit `if` blocks, not `[[ … ]] && continue` — under `set -euo pipefail` a
failing test in an `&&` list inside a loop body is an errexit trap.

### 2. `install.sh:991-1001` — flip the version-precedence in `show_upgrade_changelog`

Required *by* change 1, not scope creep: today root `VERSION` is read **first**,
so a project that owns one already has its framework version misread. Once that
file is preserved forever, the misread becomes permanent and every subsequent
upgrade computes the wrong version range. Swap the two branches
(`.aitask-scripts/VERSION` first, root `VERSION` as the pre-v0.3.0 fallback),
keeping the `return 0` and its t1414 comment untouched. This is the only reader
of root `VERSION` in the file.

### 3. New test — `tests/test_install_changelog_preservation.sh`

Follows `tests/test_install_upgrade_changelog.sh`: hermetic, zero network
(`--local-tarball`), `HOME`/`SHIM_DIR` redirected into the scratch dir, real
`bash install.sh --force --dir <scratch>` runs (which is also what
`aidocs/framework/aitasks_extension_points.md` §"Test the full install flow"
requires). Sources `tests/lib/asserts.sh`; all assertions at top level, so no
`assert_counters_init` opt-in is needed. Fixture tarball packs
`.aitask-scripts/ ait packaging/ seed/ CHANGELOG.md`, with the framework
`CHANGELOG.md` given content distinct from the project's so a *replacement* is
distinguishable from a *deletion*.

| # | Case | Flow | Discriminates? |
|---|---|---|---|
| 1 | **Upgrade** (`.aitask-scripts/VERSION` seeded) over an install owning a root `CHANGELOG.md` → survives, `cmp -s` byte-identical against a pre-run copy | e2e | **yes** (today: deleted) |
| 2 | **First-time forced install** — target has a project `CHANGELOG.md` but **no `.aitask-scripts/` at all** → survives byte-identical | e2e | **yes** (today: deleted) |
| 3 | Install into a project with no `CHANGELOG.md` → no root `CHANGELOG.md` left behind | e2e | pin |
| 4 | Project root `VERSION` + `.aitask-scripts/VERSION` present → root `VERSION` survives byte-identical | e2e | **yes** (today: deleted) |
| 5 | Legacy pre-v0.3.0 (`.aitask-scripts/` present, **no** `.aitask-scripts/VERSION`) → root `VERSION` still removed | e2e | pin |
| 6 | `show_upgrade_changelog` with a **conflicting project root `VERSION`=7.7.7**, `.aitask-scripts/VERSION`=1.0.0, tarball 2.0.0 → the framework transition is still displayed correctly | helper | **yes** (see below) |
| 7 | Same helper, root `VERSION`=1.0.0 but `.aitask-scripts/VERSION`=9.9.9 == tarball 9.9.9 → no `Upgrading:` line (early return still reached) | helper | pin |

Cases 1 and 2 are separate deliberately: they take different branches of
`check_existing_install` (`install.sh:110-115` vs the fresh path) and different
`show_upgrade_changelog` exits, so neither covers the other.

**Case 6 is the primary discriminator for change 2**, and it pins the *positive*
output rather than an absence. Pre-fix, `current_version` reads `7.7.7`; the
slicing loop (`install.sh:1026-1039`) then never meets a `## v7.7.7` heading, so
it never breaks and dumps every section. Four assertions, each failing pre-fix:

- contains `Upgrading: v1.0.0 → v2.0.0` (pre-fix: `v7.7.7 → v2.0.0`)
- does **not** contain `7.7.7` — the project's own version is never read as the
  framework's
- contains the `## v2.0.0` body (`- new thing`) — the display still works
- does **not** contain the `## v1.0.0` body (`- old thing`) — it still stops at
  the installed version (pre-fix it runs past it)

**Vacuity guard on every e2e case (1-5):** assert `rc == 0` **and**
`.aitask-scripts/VERSION` exists in the target before believing any byte
comparison. A silent installer abort (the exact t1414 failure mode, which lives
in the function change 2 edits) would otherwise leave the project's
`CHANGELOG.md` untouched and make cases 1, 2 and 4 pass for the wrong reason.

`cmp -s` rather than a checksum tool — POSIX, no `sha256sum`/`shasum`
portability split, and it is a stricter byte-identity check than the AC asks for.
The framework's tarball `CHANGELOG.md` carries content distinct from the
project's, so a *replacement* fails the comparison just as a *deletion* does.

## Documentation

No website page claims the current behaviour (`grep` of
`website/content/docs/` finds only `aitask-changelog` / release-flow mentions),
and `releases.md:96` already documents `CHANGELOG.md` being *in* the tarball,
which stays true. No doc change required; the rationale lives in the code
comments above. (`docs_updated` is not in this task's active gate set.)

## Verification

```bash
bash tests/test_install_changelog_preservation.sh   # new — must FAIL pre-fix
bash tests/test_install_upgrade_changelog.sh        # precedence-flip neighbour
bash tests/test_install_create_data_dirs.sh
bash tests/test_install_tarball_download.sh
bash tests/test_install_merge.sh
shellcheck install.sh
```

Red-proof sequencing: write the test first, run it against unmodified
`install.sh` and confirm cases **1, 2, 4 and 6** fail (and that 3, 5, 7 pass
already); then apply changes 1-2 and confirm all seven pass. Test and fix land
in the same commit.

## Risk

### Code-health risk: medium
- `install.sh` is the single load-bearing path for every install and upgrade; a
  fault here bricks upgrades for all consumers, and it runs under
  `set -euo pipefail` where a new `cp` introduces a new abort site ·
  severity: medium · → mitigation: inline post-phase `install-suite-regression`
- Version-precedence flip changes an existing, tested code path (t1414's
  `return 0` hardening sits in the same block), and a regression there is a
  *silent installer abort* rather than a visible failure · severity: medium ·
  → mitigation: inline post-phase `install-suite-regression`, plus the
  vacuity guard on test cases 1-5 (rc + extraction asserted, so an abort can
  never read as a preserved file)

### Goal-achievement risk: low
- The `VERSION` disposition is a judgement call the task left open; the chosen
  legacy-probe could mis-classify an exotic layout (root `VERSION` + populated
  `.aitask-scripts/` with no `VERSION` file, but project-owned) and delete it ·
  severity: low · → mitigation: inline post-phase `install-suite-regression`
  (case 4 pins the intended classification; the mis-classified shape is
  indistinguishable from a genuine pre-v0.3.0 install by construction)

### Post-phase (risk mitigations)

**`install-suite-regression`** — after the code change, run every existing
install-flow test file (`test_install_upgrade_changelog.sh`,
`test_install_create_data_dirs.sh`, `test_install_tarball_download.sh`,
`test_install_merge.sh`) plus `shellcheck install.sh`, and report each verdict
explicitly rather than only the new test's. These four already drive the real
`main()` end-to-end, so they are the cheapest available proof that the new
stash/restore block did not break extraction or the installer's exit status.

## Step 9

Post-implementation follows task-workflow Step 9 (commit, merge, archive t1772).
