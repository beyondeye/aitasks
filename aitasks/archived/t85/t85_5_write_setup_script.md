---
priority: high
effort: high
depends: [t85_1, t85_2]
issue_type: feature
status: Done
labels: [bash, aitasks]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-11 10:00
updated_at: 2026-02-11 13:02
completed_at: 2026-02-11 13:02
---

## Context

This is child task 5 of parent task t85 (Cross-Platform aitask Framework Distribution). The setup script is the cross-platform dependency installer that gets invoked via `ait setup`. It detects the OS/distro, installs CLI tools, creates a shared Python virtual environment, and installs a global shim so users can type `ait` without `./`.

**File to create**: `~/Work/aitasks/aiscripts/aitask_setup.sh`

## What to Do

### Script structure (~250 lines)

The script should have these sections:

#### 1. Header and constants

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$HOME/.aitask/venv"
SHIM_DIR="$HOME/.local/bin"
VERSION_FILE="$SCRIPT_DIR/../VERSION"
REPO="beyondeye/aitasks"
```

#### 2. Color helpers

```bash
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()    { echo -e "${BLUE}[ait]${NC} $1"; }
success() { echo -e "${GREEN}[ait]${NC} $1"; }
warn()    { echo -e "${YELLOW}[ait]${NC} $1"; }
die()     { echo -e "${RED}[ait] Error:${NC} $1" >&2; exit 1; }
```

#### 3. OS detection function `detect_os()`

Uses `uname -s` for primary detection:
- `Darwin` → `"macos"`
- `Linux` → check further

For Linux, check WSL first (`grep -qi microsoft /proc/version 2>/dev/null`), then source `/etc/os-release` and map `$ID` (with `$ID_LIKE` fallback for derivatives):

| ID / ID_LIKE | Result |
|---|---|
| `arch`, `manjaro`, `endeavouros` | `"arch"` |
| `ubuntu`, `debian`, `pop`, `linuxmint`, `elementary` | `"debian"` |
| `fedora`, `rhel`, `centos`, `rocky`, `alma` | `"fedora"` |
| WSL detected | `"wsl"` (treated same as debian for packages) |
| anything else | `"linux-unknown"` |

#### 4. CLI tools installation function `install_cli_tools()`

Check each tool with `command -v`:
- `fzf`, `gh`, `jq`, `git`

If all present, print "All CLI tools already installed" and return.

Otherwise, install missing tools using the native package manager:

**Package name mapping:**

| Tool | Arch (pacman) | Debian/Ubuntu (apt) | Fedora (dnf) | macOS (brew) |
|------|---------------|---------------------|--------------|--------------|
| fzf | `fzf` | `fzf` | `fzf` | `fzf` |
| gh | `github-cli` | `gh` (needs repo) | `gh` | `gh` |
| jq | `jq` | `jq` | `jq` | `jq` |
| git | `git` | `git` | `git` | `git` |

**Debian/Ubuntu special handling for `gh`:**

GitHub CLI is NOT in default apt repos. Before installing, add the official repo:
```bash
(type -p wget >/dev/null || sudo apt-get install wget -y -qq) \
  && sudo mkdir -p -m 755 /etc/apt/keyrings \
  && wget -qO- https://cli.github.com/packages/githubcli-archive-keyring.gpg \
     | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null \
  && sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
  && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
     | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
  && sudo apt-get update -qq
```

**macOS special handling:**

Check for Homebrew first (`command -v brew`). If not found, `die "Homebrew is required on macOS. Install from https://brew.sh"`.

Also install `bash` (version 5.x) because macOS system bash is v3.2 and the scripts use `declare -A` (bash 4+ associative arrays).

Also install `coreutils` for `gdate` (the scripts use `date -d` which is GNU-specific; macOS BSD `date` doesn't support it). Note: this is a known limitation — scripts would need a `date` wrapper to actually use `gdate` on macOS, but installing coreutils is a prerequisite step.

**On Debian/Ubuntu also install**: `python3`, `python3-venv` (needed for venv creation).

**For unknown distros**: print a warning listing the missing tools and ask user to install manually. Don't die — continue with the rest of setup.

#### 5. Python venv setup function `setup_python_venv()`

- Find python3: try `python3` then `python` via `command -v`
- If not found, die with message
- If `$VENV_DIR` doesn't exist: `mkdir -p "$(dirname "$VENV_DIR")" && "$python_cmd" -m venv "$VENV_DIR"`
- Upgrade pip: `"$VENV_DIR/bin/pip" install --quiet --upgrade pip`
- Install deps: `"$VENV_DIR/bin/pip" install --quiet textual pyyaml linkify-it-py`
- Print success message with venv path

#### 6. Global shim installation function `install_global_shim()`

This must be **non-blocking** — if it fails for any reason, warn and continue.

Wrap the entire function body in a subshell or use `|| true` patterns.

The shim script to write at `$SHIM_DIR/ait`:

```bash
#!/usr/bin/env bash
# Global shim for ait - finds nearest project-local ait dispatcher
if [[ "${_AIT_SHIM_ACTIVE:-}" == "1" ]]; then
    echo "Error: ait dispatcher not found in any parent directory." >&2
    exit 1
fi
export _AIT_SHIM_ACTIVE=1
dir="$PWD"
while [[ "$dir" != "/" ]]; do
    if [[ -x "$dir/ait" && -d "$dir/aiscripts" ]]; then
        exec "$dir/ait" "$@"
    fi
    dir="$(dirname "$dir")"
done
echo "Error: No ait project found in any parent directory of $PWD" >&2
echo "  Install aitasks in a project: curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh | bash" >&2
exit 1
```

After writing:
- `chmod +x "$SHIM_DIR/ait"`
- Check if `$SHIM_DIR` is in `$PATH`. If not, warn with instructions to add it.

The shim checks both `ait` (executable) AND `aiscripts/` (directory) exist — this prevents matching unrelated files named `ait`.

The `_AIT_SHIM_ACTIVE` environment variable prevents infinite recursion if the shim finds itself.

#### 7. Version check function `check_latest_version()`

- Read local version from `$VERSION_FILE`
- Fetch latest from GitHub API: `curl -sS "https://api.github.com/repos/$REPO/releases/latest"` and extract `tag_name`
- Compare: if different, print update available message with install command
- If API call fails (no network, rate limited), silently skip
- This is informational only, never auto-updates

#### 8. Main function

Call all functions in order:
1. `detect_os` → store result
2. `install_cli_tools "$os"`
3. `setup_python_venv`
4. `install_global_shim` (non-blocking)
5. `check_latest_version`
6. Print summary with all paths and versions

### Commit

```bash
cd ~/Work/aitasks
git add aiscripts/aitask_setup.sh
git commit -m "Add cross-platform dependency installer (ait setup)"
```

## Verification

1. `bash -n ~/Work/aitasks/aiscripts/aitask_setup.sh` — no syntax errors
2. On the current system (Arch Linux): `cd ~/Work/aitasks && ./ait setup` installs successfully
3. `~/.aitask/venv/bin/python -c "import textual; import yaml; import linkify_it; print('OK')"` prints OK
4. `ls -la ~/.local/bin/ait` shows the global shim exists and is executable
5. From a subdirectory of the aitasks repo: `ait --version` works via the global shim
