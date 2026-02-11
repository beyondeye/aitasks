---
Task: t85_5_write_setup_script.md
Parent Task: aitasks/t85_universal_install.md
Sibling Tasks: aitasks/t85/t85_6_*.md, aitasks/t85/t85_7_*.md, etc.
Archived Sibling Plans: aiplans/archived/p85/p85_*_*.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: t85_5 - Write `aitask_setup.sh` Cross-Platform Dependency Installer

## Context

The `aitask_setup.sh` script is the setup command invoked via `ait setup`. It detects the OS/distro, installs required CLI tools (fzf, gh, jq, git), creates a shared Python venv at `~/.aitask/venv/`, installs Python dependencies, and places a global `ait` shim at `~/.local/bin/ait`.

The file already exists as an empty placeholder at `~/Work/aitasks/aiscripts/aitask_setup.sh` (created in t85_1). The `ait` dispatcher already routes `setup` to this script.

## File to Modify

- `~/Work/aitasks/aiscripts/aitask_setup.sh` — replace empty file with full implementation

## Implementation

Write the script with these 8 sections, closely following the task spec:

### 1. Header + constants
- `#!/usr/bin/env bash`, `set -euo pipefail`
- `SCRIPT_DIR`, `VENV_DIR="$HOME/.aitask/venv"`, `SHIM_DIR="$HOME/.local/bin"`, `VERSION_FILE="$SCRIPT_DIR/../VERSION"`, `REPO="beyondeye/aitasks"`

### 2. Color helpers
- `RED`, `GREEN`, `YELLOW`, `BLUE`, `NC`
- Functions: `info()`, `success()`, `warn()`, `die()`

### 3. `detect_os()` function
- `uname -s` → `Darwin` = `"macos"`, `Linux` = check further
- WSL check via `/proc/version`
- Source `/etc/os-release`, map `$ID` (with `$ID_LIKE` fallback):
  - arch/manjaro/endeavouros → `"arch"`
  - ubuntu/debian/pop/linuxmint/elementary → `"debian"`
  - fedora/rhel/centos/rocky/alma → `"fedora"`
  - WSL → `"wsl"` (treated as debian for packages)
  - other → `"linux-unknown"`

### 4. `install_cli_tools()` function
- Check `fzf`, `gh`, `jq`, `git` via `command -v`
- If all present, return early
- Package manager dispatch by OS:
  - `arch` → `sudo pacman -S --needed --noconfirm` (gh = `github-cli`)
  - `debian`/`wsl` → `sudo apt-get install -y -qq` (with `gh` special repo setup)
  - `fedora` → `sudo dnf install -y -q`
  - `macos` → `brew install` (check brew first, also install `bash` + `coreutils`)
  - Also install `python3 python3-venv` on debian/wsl
  - `linux-unknown` → warn and list missing tools

### 5. `setup_python_venv()` function
- Find python3 via `command -v python3 || command -v python`
- Create venv if `$VENV_DIR` doesn't exist
- Upgrade pip, install `textual pyyaml linkify-it-py`

### 6. `install_global_shim()` function
- Non-blocking (wrap in `|| true` patterns)
- Write shim at `$SHIM_DIR/ait` with recursive-find logic
- `chmod +x`, check if `$SHIM_DIR` is in `$PATH`

### 7. `check_latest_version()` function
- Read local version from `$VERSION_FILE`
- Fetch latest via GitHub API (`curl -sS`)
- Compare, print update message if different
- Silently skip on failure

### 8. `main()` function
- Call: `detect_os` → `install_cli_tools` → `setup_python_venv` → `install_global_shim` → `check_latest_version`
- Print summary

## Verification

Run all checks automatically after implementation. Each check prints PASS/FAIL.

### Pre-run checks (no side effects)
1. `bash -n ~/Work/aitasks/aiscripts/aitask_setup.sh` — no syntax errors
2. Verify script is executable: `test -x ~/Work/aitasks/aiscripts/aitask_setup.sh`
3. ShellCheck lint (if available): `shellcheck ~/Work/aitasks/aiscripts/aitask_setup.sh` — no errors (warnings OK)

### Run setup
4. `cd ~/Work/aitasks && ./ait setup` — exits 0 on Arch Linux

### Post-run verification
5. **Venv exists:** `test -d ~/.aitask/venv`
6. **Venv pip works:** `~/.aitask/venv/bin/pip --version` exits 0
7. **Python deps installed:** `~/.aitask/venv/bin/python -c "import textual; import yaml; import linkify_it; print('OK')"` prints `OK`
8. **Shim exists and is executable:** `test -x ~/.local/bin/ait`
9. **Shim content is correct:** `grep -q '_AIT_SHIM_ACTIVE' ~/.local/bin/ait` — contains recursion guard
10. **Shim content is correct:** `grep -q 'aiscripts' ~/.local/bin/ait` — contains aiscripts directory check
11. **Global shim resolves project:** `cd ~/Work/aitasks/aiscripts && ~/.local/bin/ait --version` — prints version string
12. **CLI tools present:** `command -v fzf && command -v gh && command -v jq && command -v git` — all found

### Idempotency check
13. Run `cd ~/Work/aitasks && ./ait setup` a second time — exits 0 with "already installed" messages, no errors

### Function isolation tests (source the script and call functions directly)
14. Source and test `detect_os`:
    ```bash
    (source ~/Work/aitasks/aiscripts/aitask_setup.sh --source-only 2>/dev/null; detect_os; echo "OS=$OS")
    ```
    — prints a known OS value (arch/debian/fedora/macos/wsl/linux-unknown)

Note: Add a `--source-only` guard at the bottom of the script (`[[ "${1:-}" == "--source-only" ]] && return 0`) to enable sourcing for testing without running main.

## Final Implementation Notes
- **Actual work done:** Created `aitask_setup.sh` (295 lines) at `~/Work/aitasks/aiscripts/`. Implements all 8 sections from the task spec: OS detection (arch/debian/fedora/macos/wsl), CLI tool installation with per-distro package manager dispatch, Python venv creation at `~/.aitask/venv/`, global shim at `~/.local/bin/ait`, and GitHub version check. Added `--source-only` guard for test isolation.
- **Deviations from plan:** None — implementation closely follows the task spec.
- **Issues encountered:** None. All 14 verification checks passed on first run (Arch Linux). ShellCheck skipped (not installed on test system).
- **Key decisions:** Used `|| true` pattern wrapping the entire `install_global_shim` body in a compound command `{ ... } || { ... }` for non-blocking behavior. Used `sed` for extracting `tag_name` from GitHub API JSON instead of requiring `jq` (since `jq` might not be installed yet during first run). Added `--source-only` flag at script bottom for function isolation testing.
- **Notes for sibling tasks:** The shared venv is at `~/.aitask/venv/` with Python 3.14. t85_6 (update board for shared venv) should update `aitask_board.sh` to use `$HOME/.aitask/venv/bin/python` instead of bare `python3`. The global shim checks for both `ait` (executable) AND `aiscripts/` (directory) in parent directories. t85_7 (install.sh) should invoke `ait setup` as the final step of the curl bootstrap.

## Post-Implementation (Step 9)

Archive child task and plan, update parent's `children_to_implement`.
