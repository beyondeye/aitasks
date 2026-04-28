---
Task: t695_2_venv_python_upgrade.md
Parent Task: aitasks/t695_install_python_if_sys_python_old.md
Sibling Tasks: aitasks/t695/t695_1_python_resolve_helper.md, aitasks/t695/t695_3_aitask_bin_symlink_path.md, aitasks/t695/t695_4_refactor_python_callers.md
Archived Sibling Plans: aiplans/archived/p695/p695_*_*.md
Worktree: aiwork/t695_2_venv_python_upgrade
Branch: aitask/t695_2_venv_python_upgrade
Base branch: main
---

# Plan — t695_2: venv-Python upgrade flow in setup_python_venv (macOS + Linux)

## Context

Second child of t695. The heart of the fix. After this child lands, every
fresh `ait setup` produces a venv backed by a Python ≥ `AIT_VENV_PYTHON_MIN`
(default 3.11) regardless of how old the system Python is. Linux installs
go strictly to user-scoped paths under `~/.aitask/` — no sudo, no apt/dnf
modifications.

This child does not yet wire up the `~/.aitask/bin/python3` symlink (that's
t695_3) and does not refactor any callers (t695_4). Its scope is contained
to `setup_python_venv()` and supporting helpers in `aitask_setup.sh`.

## Files

- `.aitask-scripts/aitask_setup.sh` — modify `setup_python_venv()` (lines
  435-511 today), add `find_modern_python()` and `install_modern_python()`
  helpers, add `AIT_VENV_PYTHON_MIN` / `AIT_VENV_PYTHON_PREFERRED` constants
  near the top.
- `tests/test_setup_python_install.sh` — NEW. Integration test that runs
  the full `bash install.sh --dir /tmp/scratchXY` → `ait setup` flow per
  the CLAUDE.md "Test the full install flow for setup helpers" rule.

## Implementation Steps

### Step 1 — Add config constants

Near the top of `aitask_setup.sh`, after `VENV_DIR` and other framework
constants:

```bash
AIT_VENV_PYTHON_MIN="${AIT_VENV_PYTHON_MIN:-3.11}"
AIT_VENV_PYTHON_PREFERRED="${AIT_VENV_PYTHON_PREFERRED:-3.13}"
```

### Step 2 — Add `find_modern_python <min_version>`

Place before `check_python_version()`. Searches a known list of locations
for a Python ≥ min_version. Echoes the path or empty.

```bash
find_modern_python() {
  local min="${1:-$AIT_VENV_PYTHON_MIN}"
  local major="${min%%.*}" minor="${min##*.}"
  local cand candidates=(
    "$HOME/.aitask/bin/python3"
    "$HOME/.aitask/python/$AIT_VENV_PYTHON_PREFERRED/bin/python3"
    python3.13 python3.12 python3.11
  )
  for cand in "${candidates[@]}"; do
    local resolved
    resolved="$(command -v "$cand" 2>/dev/null || true)"
    [[ -z "$resolved" || ! -x "$resolved" ]] && continue
    if "$resolved" -c "import sys; sys.exit(0 if sys.version_info >= ($major, $minor) else 1)" 2>/dev/null; then
      echo "$resolved"
      return 0
    fi
  done
  return 0   # echo nothing
}
```

### Step 3 — Add `install_modern_python` (OS-dispatched)

```bash
install_modern_python() {
  case "$OS" in
    macos) _install_modern_python_macos ;;
    *)     _install_modern_python_linux ;;   # debian/arch/fedora/wsl/linux-unknown
  esac
}

_install_modern_python_macos() {
  if ! command -v brew >/dev/null 2>&1; then
    die "Homebrew not found. Install from https://brew.sh and re-run 'ait setup'."
  fi
  info "Installing python@$AIT_VENV_PYTHON_PREFERRED via Homebrew (user-scoped)..."
  brew install "python@$AIT_VENV_PYTHON_PREFERRED"
}

_install_modern_python_linux() {
  local uv_dir="$HOME/.aitask/uv"
  if [[ ! -x "$uv_dir/bin/uv" ]]; then
    info "Downloading uv (astral-sh/uv) into $uv_dir (user-scoped, no sudo)..."
    UV_INSTALL_DIR="$uv_dir" \
    INSTALLER_NO_MODIFY_PATH=1 \
      curl -LsSf https://astral.sh/uv/install.sh | sh
  fi
  info "Installing Python $AIT_VENV_PYTHON_PREFERRED via uv..."
  "$uv_dir/bin/uv" python install "$AIT_VENV_PYTHON_PREFERRED"
  local installed
  installed="$("$uv_dir/bin/uv" python find "$AIT_VENV_PYTHON_PREFERRED")"
  [[ -z "$installed" || ! -x "$installed" ]] && \
    die "uv reported Python $AIT_VENV_PYTHON_PREFERRED installed but interpreter is not executable: $installed"
  mkdir -p "$HOME/.aitask/python/$AIT_VENV_PYTHON_PREFERRED/bin"
  ln -sf "$installed" "$HOME/.aitask/python/$AIT_VENV_PYTHON_PREFERRED/bin/python3"
  info "Python $AIT_VENV_PYTHON_PREFERRED installed at $installed (symlinked at ~/.aitask/python/$AIT_VENV_PYTHON_PREFERRED/bin/python3)."
}
```

Verify the uv installer's env-var contract at implementation time —
`UV_INSTALL_DIR` and `INSTALLER_NO_MODIFY_PATH` are documented at
https://github.com/astral-sh/uv/blob/main/docs/installation.md but the
exact spelling may have changed. If different, adjust accordingly.

### Step 4 — Refactor `setup_python_venv()`

Replace the existing "find python_cmd" preamble:

```bash
setup_python_venv() {
  local python_cmd
  python_cmd="$(find_modern_python "$AIT_VENV_PYTHON_MIN")"
  if [[ -z "$python_cmd" ]]; then
    info "No Python >=$AIT_VENV_PYTHON_MIN found in PATH. Installing one (user-scoped)..."
    install_modern_python
    python_cmd="$(find_modern_python "$AIT_VENV_PYTHON_MIN")"
    [[ -z "$python_cmd" ]] && \
      die "Modern Python install completed but interpreter still not found. Aborting venv setup."
  fi
  info "Using Python for venv: $python_cmd ($("$python_cmd" --version 2>&1))"

  # ... existing venv creation + pip install block, unchanged ...
  "$python_cmd" -m venv "$VENV_DIR"
  "$VENV_DIR/bin/pip" install --quiet --upgrade pip
  "$VENV_DIR/bin/pip" install --quiet \
    'textual>=8.1.1,<9' 'pyyaml==6.0.3' 'linkify-it-py==2.1.0' 'tomli>=2.4.0,<3'
  # ... plotext block ...
}
```

### Step 5 — Update `check_python_version()` doc comment

The function still enforces the 3.9+ baseline for system Python (used by
`install.sh`'s pre-setup merge step). Add a comment clarifying the split:

```bash
check_python_version() {
  # System-Python minimum (3.9+). This is the floor for bootstrap callers
  # like install.sh's aitask_install_merge.py that run BEFORE the venv
  # exists. The venv itself uses a higher floor (AIT_VENV_PYTHON_MIN, see
  # setup_python_venv).
  ...
}
```

No behavior change in this function.

### Step 6 — Integration test

Path: `tests/test_setup_python_install.sh`

Outline (high-level — refine during implementation):

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRATCH="$(mktemp -d /tmp/scratch695XX.XXXXXX)"
trap 'rm -rf "$SCRATCH"' EXIT

# Run install.sh into scratch dir
bash install.sh --dir "$SCRATCH"

# Run ait setup (non-interactive; rely on default profile)
cd "$SCRATCH"
HOME="$SCRATCH/fakehome" ./ait setup --yes  # or whatever non-interactive flag exists

# Assert venv exists and Python is modern
HOME="$SCRATCH/fakehome" "$SCRATCH/fakehome/.aitask/venv/bin/python" -V \
  | awk '{print $2}' | awk -F. '{exit ($1==3 && $2>=11) ? 0 : 1}'

# Assert linkify imports
HOME="$SCRATCH/fakehome" "$SCRATCH/fakehome/.aitask/venv/bin/python" \
  -c "import linkify_it; import textual; import yaml"

# On Linux: assert uv was used and no sudo was invoked
if [[ "$(uname)" == "Linux" ]]; then
  [[ -x "$SCRATCH/fakehome/.aitask/uv/bin/uv" ]]
  [[ -L "$SCRATCH/fakehome/.aitask/python/3.13/bin/python3" ]]
fi

echo "Setup integration test passed."
```

This test may need to be guarded with `[[ -n "$AIT_RUN_INTEGRATION_TESTS" ]]`
or similar if it's too heavy for the default test run. Match whatever
gating pattern exists in `tests/test_release_tarball.sh`.

## Verification

- `bash tests/test_setup_python_install.sh` passes on macOS and Linux
  hosts.
- `shellcheck .aitask-scripts/aitask_setup.sh` clean.
- Manual on macOS with Python 3.9: run `ait setup` → verify brew install
  triggers, venv built on 3.13.
- Manual on Debian 11 with Python 3.9: run `ait setup` → verify uv
  download + python install path triggers, no sudo prompts.

## Dependencies / Sequencing

t695_1 (helper) should land first so `find_modern_python`'s lookup paths
are consistent with the resolver's. Functionally this child is independent,
but coordinating commit order avoids confusion.

## Step 9 — Post-Implementation

Standard archival flow. The integration test runs in a scratch dir, so
nothing on the dev machine needs cleanup beyond what the trap already
handles.
