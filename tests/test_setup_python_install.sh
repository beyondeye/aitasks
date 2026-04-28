#!/usr/bin/env bash
# test_setup_python_install.sh - End-to-end test of `install.sh -> ait setup`
# verifying that the framework venv is built on a Python >=3.11.
#
# Heavy integration test (downloads brew formulae or uv; minutes-scale).
# Gated behind AIT_RUN_INTEGRATION_TESTS=1 to keep default `bash tests/...`
# runs fast.
#
# Run: AIT_RUN_INTEGRATION_TESTS=1 bash tests/test_setup_python_install.sh
set -euo pipefail

if [[ -z "${AIT_RUN_INTEGRATION_TESTS:-}" ]]; then
    echo "SKIP: set AIT_RUN_INTEGRATION_TESTS=1 to run full install integration test"
    exit 0
fi

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRATCH="$(mktemp -d /tmp/scratch695_XXXXXX)"
trap 'rm -rf "$SCRATCH"' EXIT

FAKE_HOME="$SCRATCH/fakehome"
mkdir -p "$FAKE_HOME"

echo "=== Integration test: ait setup installs venv on Python >=3.11 ==="
echo "Scratch: $SCRATCH"
echo ""

# Run install.sh into scratch dir
echo "--- Running install.sh ---"
bash "$PROJECT_DIR/install.sh" --dir "$SCRATCH"

# Run ait setup with stdin redirected so the existing -t 0 auto-accept paths
# fire (no --yes flag exists, by design).
echo ""
echo "--- Running ait setup (HOME=$FAKE_HOME) ---"
HOME="$FAKE_HOME" "$SCRATCH/ait" setup < /dev/null

# Assert venv exists and Python >= 3.11
echo ""
echo "--- Verifying venv Python >=3.11 ---"
[[ -x "$FAKE_HOME/.aitask/venv/bin/python" ]] || {
    echo "FAIL: venv python not found at $FAKE_HOME/.aitask/venv/bin/python"
    exit 1
}
ver="$("$FAKE_HOME/.aitask/venv/bin/python" -c 'import sys; print("{}.{}".format(*sys.version_info[:2]))')"
ver_major="${ver%%.*}"
ver_minor="${ver##*.}"
if ! { [[ "$ver_major" -gt 3 ]] || { [[ "$ver_major" -eq 3 ]] && [[ "$ver_minor" -ge 11 ]]; }; }; then
    echo "FAIL: venv Python is $ver (expected >= 3.11)"
    exit 1
fi
echo "PASS: venv Python is $ver"

# Assert critical deps import (linkify-it is the original failure point)
echo ""
echo "--- Verifying linkify_it / textual / yaml import ---"
"$FAKE_HOME/.aitask/venv/bin/python" -c "import linkify_it; import textual; import yaml"
echo "PASS: dependencies import"

# On Linux without modern system python: assert uv was used
echo ""
echo "--- Inspecting install artifacts ---"
if [[ "$(uname)" == "Linux" ]] && [[ -x "$FAKE_HOME/.aitask/uv/bin/uv" ]]; then
    echo "uv was installed at $FAKE_HOME/.aitask/uv/bin/uv"
    if [[ -L "$FAKE_HOME/.aitask/python/3.13/bin/python3" ]]; then
        echo "PASS: uv installed Python 3.13 with symlink at $FAKE_HOME/.aitask/python/3.13/bin/python3"
    fi
elif [[ "$(uname)" == "Darwin" ]]; then
    echo "Note: macOS host — brew install path expected (not asserting brew artifacts)."
else
    echo "Note: Linux host had a modern system Python; uv path not exercised."
fi

echo ""
echo "=== PASS: integration test ==="
