#!/usr/bin/env bash
# run_all_python_tests.sh - Run all Python unit tests
# Run: bash tests/run_all_python_tests.sh

set -euo pipefail

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_DIR/.." && pwd)"

# Resolve the framework interpreter (prefers the aitask venv, which has the
# board/TUI third-party deps) instead of bare python3, which may be a system
# interpreter lacking yaml/textual/rich (t935).
# shellcheck source=.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"
PY="$(require_ait_python)"

# Add board and lib modules to PYTHONPATH for imports
export PYTHONPATH="$PROJECT_DIR/.aitask-scripts/board:$PROJECT_DIR/.aitask-scripts/lib${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONDONTWRITEBYTECODE=1

# Try pytest first, fall back to unittest
if "$PY" -c "import pytest" 2>/dev/null; then
    "$PY" -m pytest "$TEST_DIR"/test_*.py -v "$@"
else
    echo "pytest not found, using unittest discovery"
    "$PY" -m unittest discover -s "$TEST_DIR" -p 'test_*.py' -v "$@"
fi
