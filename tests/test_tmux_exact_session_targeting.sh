#!/usr/bin/env bash
# test_tmux_exact_session_targeting.sh - Verify that session-denominated tmux
# targets use exact-match (=<session>) form, so that projects with session
# names sharing a prefix (e.g. 'aitasks' vs 'aitasks_mob') do not collide.
#
# Covers:
#   * tmux_session_target / tmux_window_target helpers return '=<session>[:win]'
#   * Real tmux distinguishes '=<name>' (exact) from plain '<name>' (prefix)
#   * agent_launch_utils.find_window_by_name is scoped to a single session
#
# Run: bash tests/test_tmux_exact_session_targeting.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/require_no_tmux.sh
. "$SCRIPT_DIR/lib/require_no_tmux.sh"
require_no_tmux

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

assert_exit_zero() {
    local desc="$1"
    shift
    TOTAL=$((TOTAL + 1))
    if "$@" >/dev/null 2>&1; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected exit 0, got non-zero)"
    fi
}

assert_exit_nonzero() {
    local desc="$1"
    shift
    TOTAL=$((TOTAL + 1))
    if "$@" >/dev/null 2>&1; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected non-zero exit, got 0)"
    else
        PASS=$((PASS + 1))
    fi
}

# --- Tier 1: Python helpers (always run) ---

out=$(PYTHONPATH="$PROJECT_DIR/.aitask-scripts/lib" python3 -c "
import agent_launch_utils as u
print(u.tmux_session_target('aitasks'))
print(u.tmux_window_target('aitasks', 'monitor'))
print(u.tmux_window_target('aitasks', ''))
print(u.tmux_window_target('aitasks', 42))
")
mapfile -t lines <<<"$out"
assert_eq "tmux_session_target('aitasks')" "=aitasks" "${lines[0]:-}"
assert_eq "tmux_window_target('aitasks','monitor')" "=aitasks:monitor" "${lines[1]:-}"
assert_eq "tmux_window_target('aitasks','') (trailing-colon idiom)" "=aitasks:" "${lines[2]:-}"
assert_eq "tmux_window_target('aitasks',42) (int index)" "=aitasks:42" "${lines[3]:-}"

# find_window_by_name requires an explicit session (no default, positional arg).
sig=$(PYTHONPATH="$PROJECT_DIR/.aitask-scripts/lib" python3 -c "
import inspect, agent_launch_utils as u
print(list(inspect.signature(u.find_window_by_name).parameters))
")
assert_eq "find_window_by_name signature takes [name, session]" "['name', 'session']" "$sig"

# --- Tier 2: Real tmux behavior (skip cleanly if tmux missing or unusable) ---

if ! command -v tmux >/dev/null 2>&1; then
    echo "SKIP: tmux not installed — skipping runtime assertions"
else
    # Use a test-only tmux server (TMUX_TMPDIR) so we never touch the user's
    # real sessions, regardless of outcome.
    TEST_TMUX_DIR=$(mktemp -d "${TMPDIR:-/tmp}/ait_tmux_test_XXXXXX")
    export TMUX_TMPDIR="$TEST_TMUX_DIR"
    # Unset TMUX so nested invocations don't refuse.
    unset TMUX

    PFX="aittest_$$"

    cleanup() {
        tmux kill-server 2>/dev/null || true
        rm -rf "$TEST_TMUX_DIR"
    }
    trap cleanup EXIT

    # Start two sessions whose names share a prefix.
    if ! tmux new-session -d -s "${PFX}_mob" -n stub 'sleep 300' 2>/dev/null; then
        echo "SKIP: could not start test tmux session — skipping runtime assertions"
    else
        tmux new-session -d -s "${PFX}" -n stub 'sleep 300'

        # Sanity: both sessions exist under their exact names.
        assert_exit_zero "=${PFX} exists"       tmux has-session -t "=${PFX}"
        assert_exit_zero "=${PFX}_mob exists"   tmux has-session -t "=${PFX}_mob"

        # Kill the shorter-named session; the longer one remains.
        tmux kill-session -t "=${PFX}"

        # Exact match MUST now fail — this is the property we need.
        assert_exit_nonzero "=${PFX} rejects prefix collision" \
            tmux has-session -t "=${PFX}"

        # Document (not require) that plain prefix match still succeeds;
        # this is the tmux default that the '=' prefix guards against.
        if tmux has-session -t "${PFX}" 2>/dev/null; then
            : # expected — plain match wrongly resolves to ${PFX}_mob
        fi

        # find_window_by_name MUST be scoped: looking up 'stub' in '=${PFX}'
        # (which was killed) must return None, even though a 'stub' window
        # still exists in '${PFX}_mob'. Without scoping, the old whole-
        # server scan would have returned the wrong session.
        result=$(PYTHONPATH="$PROJECT_DIR/.aitask-scripts/lib" \
            TMUX_TMPDIR="$TEST_TMUX_DIR" python3 -c "
import agent_launch_utils as u
r = u.find_window_by_name('stub', '${PFX}')
print('NONE' if r is None else 'FOUND:%s:%s' % r)
")
        assert_eq "find_window_by_name('stub','${PFX}') returns None" \
            "NONE" "$result"

        # And it DOES find the window when pointed at the surviving session.
        result=$(PYTHONPATH="$PROJECT_DIR/.aitask-scripts/lib" \
            TMUX_TMPDIR="$TEST_TMUX_DIR" python3 -c "
import agent_launch_utils as u
r = u.find_window_by_name('stub', '${PFX}_mob')
print('NONE' if r is None else 'FOUND:%s' % r[0])
")
        assert_eq "find_window_by_name('stub','${PFX}_mob') finds it" \
            "FOUND:${PFX}_mob" "$result"
    fi
fi

echo
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
exit $([[ $FAIL -eq 0 ]] && echo 0 || echo 1)
