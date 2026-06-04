---
Task: t938_clean_up_packaging_leftover_after_install.md
Worktree: (none — working on current branch per profile 'fast')
Branch: main
Base branch: main
---

# Plan: Clean up `packaging/` leftover after install (t938)

## Context

Every fresh `install.sh` / `ait upgrade` into a consumer project leaves an
untracked `packaging/` directory (`aur/`, `homebrew/`, `nfpm/`, `shim/`) behind.
It is framework-release tooling with no role in a consumer repo. The release
tarball ships `packaging/` only because the installer needs **one** file —
`packaging/shim/ait`, the source for the global `~/.local/bin/ait` launcher.

`install.sh` already cleans up the other transient tarball members (`CHANGELOG.md`,
`VERSION`, `seed/`) but never removes `packaging/`. This is **option C — minimal**:
no changes to `packaging/` contents, the `release.yml` file list, or the shim
location. We only (1) make the shim install resilient to a missing source, then
(2) delete the extracted `packaging/` after the shim is consumed — guarded so the
framework repo's own *tracked* `packaging/` is never deleted.

Verified during exploration:
- `install_global_shim()` is `.aitask-scripts/aitask_setup.sh:807`. Its body is
  wrapped in `{ … } || { warn … }`, but `die` (`:813`) calls `exit 1`, which is
  **not** caught by `||` (brace group, not subshell) — so a missing source still
  hard-aborts. It is called on every `ait setup` (`:3080`) **and** by `install.sh`
  (`:990`) via the sourced setup.
- `install.sh:990` calls `install_global_shim` right before `commit_installed_files`.
  `seed/` is removed at `:981` with `rm -rf "$INSTALL_DIR/seed"` — the pattern to mirror.
- `install.sh` ends with `main "$@"` (`:1015`) and has **no** source-only guard;
  `aitask_setup.sh:3120` has the canonical guard
  `[[ "${1:-}" == "--source-only" ]] && return 0 2>/dev/null || true`.
- `ait upgrade` runs `bash install.sh --force --dir "$AIT_DIR"` over the working
  tree (`aitask_upgrade.sh:127`) — this is why the framework repo needs the
  tracked-guard.
- `check_paths` / commit lists do **not** reference `packaging/`, so no commit-list
  change is needed.

## Change 1 — Make `install_global_shim` tolerant of a missing shim source

**File:** `.aitask-scripts/aitask_setup.sh` (`install_global_shim`, ~`:807-823`)

Replace the unconditional `[[ -f "$shim_src" ]] || die …` with a three-way branch:
the copy still refreshes when the source is present; a missing source is a **skip
(info, not die)** when `$SHIM_DIR/ait` already exists; a missing source is still
**fatal** on a genuine first-time install with no global shim yet.

```bash
install_global_shim() {
    # Non-blocking: if anything fails, warn and continue
    {
        mkdir -p "$SHIM_DIR"

        local shim_src="$SCRIPT_DIR/../packaging/shim/ait"
        if [[ ! -f "$shim_src" ]]; then
            # The in-project shim source is shipped only to seed the global
            # launcher. install.sh deletes packaging/ after the first consume,
            # so on any later run (e.g. the post-install `ait setup`) the source
            # is gone but the global shim already exists — that is the steady
            # state, not an error. Only a true first-time install with no global
            # shim yet is fatal.
            if [[ -f "$SHIM_DIR/ait" ]]; then
                info "Shim source absent; global shim already present at $SHIM_DIR/ait — skipping refresh."
                ensure_path_in_profile "$SHIM_DIR"
                return 0
            fi
            die "Cannot locate shim source ($shim_src)"
        fi
        cp "$shim_src" "$SHIM_DIR/ait"

        chmod +x "$SHIM_DIR/ait"

        success "Global shim installed at $SHIM_DIR/ait"
        ensure_path_in_profile "$SHIM_DIR"
    } || {
        warn "Could not install global shim at $SHIM_DIR/ait (non-fatal)"
    }
}
```

`return 0` inside the `{ … }` brace group returns from the function (not a
subshell), which is the intended skip. `ensure_path_in_profile` is idempotent
(`aitask_setup.sh:780` — early-returns if PATH already has the dir / profile
already has a `.local/bin` entry), so calling it on the skip path is safe and
keeps PATH correct if the shim pre-exists but PATH was never configured.

## Change 2 — Delete the extracted `packaging/` after the shim is consumed

**File:** `install.sh`

(a) Add a guarded cleanup function near the other helpers (just before `main()`):

```bash
# Remove the framework-release packaging/ tooling left behind after the shim is
# consumed. The release tarball bundles packaging/ only so install_global_shim
# can copy packaging/shim/ait; nothing under it has a runtime role in a consumer
# project. Mirrors the `rm -rf "$INSTALL_DIR/seed"` cleanup.
#
# Blast-radius guard: the aitasks framework repo IS an aitasks project and tracks
# packaging/ as source. `ait upgrade` runs install.sh over that working tree, so
# an unguarded rm would delete the framework's own build tooling. Only remove an
# UNTRACKED packaging/ (tracked => this is the framework source repo; leave it).
cleanup_packaging_leftover() {
    local dir="$1"
    [[ -d "$dir/packaging" ]] || return 0
    if git -C "$dir" ls-files --error-unmatch packaging >/dev/null 2>&1; then
        info "packaging/ is git-tracked (framework source repo) — leaving it in place."
        return 0
    fi
    rm -rf "$dir/packaging"
}
```

(b) Call it in `main()` immediately after `install_global_shim` (`:990`), before
`commit_installed_files`:

```bash
    install_global_shim

    # Drop the framework-release packaging/ tooling now that the shim is copied.
    cleanup_packaging_leftover "$INSTALL_DIR"

    commit_installed_files
```

(c) Add the source-only guard before `main "$@"` (mirrors `aitask_setup.sh:3120`)
so tests can source `install.sh` to reach `cleanup_packaging_leftover` without
running the installer:

```bash
[[ "${1:-}" == "--source-only" ]] && return 0 2>/dev/null || true

main "$@"
```

Guard semantics: `git ls-files --error-unmatch packaging` exits 0 only if at least
one tracked file lives under `packaging/`. In a consumer project (untracked, or no
git repo at all) it exits non-zero → we delete. In the framework repo it exits 0 →
we skip. Ordering is correct: deletion runs *after* the shim was copied to
`~/.local/bin`.

## Tests

**Extend `tests/test_global_shim.sh`** (Change 1) — add two cases using a subshell
so `die`'s `exit 1` only kills the subshell, with `HOME` and `SCRIPT_DIR`
overridden to a temp dir lacking `packaging/`:
- **Source absent + global shim present** → returns 0 (no die), existing shim
  preserved, info message emitted.
- **Source absent + no global shim** → non-zero exit (still fatal).

**New `tests/test_packaging_cleanup.sh`** (Change 2) — `source install.sh
--source-only` to get `cleanup_packaging_leftover`, then:
- Untracked `packaging/` in a non-git dir → removed.
- Untracked `packaging/` in a git repo where it is not tracked → removed.
- Git-tracked `packaging/` → preserved (framework-repo guard).
- No `packaging/` dir → no-op, rc 0.

Follows existing patterns: `. "$PROJECT_DIR/tests/lib/asserts.sh"`, per-file
`PASS/FAIL/TOTAL` counters + summary (see `test_global_shim.sh`), and the
`assert_dir_exists` / `assert_dir_not_exists` / `assert_exit_*_rc` helpers.

**Lints:**
```bash
shellcheck .aitask-scripts/aitask_setup.sh
bash -n install.sh && shellcheck install.sh   # install.sh lint
bash tests/test_global_shim.sh
bash tests/test_packaging_cleanup.sh
```

## Acceptance criteria (from task)

- Fresh `install.sh` / `ait upgrade` into a consumer project leaves **no** `packaging/`.
- Post-install `ait setup` (and any later re-run) **does not die** when the in-project
  shim source is gone but `~/.local/bin/ait` exists.
- A genuine first-time install with a truly missing shim source still errors.
- `ait upgrade` in the `aitasks` framework repo does **not** delete its tracked `packaging/`.

## Step 9 (Post-Implementation)

Working on the current branch (profile 'fast') — no worktree/merge. After review &
commit: run `verify_build` if configured, then archive via
`./.aitask-scripts/aitask_archive.sh 938` and `./ait git push`.

## Risk

### Code-health risk: low
- Both changes are additive and localized (one function made tolerant, one new
  guarded helper + a source-only guard). No existing call sites change behavior on
  the happy path; the `die`→skip branch only triggers when the source is genuinely
  absent. Blast radius is two install-flow files. · severity: low · → mitigation: None

### Goal-achievement risk: low
- The fix is precisely specified in the task with verified line numbers and a
  mirror pattern (`rm -rf seed`) already in the file. The tracked-vs-untracked
  guard via `git ls-files --error-unmatch` is the standard idiom and is covered by
  a dedicated test. · severity: low · → mitigation: None

No mitigations required (both axes low).
