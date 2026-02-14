---
Task: t128_ait_setup_fixes.md
---

## Context

Task t128 addresses three issues with the `ait setup` / install workflow:

1. **CHANGELOG.md and VERSION polluting project root** — The release tarball includes both files, which get extracted into the user's project directory. CHANGELOG.md is purely framework metadata. VERSION is needed at runtime but shouldn't be a top-level file in the user's project.
2. **Undocumented `ait setup` auto-bootstrap** — The global shim now supports `ait setup` in directories without aitasks, auto-downloading and installing the framework. This needs README documentation.
3. **Framework files not git-committed in existing repos** — `setup_git_repo()` returns immediately when a git repo exists, never offering to commit the freshly-installed framework files.

## Plan

### 1. Relocate VERSION to `aiscripts/VERSION` and remove CHANGELOG.md from installs

**install.sh** (4 changes):
- After line 350 (tarball extraction): add `rm -f "$INSTALL_DIR/CHANGELOG.md"` and `mv "$INSTALL_DIR/VERSION" "$INSTALL_DIR/aiscripts/VERSION" 2>/dev/null || true`
- `show_upgrade_changelog()` (line 254): check both `$install_dir/VERSION` and `$install_dir/aiscripts/VERSION` for backward compat during upgrades
- Also handle the edge case where an old VERSION exists at root — clean it up: `rm -f "$INSTALL_DIR/VERSION"` after the move

**ait** dispatcher (2 changes):
- `show_version()` line 10: `"$AIT_DIR/aiscripts/VERSION"` instead of `"$AIT_DIR/VERSION"`
- `check_for_updates()` line 45: same path change

**aiscripts/aitask_setup.sh** (2 changes):
- Line 10: `VERSION_FILE="$SCRIPT_DIR/VERSION"` (was `"$SCRIPT_DIR/../VERSION"`)
- Line 369 (git add in `setup_git_repo`): remove `VERSION` from the list (it's inside `aiscripts/` already)

**aiscripts/aitask_install.sh** (1 change):
- Line 102: read from `"$AIT_DIR/aiscripts/VERSION"` instead of `"$AIT_DIR/VERSION"`

**No changes to release.yml** — VERSION and CHANGELOG.md remain in the tarball (needed by install.sh's `show_upgrade_changelog()` which extracts them to a temp dir).

### 2. Auto-commit framework files in existing git repos

**aiscripts/aitask_setup.sh** — `setup_git_repo()`:
- After the "Git repository already initialized" success message (line 305-306), add a check for untracked framework files using `git ls-files --others --exclude-standard`
- If untracked files found, list them and prompt user (Y/n) to commit
- Use the same git add list as the new-repo path (minus VERSION at root)
- Commit with message "Add aitask framework"

### 3. Document `ait setup` auto-bootstrap in README

**README.md** — two additions:
- **Quick Install section** (after line 87): add a paragraph explaining that if you already have the global `ait` shim (from a previous install on another project), you can just run `ait setup` in any new project directory to auto-download and install the framework
- **`ait setup` section** (around line 183): add a note about the auto-bootstrap behavior when run outside an aitasks project via the global shim

### 4. Post-implementation: Step 9 (archival/merge per aitask-pick workflow)

## Files to modify

| File | Changes |
|------|---------|
| `install.sh` | Remove CHANGELOG.md, move VERSION to aiscripts/, backward compat in show_upgrade_changelog |
| `ait` | Update VERSION path in show_version and check_for_updates |
| `aiscripts/aitask_setup.sh` | Update VERSION_FILE path, add untracked-file check in setup_git_repo, remove VERSION from git add |
| `aiscripts/aitask_install.sh` | Update VERSION path |
| `README.md` | Document ait setup auto-bootstrap |

## Verification

1. Run `bash -n install.sh ait aiscripts/aitask_setup.sh aiscripts/aitask_install.sh` — syntax check all modified scripts
2. Run `./ait --version` — should still show version correctly from new path
3. Verify `aiscripts/VERSION` exists and root `VERSION` doesn't (in the project after changes)
4. Read through README changes for clarity

## Final Implementation Notes
- **Actual work done:** All three issues addressed as planned. Additionally updated `release.yml` (removed VERSION from tarball root since it's now inside aiscripts/), `create_new_release.sh` (VERSION path), and `tests/test_setup_git.sh` (adapted to VERSION relocation and new untracked-file detection).
- **Deviations from plan:** Plan said "no changes to release.yml" but this was revised — VERSION was also removed from the tarball's root-level inclusion (it's already inside `aiscripts/` which is included). This is cleaner than extracting at root then moving.
- **Issues encountered:** Test suite (`tests/test_setup_git.sh`) had pre-existing failures from t127's `-t 0` non-interactive checks. Tests 3 and 5 piped input that was ignored by non-interactive mode. Fixed by rewriting tests to properly test non-interactive auto-accept behavior.
- **Key decisions:** CHANGELOG.md is removed entirely from installs (not relocated). VERSION is moved to `aiscripts/VERSION` in both the repo and installed projects. Backward compat: `install.sh` checks both `VERSION` and `aiscripts/VERSION` during upgrades, and cleans up legacy root VERSION.
