#!/usr/bin/env bash
# aitask_crew_runner.sh - Thin bash wrapper for the AgentCrew runner Python CLI.
#
# Usage: ait crew runner --crew <id> [--interval N] [--max-concurrent N] [--once] [--dry-run] [--check] [--force]
#
# Detects Python (venv > system), validates pyyaml is available, then execs
# into agentcrew/agentcrew_runner.py.

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

exec "$PYTHON" "$SCRIPT_DIR/agentcrew/agentcrew_runner.py" "$@"
