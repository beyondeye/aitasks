---
priority: medium
effort: low
depends: [t85_3]
issue_type: feature
status: Done
labels: [bash, aitasks]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-11 10:00
updated_at: 2026-02-11 13:13
completed_at: 2026-02-11 13:13
---

## Context

This is child task 6 of parent task t85 (Cross-Platform aitask Framework Distribution). The `aitask_board.sh` script launches the Python TUI board. Currently it tries to auto-install Python dependencies via pip, pipx, or pacman. This needs to be replaced with logic that uses the shared venv at `~/.aitask/venv/` (created by `ait setup`).

**File to modify**: `~/Work/aitasks/aiscripts/aitask_board.sh`

Note: t85_3 already fixed the path from `aitask_board/aitask_board.py` to `board/aitask_board.py`. This task replaces the entire Python resolution and dependency logic.

## Current content (after t85_3 path fix)

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"

if ! command -v "$PYTHON" &>/dev/null; then
    echo "Error: $PYTHON not found. Install Python 3.8+ or set PYTHON env var." >&2
    exit 1
fi

missing=()
$PYTHON -c "import textual" 2>/dev/null || missing+=(textual)
$PYTHON -c "import yaml" 2>/dev/null   || missing+=(pyyaml)
$PYTHON -c "import linkify_it" 2>/dev/null || missing+=(linkify-it-py)

if [ ${#missing[@]} -gt 0 ]; then
    echo "Installing missing dependencies: ${missing[*]}"
    if $PYTHON -m pip --version &>/dev/null; then
        $PYTHON -m pip install --quiet "${missing[@]}"
    elif command -v pipx &>/dev/null; then
        for pkg in "${missing[@]}"; do pipx install "$pkg"; done
    elif command -v pacman &>/dev/null; then
        declare -A pkg_map=([textual]=python-textual [pyyaml]=python-yaml [linkify-it-py]=python-linkify-it-py)
        arch_pkgs=()
        for pkg in "${missing[@]}"; do arch_pkgs+=("${pkg_map[$pkg]:-python-$pkg}"); done
        sudo pacman -S --needed --noconfirm "${arch_pkgs[@]}"
    else
        echo "Error: pip not available. Install dependencies manually: ${missing[*]}" >&2
        exit 1
    fi
fi

exec $PYTHON "$SCRIPT_DIR/board/aitask_board.py" "$@"
```

## What to Do

### Replace the entire script with this new version

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$HOME/.aitask/venv/bin/python"

# Prefer shared venv, fall back to system python
if [[ -x "$VENV_PYTHON" ]]; then
    PYTHON="$VENV_PYTHON"
else
    PYTHON="${PYTHON:-python3}"
    if ! command -v "$PYTHON" &>/dev/null; then
        echo "Error: Python not found. Run 'ait setup' to install dependencies." >&2
        exit 1
    fi

    # Check for required packages when using system python
    missing=()
    $PYTHON -c "import textual" 2>/dev/null || missing+=(textual)
    $PYTHON -c "import yaml" 2>/dev/null   || missing+=(pyyaml)
    $PYTHON -c "import linkify_it" 2>/dev/null || missing+=(linkify-it-py)

    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "Missing Python packages: ${missing[*]}" >&2
        echo "Run 'ait setup' to install all dependencies." >&2
        echo "Or install manually: pip install ${missing[*]}" >&2
        exit 1
    fi
fi

exec "$PYTHON" "$SCRIPT_DIR/board/aitask_board.py" "$@"
```

### Key changes from current version

1. **Prefers `~/.aitask/venv/bin/python`** — if the shared venv exists, use it directly (no dependency checks needed since setup installed everything)
2. **Falls back to system python** with dependency checks — but does NOT auto-install
3. **Removes all auto-install logic** (pip, pipx, pacman) — delegates to `ait setup`
4. **Error messages reference `ait setup`** instead of manual pip commands
5. **Quotes `$PYTHON`** in the `exec` line for safety

### Commit

```bash
cd ~/Work/aitasks
git add aiscripts/aitask_board.sh
git commit -m "Use shared venv for Python TUI, remove auto-install logic"
```

## Verification

1. With venv present (`~/.aitask/venv/` exists): `./ait board` launches using venv python
2. With venv absent (temporarily rename `~/.aitask/`): script falls back to system python or prints clear error message pointing to `ait setup`
3. No references to `pacman`, `pipx`, or `pip install` remain in the script
