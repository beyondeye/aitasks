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
        # Arch Linux: map PyPI names to system packages
        declare -A pkg_map=([textual]=python-textual [pyyaml]=python-yaml [linkify-it-py]=python-linkify-it-py)
        arch_pkgs=()
        for pkg in "${missing[@]}"; do arch_pkgs+=("${pkg_map[$pkg]:-python-$pkg}"); done
        sudo pacman -S --needed --noconfirm "${arch_pkgs[@]}"
    else
        echo "Error: pip not available. Install dependencies manually: ${missing[*]}" >&2
        exit 1
    fi
fi

exec $PYTHON "$SCRIPT_DIR/aitask_board/aitask_board.py" "$@"
