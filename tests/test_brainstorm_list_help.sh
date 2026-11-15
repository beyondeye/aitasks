#!/usr/bin/env bash
# test_brainstorm_list_help.sh - `ait brainstorm list --help` prints help for
# `list`, not `status`'s usage (t2308).
# Run: bash tests/test_brainstorm_list_help.sh
#
# The dispatcher implements `list` as `aitask_brainstorm_status.sh --list`, so
# list's help comes from the status script. The `status --help` control proves
# the list branch is selective rather than a global swap of the help text.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

# Shared assertion helpers (see tests/lib/asserts.sh). All assertions run at
# top level (no subshells), so the in-process counters are sufficient.
. "$PROJECT_DIR/tests/lib/asserts.sh"
PASS=0
FAIL=0
TOTAL=0

SCRATCH="$(mktemp -d "${TMPDIR:-/tmp}/brainstorm_list_help.XXXXXX")"
trap 'rm -rf "$SCRATCH"' EXIT

STATUS_SH="$PROJECT_DIR/.aitask-scripts/aitask_brainstorm_status.sh"
STATUS_USAGE="Usage: ait brainstorm status <task_num>"
LIST_USAGE="Usage: ait brainstorm list"

# run <cmd...>: capture stdout and exit status into r_out / r_rc (stderr is discarded).
r_out="" r_rc=""
run() {
    local out_f="$SCRATCH/out"
    r_rc=0
    "$@" >"$out_f" 2>/dev/null || r_rc=$?
    r_out="$(cat "$out_f")"
}

echo "--- ait brainstorm list --help ---"
for flag in --help -h; do
    run "$PROJECT_DIR/ait" brainstorm list "$flag"
    assert_eq "list $flag exits 0" "0" "$r_rc"
    assert_contains "list $flag shows list usage" "$LIST_USAGE" "$r_out"
    assert_not_contains "list $flag does not show status usage" \
        "$STATUS_USAGE" "$r_out"
done

echo "--- flag order does not matter ---"
run bash "$STATUS_SH" --help --list
assert_eq "status --help --list exits 0" "0" "$r_rc"
assert_contains "status --help --list shows list usage" "$LIST_USAGE" "$r_out"
assert_not_contains "status --help --list does not show status usage" \
    "$STATUS_USAGE" "$r_out"

echo "--- control: status --help unchanged ---"
for flag in --help -h; do
    run "$PROJECT_DIR/ait" brainstorm status "$flag"
    assert_eq "status $flag exits 0" "0" "$r_rc"
    assert_contains "status $flag shows status usage" "$STATUS_USAGE" "$r_out"
done

echo ""
echo "=== Results ==="
echo "PASS: $PASS"
echo "FAIL: $FAIL"
echo "TOTAL: $TOTAL"

if [[ "$FAIL" -gt 0 ]]; then
    echo "SOME TESTS FAILED"
    exit 1
fi
echo "ALL TESTS PASSED"
