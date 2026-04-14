#!/usr/bin/env bash
# aitask_crew_logview.sh - Thin bash wrapper for the agent log viewer TUI.
#
# Usage:
#   ait crew logview --path <file> [--no-tail]
#   ait crew logview <crew_id> <agent_name> [--no-tail]

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
        die "Python not found. Run 'ait setup' to install dependencies."
    fi
fi

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    cat <<'EOF'
Usage:
  ait crew logview --path <file> [--no-tail]
  ait crew logview <crew_id> <agent_name> [--no-tail]

Render an agent log file with ANSI escape support. Tails the file live
by default; pass --no-tail for a static snapshot.
EOF
    exit 0
fi

ARGS=()
if [[ $# -ge 2 && "$1" != --* && "$2" != --* ]]; then
    ARGS+=(--crew "$1" --agent "$2")
    shift 2
fi
ARGS+=("$@")

exec "$PYTHON" "$SCRIPT_DIR/logview/logview_app.py" "${ARGS[@]}"
