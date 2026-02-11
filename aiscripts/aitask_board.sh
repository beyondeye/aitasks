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
