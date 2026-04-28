#!/usr/bin/env bash
# aitask_crew_report.sh - Thin bash wrapper for the AgentCrew report Python CLI.
#
# Usage: ait crew report [--batch] <summary|detail|output|list> [options]
#
# Detects Python (venv > system), validates pyyaml is available, then execs
# into agentcrew/agentcrew_report.py.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/aitask_path.sh
source "$SCRIPT_DIR/lib/aitask_path.sh"
# shellcheck source=lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

PYTHON="$(require_ait_python)"

if ! "$PYTHON" -c "import yaml" 2>/dev/null; then
    die "Missing Python package: pyyaml. Run 'ait setup' or: pip install pyyaml"
fi

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Usage: ait crew report [--batch] <summary|detail|output|list> [options]"
    echo ""
    echo "Report crew summary, agent details, and outputs."
    exit 0
fi

exec "$PYTHON" "$SCRIPT_DIR/agentcrew/agentcrew_report.py" "$@"
