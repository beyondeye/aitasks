#!/usr/bin/env bash
# aitask_crew_status.sh - Thin bash wrapper for the AgentCrew status Python CLI.
#
# Usage: ait crew status --crew <id> [--agent <name>] <get|set|list|heartbeat> [options]
#
# Detects Python (venv > system), validates pyyaml is available, then execs
# into agentcrew/agentcrew_status.py.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

VENV_PYTHON="$HOME/.aitask/venv/bin/python"

# Prefer shared venv, fall back to system python
if [[ -x "$VENV_PYTHON" ]]; then
    PYTHON="$VENV_PYTHON"
else
    PYTHON="${PYTHON:-python3}"
    if ! command -v "$PYTHON" &>/dev/null; then
        die "Python not found. Run 'ait setup' to install dependencies."
    fi

    # Check for required packages when using system python
    if ! $PYTHON -c "import yaml" 2>/dev/null; then
        die "Missing Python package: pyyaml. Run 'ait setup' or: pip install pyyaml"
    fi
fi

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Usage: ait crew status --crew <id> [--agent <name>] <get|set|list|heartbeat> [options]"
    echo ""
    echo "Get or set agent and crew status."
    exit 0
fi

exec "$PYTHON" "$SCRIPT_DIR/agentcrew/agentcrew_status.py" "$@"
