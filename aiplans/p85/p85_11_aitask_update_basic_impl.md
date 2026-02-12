---
Task: t85_11_aitask_update_basic_impl.md
Parent Task: aitasks/t85_universal_install.md
Archived Sibling Plans: aiplans/archived/p85/p85_*_*.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: t85_11 - Basic Update/Upgrade Mechanism

## Context

The aitasks framework currently has no way to update itself. Users must manually `curl | bash -s -- --force` to upgrade. This task adds:
1. A cached, once-daily update check in the `ait` dispatcher
2. A new `ait install [latest|VERSION]` subcommand
3. Changelog display during upgrades in `install.sh`
4. `CHANGELOG.md` included in the release tarball

## Files to Modify/Create

1. **`.github/workflows/release.yml`** — Add CHANGELOG.md to tarball
2. **`aiscripts/aitask_install.sh`** — NEW: `ait install` subcommand
3. **`ait`** — Add update check function + `install` dispatch
4. **`install.sh`** — Add changelog display during `--force` upgrade
5. **`aiscripts/aitask_setup.sh`** — Update version check message (one line)
6. **`README.md`** — Document new command

## Implementation Steps

### Step 1: Add CHANGELOG.md to release tarball

**File:** `.github/workflows/release.yml`

Add `CHANGELOG.md` to the `tar -czf` command (line ~40-45). Simple, zero-risk prerequisite for the changelog display feature.

### Step 2: Create `aiscripts/aitask_install.sh`

New script implementing `ait install [latest|VERSION]`:

- **`resolve_version()`**: If `latest`, query GitHub API for latest release tag_name. If specific version, validate semver format.
- **`download_installer()`**: Download `install.sh` from the target version's git tag (`raw.githubusercontent.com/$REPO/v${version}/install.sh`). This ensures installer compatibility with the release.
- **`main()`**: Resolve version, check if already up-to-date, download installer from target tag, run `bash install.sh --force --dir "$AIT_DIR"`, clear update cache (`~/.aitask/update_check`).

Follows existing script patterns: shebang + strict mode, inline color helpers, help text.

### Step 3: Add update check to `ait` dispatcher

**File:** `ait`

Add `check_for_updates()` function between `show_usage()` and the `case` statement:

- **Cache location:** `~/.aitask/update_check` (global, not per-project)
- **Cache format:** `<unix_timestamp> <latest_version>` (single line)
- **When cache is fresh (<24h):** Read cached version, compare with local VERSION. If different, print update notice synchronously (before `exec`).
- **When cache is stale (>24h) or missing:** Spawn a background subshell that fetches the latest version from GitHub API (5s timeout), writes to cache file. Do NOT print message from background (avoids interleaved output with the subcommand). User sees the notice on the next invocation.
- **Skip check for:** `help`, `--help`, `-h`, `--version`, `-v`, `install`, `setup`

Add `install)` case to the dispatcher, and update `show_usage()`.

### Step 4: Add changelog display to `install.sh`

**File:** `install.sh`

Add `show_upgrade_changelog()` function called after `download_tarball()` and before extraction:

- Only runs when `--force` is true AND existing `VERSION` file exists
- Extracts just `VERSION` and `CHANGELOG.md` from tarball into a temp dir
- Compares versions; skips if same
- Reads CHANGELOG.md line by line, printing all `## vX.Y.Z` sections between the file top and the current version's heading (exclusive)
- Gracefully handles missing CHANGELOG.md (pre-change releases)
- Asks for confirmation (`[[ -t 0 ]]` for pipe detection, default Yes)

### Step 5: Update setup.sh version check message

**File:** `aiscripts/aitask_setup.sh` (line 255)

Change the suggestion from `curl -fsSL ... | bash` to `ait install latest`.

### Step 6: Update README.md

The README was recently reorganized (Table of Contents, sections reordered). Key insertion points:

- **Command reference table** (line ~140): Add `| \`ait install\` | Update aitasks to latest or specific version |`
- **Table of Contents** (line ~111, after `ait setup`): Add `  - [ait install](#ait-install)`
- **Usage examples** (line ~153): Add `ait install` and `ait install 0.2.1` examples
- **Quick Install section** (line ~75-79): Update "Upgrade" to recommend `ait install latest`, keep curl as fallback
- **New `### ait install` section**: Insert after `### ait setup` section (after line ~193), before `### ait create`. Document: usage, arguments (latest/VERSION), options (--help), examples, how it works, and the automatic update check feature

### Step 7: Set permissions

```bash
chmod +x aiscripts/aitask_install.sh
```

## Verification

1. `bash -n ait` and `bash -n aiscripts/aitask_install.sh` — syntax check
2. `shellcheck ait aiscripts/aitask_install.sh install.sh` — lint
3. `./ait --version` — dispatcher still works
4. `./ait help` — shows `install` subcommand
5. `./ait install --help` — shows install usage
6. Test update check: `rm ~/.aitask/update_check && ./ait ls -v 5` — should trigger background check
7. Test cached notice: `echo "0 99.99.99" > ~/.aitask/update_check && ./ait ls -v 5` — should show update notice
8. Test already up to date: `./ait install` with current version — should say "Already up to date"

## Final Implementation Notes
- **Actual work done:** Implemented all 7 steps from the plan. Created `aiscripts/aitask_install.sh` (115 lines) implementing `ait install [latest|VERSION]`. Added `check_for_updates()` to the `ait` dispatcher with background daily GitHub API check and cached results at `~/.aitask/update_check`. Added `show_upgrade_changelog()` to `install.sh` for displaying changelog during `--force` upgrades. Added CHANGELOG.md to release tarball. Updated README.md with full documentation. Also fixed a missing `changelog` subcommand in the `ait` dispatcher.
- **Deviations from plan:** (1) Moved "Checking latest version..." info message out of `resolve_version()` function to avoid stdout capture inside `$()` command substitution — was causing garbled output. (2) Added `changelog)` dispatch in `ait` which was missing from the original dispatcher. (3) Moved `install` to the end of the commands list in `ait help` (after `setup`) per user request.
- **Issues encountered:** Initial version had `info()` messages inside `resolve_version()` going to stdout, which got captured by the `$()` substitution in the caller, causing garbled version strings and download failures. Fixed by moving the message outside the function.
- **Key decisions:** Used background fetch (with `disown`) for stale cache to avoid any latency. `ait install` downloads `install.sh` from the target version's git tag (not from `main`) to ensure compatibility. Version comparison uses string equality, not semver ordering.
- **Notes for sibling tasks:** This is the last child task for t85. The `ait install` command is now available and tested against the live GitHub release (v0.2.0). Future releases will include CHANGELOG.md in the tarball for changelog display during upgrades.

## Post-Implementation (Step 9)

Archive child task and plan, update parent's `children_to_implement`.
