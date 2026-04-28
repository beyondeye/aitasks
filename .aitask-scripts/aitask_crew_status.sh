#!/usr/bin/env bash
# aitask_crew_status.sh - Thin bash wrapper for the AgentCrew status Python CLI.
#
# Usage: ait crew status --crew <id> [--agent <name>] <get|set|list|heartbeat> [options]
#
# Detects Python (venv > system), validates pyyaml is available, then execs
# into agentcrew/agentcrew_status.py.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/aitask_path.sh
source "$SCRIPT_DIR/lib/aitask_path.sh"
# shellcheck source=lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

PYTHON="$(require_ait_python)"

# Catch the "venv exists but lacks deps" case.
if ! "$PYTHON" -c "import yaml" 2>/dev/null; then
    die "Missing Python package: pyyaml. Run 'ait setup' or: pip install pyyaml"
fi

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Usage: ait crew status --crew <id> [--agent <name>] <get|set|list|heartbeat> [options]"
    echo ""
    echo "Get or set agent and crew status."
    exit 0
fi

exec "$PYTHON" "$SCRIPT_DIR/agentcrew/agentcrew_status.py" "$@"
