---
Task: t85_7_write_install_script.md
Parent Task: aitasks/t85_universal_install.md
Sibling Tasks: aitasks/t85/t85_8_*.md, aitasks/t85/t85_9_*.md, etc.
Archived Sibling Plans: aiplans/archived/p85/p85_*_*.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: t85_7 - Write `install.sh` Curl Bootstrap Script

## Context

The `install.sh` script is the curl-friendly bootstrap that users run to install aitasks into their project. It downloads the latest release tarball from GitHub, extracts framework files, installs Claude Code skills, and runs `ait setup`. The file already exists as an empty placeholder at `~/Work/aitasks/install.sh`.

**Usage**: `curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh | bash`

## File to Modify

- `~/Work/aitasks/install.sh` — replace empty file with full implementation

## Reference Files

- `~/Work/aitasks/aiscripts/aitask_setup.sh` — color helpers pattern, same `[ait]` prefix
- `~/Work/aitasks/ait` — dispatcher structure, `set -euo pipefail` pattern

## Implementation

Write the script with these sections, following the task spec closely:

### 1. Header + Constants
- `#!/usr/bin/env bash`, `set -euo pipefail`
- `REPO="beyondeye/aitasks"`
- `INSTALL_DIR` defaulting to `.` (current directory)
- `FORCE=false`

### 2. Color Helpers
Same pattern as `aitask_setup.sh`

### 3. Argument Parsing
Parse `--force`, `--dir PATH`, `--local-tarball PATH`, `--help`

### 4. Prerequisites Check
Verify `tar` and `curl`/`wget`

### 5. Safety Check
Warn and exit if `ait` or `aiscripts/` exist unless `--force`

### 6. Interactive Prompt
`[[ -t 0 ]]` detection, skip when piped

### 7. Download
GitHub API for latest release, curl/wget fallback, temp dir with trap

### 8. Extract
`tar -xzf` into `$INSTALL_DIR`

### 9. Install Skills
Copy from `skills/` to `.claude/skills/`, remove staging dir

### 10. Create Data Directories
`aitasks/metadata/`, `aitasks/archived/`, `aiplans/archived/`

### 11. Set Permissions
`chmod +x` on `ait` and `aiscripts/*.sh`

### 12. Run Setup
Execute `./ait setup`

### 13. Print Summary

## Verification

19 automated tests covering: syntax, shellcheck, functional install, permissions, skills, data directories, safety/idempotency, --force, --dir, edge cases.

## Final Implementation Notes
- **Actual work done:** Created `install.sh` (242 lines) at `~/Work/aitasks/`. Implements all 13 sections from the plan: argument parsing (--force, --dir, --local-tarball, --help), prerequisites check (tar, curl/wget), safety check for existing installations, interactive prompt with pipe detection, GitHub API release download with curl/wget fallback, tarball extraction, skills installation from `skills/` to `.claude/skills/`, data directory creation, permission setting, and `ait setup` invocation. Added `--local-tarball` flag for CI-friendly testing without network access.
- **Deviations from plan:** Added `--local-tarball PATH` flag (not in original task spec) for offline/CI testing. Added `--help` flag with usage text. Added shellcheck disable comment for the intentional SC2064 trap expansion.
- **Issues encountered:** None. All 18 verification tests passed on first implementation. ShellCheck initially flagged SC2064 (trap variable expansion) which was addressed with a disable comment since expanding at definition time is intentional.
- **Key decisions:** Used `sed` for extracting `browser_download_url` from GitHub API JSON (no `jq` dependency, same pattern as `aitask_setup.sh`). Unknown arguments cause immediate `die()` rather than being silently ignored. INSTALL_DIR is resolved to absolute path early via `cd && pwd`.
- **Notes for sibling tasks:** The `--local-tarball` flag is useful for t85_8 (GitHub Actions release workflow) to test the install flow in CI. The tarball must contain `ait`, `VERSION`, `aiscripts/`, `skills/` at the top level (no parent directory wrapper). t85_9 (apply changes to tubetime) should note that `install.sh` lives at repo root alongside `ait` and `VERSION`.

## Post-Implementation (Step 9)

Archive child task and plan, update parent's `children_to_implement`.
