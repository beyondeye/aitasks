---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: []
created_at: 2026-06-04 11:04
updated_at: 2026-06-04 11:04
---

## Problem

Every fresh install / upgrade leaves an untracked `packaging/` directory
(`aur/`, `homebrew/`, `nfpm/`, `shim/`) in the consumer project. It is
framework-release tooling that has no place in a consumer repo, and it is never
cleaned up.

## Root cause (investigated)

- The release tarball (`.github/workflows/release.yml:87`) bundles the whole
  `packaging/` dir. It is shipped only because the installer needs one file —
  `packaging/shim/ait`, the global launcher shim.
- `install.sh:919` extracts the entire tarball, then explicitly cleans up the
  other transient members (`CHANGELOG.md` `:922`, `VERSION` `:924`, `seed/`
  `:981`, and the skill-staging dirs). **`packaging/` has no cleanup**, so it is
  left behind. It is also not in the commit list (`check_paths`,
  `aitask_setup.sh:2421`), so it sits as an untracked leftover.
- The shim that actually runs is **global and project-agnostic**:
  `SHIM_DIR="$HOME/.local/bin"` (`aitask_setup.sh:9`); the shim
  (`packaging/shim/ait`) walks up from `$PWD` to find a project-local `./ait` and
  `exec`s it. The in-project `packaging/shim/ait` is **only a source file** that
  `install_global_shim` (`aitask_setup.sh:807`) copies from — it has no runtime
  purpose once `~/.local/bin/ait` exists.
- The only thing currently keeping it "load-bearing": `install_global_shim` is
  called on every `ait setup` (`:3080`) and re-copies from the in-project
  `packaging/shim/ait`, hard-failing (`die`, `:813` → `:78` `exit 1`) if the
  source is missing.

## Scope of this task (option C — minimal, no packaging-pipeline changes)

**Do NOT** modify `packaging/` contents, the `release.yml` tarball file list,
`packaging/nfpm/nfpm.yaml`, or relocate the shim. The tarball keeps shipping
`packaging/` as-is. We only (a) make the shim install resilient and (b) delete
the extracted `packaging/` from the installed project after the shim is
consumed.

## Fix

1. **Make `install_global_shim` tolerant of a missing in-project shim source**
   (`aitask_setup.sh:807-823`). Current logic `die`s when
   `$SCRIPT_DIR/../packaging/shim/ait` is absent. Change to: if the source file
   is missing **and** `$SHIM_DIR/ait` already exists, skip (info, not die);
   only treat a missing source as fatal on a genuine first-time install where
   no global shim is present yet. (Keep refreshing the copy when the source is
   present.) This is **required** so re-runs don't break after step 2 removes
   the source — including the post-install `ait setup` the installer tells the
   user to run, which calls `install_global_shim` at `:3080`.

2. **Delete `packaging/` after the shim is consumed** in `install.sh`. The shim
   is consumed at `install.sh:990` (`install_global_shim` via the sourced
   setup). Add `rm -rf "$INSTALL_DIR/packaging"` after that point, mirroring the
   existing `rm -rf "$INSTALL_DIR/seed"` (`:981`) cleanup pattern.

## Blast-radius guard (important)

The `aitasks` framework repo is itself an aitasks project, and its `packaging/`
is **git-tracked source**. `ait upgrade` runs `install.sh` over the working
tree — an unguarded `rm -rf packaging` would delete the framework's own tracked
build tooling. Guard the deletion so it only removes an **untracked** copy:
e.g. skip if `git -C "$INSTALL_DIR" ls-files --error-unmatch packaging >/dev/null
2>&1` succeeds (packaging is tracked → this is the framework source repo, leave
it). `ait setup` itself does not delete (only `install.sh` does), so plain
`ait setup` in the framework repo is already safe — but `ait upgrade` is not
without this guard.

## Acceptance criteria

- A fresh `install.sh` / `ait upgrade` into a consumer project leaves **no**
  `packaging/` directory.
- The post-install `ait setup` (and any later `ait setup` re-run) **does not
  die** when the in-project shim source is gone but `~/.local/bin/ait` already
  exists.
- A genuine first-time install with a truly missing shim source still errors
  (no silent no-op that leaves the user without a global shim).
- Running `ait upgrade` in the `aitasks` framework repo does **not** delete its
  tracked `packaging/`.

## Tests

Add/extend a setup/install test (see `tests/`) asserting: (a) no `packaging/`
leftover after a simulated install, (b) `install_global_shim` succeeds (skips)
when the source is absent but the global shim exists, (c) the tracked-packaging
guard prevents deletion. Run `shellcheck .aitask-scripts/aitask_setup.sh` and
the install.sh lint.

## Notes / required reading

- Per CLAUDE.md, read `aidocs/framework/aitasks_extension_points.md` (install
  flow) and `aidocs/framework/shell_conventions.md` before editing
  `install.sh` / `aitask_setup.sh`.
- The `check_paths` lists in `aitask_setup.sh:2421` and
  `install.sh` `commit_installed_files()` are kept in sync but neither
  references `packaging/`, so no commit-list change is needed.
