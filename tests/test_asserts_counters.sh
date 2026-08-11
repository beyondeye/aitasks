#!/usr/bin/env bash
# test_asserts_counters.sh - Tests for the subshell-safe counters in
# tests/lib/asserts.sh (t1207).
#
# WHY THIS FILE EXISTS
#
# Eleven test files ran every assertion inside a `( … )` subshell while their
# footers read a file-backed COUNTER_FILE that the shared asserts.sh helpers
# never wrote. They printed `FAIL:` lines and still exited 0 — for two years,
# invisibly. tests/lib/asserts.sh now offers opt-in file-backed counters with a
# fail-closed contract; this file pins both the mechanism and the contract, plus
# a drift guard so the class cannot come back.
#
# HOW IT TESTS
#
# Each scenario runs in a CHILD `bash` that sources the real asserts.sh and
# prints its counters; the assertions about that child's behaviour then run at
# top level here. A guard test must not judge itself with the counters it is
# testing, and the interesting failures are ones where the child's exit status
# is the whole point.
#
# Run: bash tests/test_asserts_counters.sh

set -e

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_DIR/.." && pwd)"

# Shared assertion helpers (see tests/lib/asserts.sh).
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

ASSERTS="$PROJECT_DIR/tests/lib/asserts.sh"

# Run a child bash script against the real asserts.sh. Echoes the child's
# combined output with a trailing `rc=<status>` line so a scenario can assert on
# both what it printed and how it exited.
run_child() {
    local script="$1" out rc
    set +e
    out="$(bash -c "$script" 2>&1)"
    rc=$?
    set -e
    printf '%s\nrc=%s\n' "$out" "$rc"
}

# ============================================================
# Mechanism: counters survive a subshell
# ============================================================

echo "Test 1: a failing assertion inside a subshell reaches the footer"
out="$(run_child "
    . '$ASSERTS'
    assert_counters_init
    trap 'rm -f \"\$AIT_ASSERT_COUNTER_FILE\"' EXIT
    ( assert_eq 'inner' 'a' 'b' )
    assert_counters_load
    echo \"COUNTS PASS=\$PASS FAIL=\$FAIL TOTAL=\$TOTAL\"
")"
assert_contains "T1: subshell failure counted" "COUNTS PASS=0 FAIL=1 TOTAL=1" "$out"

echo "Test 2: a passing assertion inside a subshell reaches the footer"
out="$(run_child "
    . '$ASSERTS'
    assert_counters_init
    trap 'rm -f \"\$AIT_ASSERT_COUNTER_FILE\"' EXIT
    ( assert_eq 'inner' 'a' 'a' )
    assert_counters_load
    echo \"COUNTS PASS=\$PASS FAIL=\$FAIL TOTAL=\$TOTAL\"
")"
assert_contains "T2: subshell pass counted" "COUNTS PASS=1 FAIL=0 TOTAL=1" "$out"

echo "Test 3: subshell and top-level assertions are both counted"
out="$(run_child "
    . '$ASSERTS'
    assert_counters_init
    trap 'rm -f \"\$AIT_ASSERT_COUNTER_FILE\"' EXIT
    ( assert_eq 'inner pass' 'a' 'a' )
    assert_eq 'outer fail' 'a' 'b'
    assert_counters_load
    echo \"COUNTS PASS=\$PASS FAIL=\$FAIL TOTAL=\$TOTAL\"
")"
assert_contains "T3: mixed scopes counted" "COUNTS PASS=1 FAIL=1 TOTAL=2" "$out"

echo "Test 4: assert_record_pass / assert_record_fail cross the subshell too"
out="$(run_child "
    . '$ASSERTS'
    assert_counters_init
    trap 'rm -f \"\$AIT_ASSERT_COUNTER_FILE\"' EXIT
    ( assert_record_pass; assert_record_fail )
    assert_counters_load
    echo \"COUNTS PASS=\$PASS FAIL=\$FAIL TOTAL=\$TOTAL\"
")"
assert_contains "T4: hand-rolled recorders counted" "COUNTS PASS=1 FAIL=1 TOTAL=2" "$out"

echo "Test 5: the enclosing script exits non-zero on a subshell failure"
out="$(run_child "
    set -e
    . '$ASSERTS'
    assert_counters_init
    trap 'rm -f \"\$AIT_ASSERT_COUNTER_FILE\"' EXIT
    ( assert_eq 'inner' 'a' 'b' )
    assert_counters_load
    [ \"\$FAIL\" -eq 0 ] || exit 1
    echo 'REACHED_END'
")"
assert_contains "T5: exits non-zero" "rc=1" "$out"
assert_not_contains "T5: does not reach the success path" "REACHED_END" "$out"

# ============================================================
# Opt-out: the ~245 files that never enable counting are unaffected
# ============================================================

echo "Test 6: without assert_counters_init, counting is in-process and no file is made"
out="$(run_child "
    . '$ASSERTS'
    PASS=0; FAIL=0; TOTAL=0
    assert_eq 'outer fail' 'a' 'b'
    assert_eq 'outer pass' 'a' 'a'
    echo \"COUNTS PASS=\$PASS FAIL=\$FAIL TOTAL=\$TOTAL FILE=\${AIT_ASSERT_COUNTER_FILE:-none} ENABLED=\${AIT_ASSERT_COUNTERS_ENABLED:-none}\"
")"
assert_contains "T6: in-process counters still work" "COUNTS PASS=1 FAIL=1 TOTAL=2" "$out"
assert_contains "T6: no counter file is created" "FILE=none" "$out"
assert_contains "T6: counting reports itself disabled" "ENABLED=none" "$out"

echo "Test 7: opt-out under set -e is not aborted by the recorders"
out="$(run_child "
    set -e
    . '$ASSERTS'
    PASS=0; FAIL=0; TOTAL=0
    assert_eq 'outer fail' 'a' 'b'
    echo 'REACHED_END'
")"
assert_contains "T7: reaches the end" "REACHED_END" "$out"
assert_contains "T7: exits zero" "rc=0" "$out"

# ============================================================
# Fail-closed contract: an unusable record is never "0 failures"
# ============================================================

echo "Test 8: a record deleted mid-run fails closed"
# The append recreates a deleted file, so absence is not observable at load
# time — the missing sentinel is what catches it.
out="$(run_child "
    set -e
    . '$ASSERTS'
    assert_counters_init
    trap 'rm -f \"\$AIT_ASSERT_COUNTER_FILE\"' EXIT
    ( assert_eq 'inner pass' 'a' 'a' )
    rm -f \"\$AIT_ASSERT_COUNTER_FILE\"
    ( assert_eq 'inner pass 2' 'a' 'a' )
    assert_counters_load
    [ \"\$FAIL\" -eq 0 ] || exit 1
    echo 'REACHED_END'
")"
assert_contains "T8: reports a corrupted record" "sentinel missing" "$out"
assert_contains "T8: exits non-zero" "rc=1" "$out"
assert_not_contains "T8: never reports success" "REACHED_END" "$out"

echo "Test 9: a truncated record fails closed"
out="$(run_child "
    set -e
    . '$ASSERTS'
    assert_counters_init
    trap 'rm -f \"\$AIT_ASSERT_COUNTER_FILE\"' EXIT
    ( assert_eq 'inner pass' 'a' 'a' )
    : > \"\$AIT_ASSERT_COUNTER_FILE\"
    assert_counters_load
    [ \"\$FAIL\" -eq 0 ] || exit 1
    echo 'REACHED_END'
")"
assert_contains "T9: reports a corrupted record" "sentinel missing" "$out"
assert_contains "T9: exits non-zero" "rc=1" "$out"

echo "Test 10: counting enabled with no record at all fails closed"
out="$(run_child "
    set -e
    . '$ASSERTS'
    PASS=0; FAIL=0; TOTAL=0
    AIT_ASSERT_COUNTERS_ENABLED=1
    assert_counters_load
    [ \"\$FAIL\" -eq 0 ] || exit 1
    echo 'REACHED_END'
")"
assert_contains "T10: reports a missing record" "missing or unreadable" "$out"
assert_contains "T10: exits non-zero" "rc=1" "$out"

echo "Test 11: an unwritable record fails closed"
if [[ "$(id -u)" -eq 0 ]]; then
    echo "SKIP: running as root — file mode is not enforced"
else
    # The append fails, so the recorder destroys the record on purpose; the
    # missing sentinel then makes the load fail closed rather than under-count.
    out="$(run_child "
        set -e
        . '$ASSERTS'
        assert_counters_init
        trap 'rm -f \"\$AIT_ASSERT_COUNTER_FILE\"' EXIT
        chmod 0444 \"\$AIT_ASSERT_COUNTER_FILE\"
        ( assert_eq 'inner pass' 'a' 'a' )
        assert_counters_load
        [ \"\$FAIL\" -eq 0 ] || exit 1
        echo 'REACHED_END'
    ")"
    assert_contains "T11: exits non-zero" "rc=1" "$out"
    assert_not_contains "T11: never reports success" "REACHED_END" "$out"
fi

# ============================================================
# Drift guard: the t1207 class cannot come back
# ============================================================

echo "Test 12: no file both sources asserts.sh and keeps a private counter"
# Comment lines are ignored so prose may still describe the historical defect.
offenders=""
for f in "$PROJECT_DIR"/tests/test_*.sh; do
    # Skip self: Test 13's negative-control probe deliberately contains the
    # offending shape, which is exactly what this scan looks for.
    [[ "$(basename "$f")" == "$(basename "${BASH_SOURCE[0]}")" ]] && continue
    grep -q 'lib/asserts\.sh' "$f" || continue
    code="$(grep -v '^[[:space:]]*#' "$f")"
    if printf '%s\n' "$code" | grep -qE '_inc_pass|_inc_fail'; then
        offenders="$offenders $(basename "$f"):_inc_helper"
    fi
    # AIT_ASSERT_COUNTER_FILE is the sanctioned name; a bare COUNTER_FILE is the
    # orphaned scaffolding this task removed.
    if printf '%s\n' "$code" | grep -qE '(^|[^A-Z_])COUNTER_FILE'; then
        offenders="$offenders $(basename "$f"):bare_COUNTER_FILE"
    fi
done
assert_eq "T12: no file mixes asserts.sh with a private counter" "" "$offenders"

echo "Test 13: the drift guard can actually fire"
# Negative control for Test 12: a file matching the offending shape must be
# detected. Without this, an over-narrow regex would make Test 12 vacuous.
probe="$(mktemp "${TMPDIR:-/tmp}/ait_negctrl_XXXXXX")"
cat > "$probe" <<'PROBE'
. "$PROJECT_DIR/tests/lib/asserts.sh"
COUNTER_FILE="$(mktemp)"
_inc_pass() { :; }
PROBE
probe_hits=""
probe_code="$(grep -v '^[[:space:]]*#' "$probe")"
printf '%s\n' "$probe_code" | grep -qE '_inc_pass|_inc_fail' && probe_hits="${probe_hits}inc"
printf '%s\n' "$probe_code" | grep -qE '(^|[^A-Z_])COUNTER_FILE' && probe_hits="${probe_hits},counter"
rm -f "$probe"
assert_eq "T13: guard detects the offending shape" "inc,counter" "$probe_hits"

echo "Test 14: the sanctioned name does not trip the bare-COUNTER_FILE guard"
# shellcheck disable=SC2016  # a literal probe string; expansion would defeat it.
sanctioned='trap "rm -f $AIT_ASSERT_COUNTER_FILE" EXIT'
if printf '%s\n' "$sanctioned" | grep -qE '(^|[^A-Z_])COUNTER_FILE'; then
    assert_record_fail
    echo "FAIL: AIT_ASSERT_COUNTER_FILE wrongly matches the bare-COUNTER_FILE guard"
else
    assert_record_pass
fi

# ============================================================
# Summary
# ============================================================

echo ""
echo "=========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=========================="
[[ "$FAIL" -eq 0 ]] || exit 1
