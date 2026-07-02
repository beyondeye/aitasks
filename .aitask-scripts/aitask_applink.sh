#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/aitask_path.sh disable=SC1091
source "$SCRIPT_DIR/lib/aitask_path.sh"
# shellcheck source=lib/python_resolve.sh disable=SC1091
source "$SCRIPT_DIR/lib/python_resolve.sh"
# shellcheck source=lib/terminal_compat.sh disable=SC1091
source "$SCRIPT_DIR/lib/terminal_compat.sh"

PYTHON="$(require_ait_python)"

# Catch the "venv exists but lacks deps" case.
missing=()
"$PYTHON" -c "import textual"    2>/dev/null || missing+=(textual)
"$PYTHON" -c "import segno"      2>/dev/null || missing+=(segno)
"$PYTHON" -c "import websockets" 2>/dev/null || missing+=(websockets)
"$PYTHON" -c "import msgpack"    2>/dev/null || missing+=(msgpack)
if [[ ${#missing[@]} -gt 0 ]]; then
    die "Missing Python packages: ${missing[*]}. Run 'ait setup' to install all dependencies."
fi

ait_warn_if_incapable_terminal

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Usage: ait applink"
    echo ""
    echo "Launch the App Linker TUI for pairing a mobile companion."
    exit 0
fi

exec "$PYTHON" "$SCRIPT_DIR/applink/applink_app.py" "$@"
