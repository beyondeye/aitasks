#!/usr/bin/env bash
# run_all_python_tests.sh - Run all Python unit tests
# Run: bash tests/run_all_python_tests.sh
#      bash tests/run_all_python_tests.sh --test-dir <dir>   # a fixture subset
#
# `--test-dir <dir>` is honoured ONLY as the first argument; it is consumed here
# and every remaining argument forwards verbatim to pytest / unittest.
#
# Reading the result (t1179): the LAST line of output is always
#     PYTHON SUITE: PASSED|FAILED (runner=<backend>, exit=<n>)
# and it is derived from the backend's real exit status. Trust nothing else — a
# `Results: N passed, 0 failed` line earlier in the output belongs to ONE
# script-style test module, not to the suite.
#
# Caveat this script cannot fix: piping discards its status.
#     bash tests/run_all_python_tests.sh 2>&1 | tail -40   # exits with tail's 0
# Use `set -o pipefail` or check `${PIPESTATUS[0]}` in the caller. The verdict
# banner goes to stderr so the truth survives `2>&1 | tail` even when the exit
# status does not.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

TEST_DIR="$SCRIPT_DIR"
if [[ "${1:-}" == "--test-dir" ]]; then
    [[ -n "${2:-}" ]] || { echo "--test-dir needs a directory" >&2; exit 2; }
    TEST_DIR="$2"
    shift 2
fi

# Resolve the framework interpreter (prefers the aitask venv, which has the
# board/TUI third-party deps) instead of bare python3, which may be a system
# interpreter lacking yaml/textual/rich (t935).
# shellcheck source=.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"
PY="$(require_ait_python)"

# Do NOT seed PYTHONPATH (t1236). Every test file bootstraps its own sys.path
# from __file__; a runner-supplied path makes a wrong bootstrap pass here and
# fail only at TUI runtime. Any inherited value is scrubbed too, so the suite
# behaves identically regardless of the caller's environment.
unset PYTHONPATH
export PYTHONDONTWRITEBYTECODE=1
# Unbuffered stdout (t1179): a module's own print() output is block-buffered
# when redirected and would otherwise flush at exit — i.e. BELOW the framework's
# stderr verdict, making a failed run read as green from the tail.
export PYTHONUNBUFFERED=1

# Try pytest first, fall back to unittest. Choose the backend here but do not
# run it: execution, the verdict and the exit are one shared path below, so the
# result contract cannot drift between the two branches.
if "$PY" -c "import pytest" 2>/dev/null; then
    backend=pytest
    cmd=("$PY" -m pytest "$TEST_DIR"/test_*.py -v "$@")
else
    backend=unittest
    echo "pytest not found, using unittest discovery"
    cmd=("$PY" -m unittest discover -s "$TEST_DIR" -p 'test_*.py' -v "$@")
fi

set +e
"${cmd[@]}"
rc=$?
set -e

if [ "$rc" -eq 0 ]; then
    echo "PYTHON SUITE: PASSED (runner=$backend, exit=$rc)" >&2
else
    echo "PYTHON SUITE: FAILED (runner=$backend, exit=$rc)" >&2
fi
exit "$rc"
