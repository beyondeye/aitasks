#!/usr/bin/env bash
# test_shim_extraction_parity.sh - Guard the heredoc-to-file shim refactor.
# Verifies install_global_shim() writes a file byte-identical to packaging/shim/ait.
# Run: bash tests/test_shim_extraction_parity.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

PASS=0
FAIL=0
TOTAL=0

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if [[ "$expected" == "$actual" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected '$expected', got '$actual')"
    fi
}

# Sandbox SHIM_DIR so the test does not touch ~/.local/bin.
TMPROOT="$(mktemp -d "${TMPDIR:-/tmp}/ait_shim_parity_XXXXXX")"
trap 'rm -rf "$TMPROOT"' EXIT
export SHIM_DIR="$TMPROOT/bin"

# Source aitask_setup.sh in source-only mode (skips main).
# shellcheck disable=SC1091
source .aitask-scripts/aitask_setup.sh --source-only

# Sanity: the SHIM_DIR override must survive sourcing.
assert_eq "SHIM_DIR overrideable" "$TMPROOT/bin" "$SHIM_DIR"

# Run the shim install (suppress noise; failures are surfaced via the diff below).
install_global_shim >/dev/null 2>&1 || true

# Byte-identical compare against packaging/shim/ait.
TOTAL=$((TOTAL + 1))
if diff -q "$SHIM_DIR/ait" packaging/shim/ait >/dev/null 2>&1; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: installed shim differs from packaging/shim/ait"
    diff "$SHIM_DIR/ait" packaging/shim/ait | head -30 || true
fi

# Installed shim must be executable.
TOTAL=$((TOTAL + 1))
if [[ -x "$SHIM_DIR/ait" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: installed shim is not executable"
fi

echo ""
echo "Total: $TOTAL, Pass: $PASS, Fail: $FAIL"
[[ $FAIL -eq 0 ]]
