#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

VENV_PYTHON="$HOME/.aitask/venv/bin/python"

if [[ -x "$VENV_PYTHON" ]]; then
    PYTHON="$VENV_PYTHON"
else
    PYTHON="${PYTHON:-python3}"
    if ! command -v "$PYTHON" &>/dev/null; then
        echo "Error: Python not found. Run 'ait setup' to install dependencies." >&2
        exit 1
    fi

    missing=()
    $PYTHON -c "import textual" 2>/dev/null || missing+=(textual)
    $PYTHON -c "import plotext" 2>/dev/null || missing+=(plotext)

    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "Missing Python packages: ${missing[*]}" >&2
        echo "Run 'ait setup' to install all dependencies." >&2
        echo "Or install manually: pip install ${missing[*]}" >&2
        exit 1
    fi
fi

ait_warn_if_incapable_terminal

export PYTHONPATH="${SCRIPT_DIR}:${PYTHONPATH:-}"
exec "$PYTHON" "$SCRIPT_DIR/stats/stats_app.py" "$@"
