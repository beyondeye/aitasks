#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/aitask_path.sh
source "$SCRIPT_DIR/lib/aitask_path.sh"
# shellcheck source=lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

PYTHON="$(require_ait_python)"

# Applink headless mode (--headless-for-applink): skip the Textual monitor TUI
# and run the applink bridge listener (control plane + push loop) with no
# terminal UI, for an unattended box. The flag is parsed here because
# monitor_app.py's argparse would reject it; see applink/headless.py.
headless=0
fwd=()
for a in "$@"; do
    if [[ "$a" == "--headless-for-applink" ]]; then
        headless=1
    else
        fwd+=("$a")
    fi
done

if [[ "$headless" -eq 1 ]]; then
    # Headless applink needs the applink deps (NOT textual — the TUI is skipped).
    missing=()
    "$PYTHON" -c "import websockets" 2>/dev/null || missing+=(websockets)
    "$PYTHON" -c "import msgpack"    2>/dev/null || missing+=(msgpack)
    "$PYTHON" -c "import segno"      2>/dev/null || missing+=(segno)
    "$PYTHON" -c "import yaml"       2>/dev/null || missing+=(pyyaml)
    if [[ ${#missing[@]} -gt 0 ]]; then
        die "Missing Python packages: ${missing[*]}. Run 'ait setup' to install all dependencies."
    fi
    if ! command -v tmux &>/dev/null; then
        echo "Error: tmux is not installed. The applink bridge requires tmux." >&2
        exit 1
    fi
    exec "$PYTHON" "$SCRIPT_DIR/applink/headless.py" ${fwd[@]+"${fwd[@]}"}
fi

# Catch the "venv exists but lacks deps" case.
missing=()
"$PYTHON" -c "import textual" 2>/dev/null || missing+=(textual)
"$PYTHON" -c "import yaml"    2>/dev/null || missing+=(pyyaml)
if [[ ${#missing[@]} -gt 0 ]]; then
    die "Missing Python packages: ${missing[*]}. Run 'ait setup' to install all dependencies."
fi

# Check tmux is available
if ! command -v tmux &>/dev/null; then
    echo "Error: tmux is not installed. The monitor TUI requires tmux." >&2
    exit 1
fi

# Check terminal capabilities (warn on incapable terminals)
ait_warn_if_incapable_terminal

exec "$PYTHON" "$SCRIPT_DIR/monitor/monitor_app.py" "$@"
