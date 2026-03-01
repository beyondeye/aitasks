#!/usr/bin/env bash
# run_all_python_tests.sh - Run all Python unit tests
# Run: bash tests/run_all_python_tests.sh

set -euo pipefail

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_DIR/.." && pwd)"

# Add board and lib modules to PYTHONPATH for imports
export PYTHONPATH="$PROJECT_DIR/aiscripts/board:$PROJECT_DIR/aiscripts/lib${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONDONTWRITEBYTECODE=1

# Try pytest first, fall back to unittest
if python3 -c "import pytest" 2>/dev/null; then
    python3 -m pytest "$TEST_DIR"/test_*.py -v "$@"
else
    echo "pytest not found, using unittest discovery"
    python3 -m unittest discover -s "$TEST_DIR" -p 'test_*.py' -v "$@"
fi
