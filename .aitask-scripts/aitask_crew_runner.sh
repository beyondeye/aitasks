#!/usr/bin/env bash
# aitask_crew_runner.sh - Thin bash wrapper for the AgentCrew runner Python CLI.
#
# Usage: ait crew runner --crew <id> [--interval N] [--max-concurrent N] [--once] [--dry-run] [--check] [--force]
#
# Detects Python (venv > system), validates pyyaml is available, then execs
# into agentcrew/agentcrew_runner.py.

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
    echo "Usage: ait crew runner --crew <id> [--interval N] [--max-concurrent N] [--once] [--dry-run] [--check] [--force]"
    echo ""
    echo "Start or check the crew runner orchestrator."
    exit 0
fi

exec "$PYTHON" "$SCRIPT_DIR/agentcrew/agentcrew_runner.py" "$@"
