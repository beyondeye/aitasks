#!/usr/bin/env bash
# test_brainstorm_init_proposal_file.sh - Bash-level validation tests for
# `ait brainstorm init --proposal-file`. All tests exercise paths that die
# before crew creation, so no project state is mutated.

set -euo pipefail

THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$THIS_DIR/.." && pwd)"
cd "$REPO_ROOT"

PASS=0
FAIL=0

assert_dies_with() {
    local desc="$1" needle="$2"
    shift 2
    local out exitcode=0
    out=$("$@" 2>&1) || exitcode=$?
    if [[ $exitcode -eq 0 ]]; then
        echo "FAIL: $desc — expected non-zero exit"
        FAIL=$((FAIL + 1))
        return
    fi
    if [[ "$out" != *"$needle"* ]]; then
        echo "FAIL: $desc — expected '$needle' in output, got: $out"
        FAIL=$((FAIL + 1))
        return
    fi
    PASS=$((PASS + 1))
}

# 1. Missing proposal file.
assert_dies_with "missing proposal file" "Proposal file not found" \
    ./.aitask-scripts/aitask_brainstorm_init.sh 999999 --proposal-file /nonexistent/path.md

# 2. Empty proposal file.
EMPTY="$(mktemp "${TMPDIR:-/tmp}/br_empty_XXXXXX.md")"
trap 'rm -f "$EMPTY"' EXIT
assert_dies_with "empty proposal file" "Proposal file is empty" \
    ./.aitask-scripts/aitask_brainstorm_init.sh 999999 --proposal-file "$EMPTY"

# 3. Missing value after --proposal-file.
assert_dies_with "missing argument" "requires an argument" \
    ./.aitask-scripts/aitask_brainstorm_init.sh 999999 --proposal-file

echo "---"
echo "PASSED: $PASS"
echo "FAILED: $FAIL"
[[ $FAIL -eq 0 ]]
