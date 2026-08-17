#!/usr/bin/env bash
# test_trail_depth_resolve.sh — the /aitask-trail Step 0 grammar, executably
# (t1505_4).
#
# Until this file existed the argument matrix lived only as prose in the skill
# template and as substring pins in test_trail_skill_contract.sh. Neither can
# tell you what `--refresh X --deep` actually RESOLVES to — they only prove the
# sentence describing it is still present. These drive the resolver and assert
# the decision.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

. "$PROJECT_DIR/tests/lib/asserts.sh"

cd "$PROJECT_DIR"

RESOLVER="./.aitask-scripts/aitask_trail_depth.sh"

# assert_resolves <label> <expected-stdout> -- <args...>
assert_resolves() {
    local label="$1" expected="$2"
    shift 3  # label, expected, the literal --
    local actual status
    set +e
    actual="$("$RESOLVER" resolve -- "$@" 2>&1)"
    status=$?
    set -e
    TOTAL=$((TOTAL + 1))
    if [[ "$actual" == "$expected" && "$status" -eq 0 ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $label"
        echo "  args:     $*"
        echo "  expected: $(printf '%s' "$expected" | tr '\n' '|')  (exit 0)"
        echo "  actual:   $(printf '%s' "$actual" | tr '\n' '|')  (exit $status)"
    fi
}

# assert_error <label> <expected-ERROR-line> -- <args...>
# Pins BOTH the stdout line and exit 1. An earlier version of the resolver
# captured the operand via `$(...)`, which swallowed the ERROR line into a
# variable and exited 1 with EMPTY stdout — a status-only assertion would have
# passed on it.
assert_error() {
    local label="$1" expected="$2"
    shift 3
    local actual status
    set +e
    actual="$("$RESOLVER" resolve -- "$@" 2>/dev/null)"
    status=$?
    set -e
    TOTAL=$((TOTAL + 1))
    if [[ "$actual" == "$expected" && "$status" -eq 1 ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $label"
        echo "  args:     $*"
        echo "  expected: '$expected' (exit 1)"
        echo "  actual:   '$actual' (exit $status)"
    fi
}

echo "=== Test 1: the accepted grammar matrix ==="

assert_resolves "deep refresh, flag last" \
"MODE:refresh
DEPTH:deep
HANDLE:art:trail-x" -- --refresh art:trail-x --deep

assert_resolves "deep refresh, flag first (position-independent)" \
"MODE:refresh
DEPTH:deep
HANDLE:art:trail-x" -- --deep --refresh art:trail-x

assert_resolves "refresh with no flag is LITE" \
"MODE:refresh
DEPTH:lite
HANDLE:art:trail-x" -- --refresh art:trail-x

assert_resolves "task id + --deep" \
"MODE:create
DEPTH:deep
TARGET:42" -- 42 --deep

assert_resolves "--deep + task id (either order)" \
"MODE:create
DEPTH:deep
TARGET:42" -- --deep 42

assert_resolves "--topics + --deep" \
"MODE:create
DEPTH:deep
TOPICS:130,205" -- --topics 130,205 --deep

assert_resolves "--deep alone is a deep create" \
"MODE:create
DEPTH:deep" -- --deep

assert_resolves "no arguments is a LITE create" \
"MODE:create
DEPTH:lite" --

assert_resolves "--lite is the default, stated explicitly" \
"MODE:create
DEPTH:lite
TARGET:42" -- 42 --lite

echo "=== Test 2: --show does not take a depth, and says so ==="

# DEPTH is the AUTHORING depth. Show authors nothing, so it is n/a -- never
# the caller's flag echoed back. A run told "deep" here could print "deep" for
# a lite or entirely unmarked artifact, contradicting the show flow's contract
# to report the STORED depth.
assert_resolves "plain show reports no authoring depth" \
"MODE:show
DEPTH:n/a
HANDLE:art:trail-x" -- --show art:trail-x

assert_resolves "show + depth flag: still n/a, and the drop is announced" \
"MODE:show
DEPTH:n/a
HANDLE:art:trail-x
NOTE:depth_ignored_for_show" -- --show art:trail-x --deep

assert_resolves "show + --lite is equally n/a" \
"MODE:show
DEPTH:n/a
HANDLE:art:trail-x
NOTE:depth_ignored_for_show" -- --show art:trail-x --lite

echo "=== Test 3: handle normalization and auto-detect ==="

assert_resolves "bare handle without art: prefix is normalized" \
"MODE:refresh
DEPTH:lite
HANDLE:art:trail-x" -- --refresh trail-x

assert_resolves "a bare trail token is ambiguous (skill must ask show/refresh)" \
"MODE:ambiguous_handle
DEPTH:unresolved
HANDLE:art:trail-x" -- trail-x

# The ambiguous state must carry NO usable depth. Emitting "deep" here is how a
# supplied flag leaks into a show the user only chooses afterwards: the skill
# would already hold DEPTH:deep and never reach the show branch's n/a.
assert_resolves "an ambiguous handle withholds the depth even when one is given" \
"MODE:ambiguous_handle
DEPTH:unresolved
HANDLE:art:trail-x" -- trail-x --deep

assert_resolves "...and with --lite too" \
"MODE:ambiguous_handle
DEPTH:unresolved
HANDLE:art:trail-x" -- trail-x --lite

echo "=== Test 3b: re-resolving an ambiguous handle, both branches ==="

# After the show-or-refresh question the skill re-runs the resolver with the
# chosen selector inserted before the handle, keeping the original flags. Both
# outcomes are pinned, because the whole point is that they DIFFER: refresh
# honours the flag, show discards it and says so.
assert_resolves "re-resolved as refresh honours the original --deep" \
"MODE:refresh
DEPTH:deep
HANDLE:art:trail-x" -- --refresh trail-x --deep

assert_resolves "re-resolved as show discards it and announces the drop" \
"MODE:show
DEPTH:n/a
HANDLE:art:trail-x
NOTE:depth_ignored_for_show" -- --show trail-x --deep

assert_resolves "re-resolved as refresh with no flag is lite" \
"MODE:refresh
DEPTH:lite
HANDLE:art:trail-x" -- --refresh trail-x

assert_resolves "re-resolved as show with no flag has no NOTE" \
"MODE:show
DEPTH:n/a
HANDLE:art:trail-x" -- --show trail-x

# The rewrite REPLACES the bare handle token; it does not prepend a selector to
# the untouched list. Pinning the wrong transformation keeps the template's
# wording honest: an instruction to "keep every original argument" produces
# these, and they are hard errors rather than a working fallback.
assert_error "keeping the bare token as well is a mode conflict (show)" \
    "ERROR:conflicting_modes:--show,trail-x" -- --show trail-x trail-x --deep

assert_error "keeping the bare token as well is a mode conflict (refresh)" \
    "ERROR:conflicting_modes:--refresh,trail-x" -- --refresh trail-x trail-x --deep

echo "=== Test 4: conflicts fail closed, never guess ==="

assert_error "--deep with --lite is an error, not a preference" \
    "ERROR:conflicting_depth_flags" -- --deep --lite

assert_error "--lite with --deep (reverse order) is equally an error" \
    "ERROR:conflicting_depth_flags" -- --lite --deep

assert_error "two different mode selectors" \
    "ERROR:conflicting_modes:--refresh,--show" -- --refresh art:trail-a --show art:trail-b

assert_error "a repeated mode selector" \
    "ERROR:repeated_mode:--show" -- --show art:trail-a --show art:trail-b

assert_error "unknown flag" \
    "ERROR:unknown_flag:--bogus" -- --bogus

assert_error "a second bare task id" \
    "ERROR:unexpected_argument:43" -- 42 43

echo "=== Test 5: a depth flag is never eaten as a mode operand ==="

# The whole point: `--refresh --deep` must NOT resolve to a refresh of a handle
# named "--deep". Both of these also guard the silent-abort regression: they
# must print the ERROR line, not merely exit non-zero.
assert_error "--refresh consuming --deep is a missing operand" \
    "ERROR:missing_operand:--refresh" -- --refresh --deep

assert_error "--refresh with nothing after it" \
    "ERROR:missing_operand:--refresh" -- --refresh

assert_error "--show consuming --lite is a missing operand" \
    "ERROR:missing_operand:--show" -- --show --lite

assert_error "--topics consuming --deep is a missing operand" \
    "ERROR:missing_operand:--topics" -- --topics --deep

# ...and not only depth flags. Any dash-leading token in operand position is
# refused, or `--refresh --bogus` resolves "successfully" to the handle
# art:--bogus and a malformed request goes downstream instead of stopping.
assert_error "--refresh will not swallow the -- delimiter" \
    "ERROR:missing_operand:--refresh" -- --refresh --

assert_error "--refresh will not swallow an unknown flag as a handle" \
    "ERROR:missing_operand:--refresh" -- --refresh --bogus

assert_error "--show will not swallow the -- delimiter" \
    "ERROR:missing_operand:--show" -- --show --

assert_error "--show will not swallow a short flag" \
    "ERROR:missing_operand:--show" -- --show -x

assert_error "--topics will not swallow the -- delimiter" \
    "ERROR:missing_operand:--topics" -- --topics --

assert_error "--topics will not swallow an unknown flag" \
    "ERROR:missing_operand:--topics" -- --topics --bogus

echo "=== Test 6: repeated identical depth flag is not a conflict ==="

assert_resolves "--deep twice agrees with itself" \
"MODE:create
DEPTH:deep" -- --deep --deep

echo "=== Test 7: usage errors exit 2 ==="

TOTAL=$((TOTAL + 1))
set +e
"$RESOLVER" >/dev/null 2>&1
status=$?
set -e
if [[ "$status" -eq 2 ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: bare invocation should exit 2, got $status"
fi

TOTAL=$((TOTAL + 1))
set +e
"$RESOLVER" resolve >/dev/null 2>&1   # missing the -- sentinel
status=$?
set -e
if [[ "$status" -eq 2 ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: missing -- sentinel should exit 2, got $status"
fi

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]] || exit 1
