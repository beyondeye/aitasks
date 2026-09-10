#!/usr/bin/env bash
# test_tmux_pane_for_pid.sh - lib/tmux_exec.sh::ait_tmux_pane_for_pid (t1725_4).
#
# The gateway helper that turns a process id into the tmux pane owning it. Two
# callers depend on its exact output: aitask_live_endpoint.sh (live note
# delivery, whose adapter joins the target against the agent session listing)
# and aitask_sync.sh (a deferral record's `pane` column, and the
# --require-waiting re-probe).
#
#   1. a pane's own pid resolves, to the EXACT line tmux itself renders
#   2. a descendant of the pane process resolves to that same pane (the walk)
#   3. a pid no gateway pane owns returns 1 with empty output
#   4. a malformed pid returns 1 with empty output
#   5. a session name carrying `|` survives verbatim in the target (the sync
#      record percent-encodes it; the helper must not mangle it first)
#   6. NEGATIVE CONTROL: case 1's pid with the gateway socket pointed at a
#      server that does not exist returns 1, so case 1 is attributable to the
#      socket handed to the helper and not to anything ambient
#
# Isolation: a private `-L` server killed in a trap; `require_isolated_tmux`
# detaches this process from any inherited server first.
#
# Run: bash tests/test_tmux_pane_for_pid.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

if ! command -v tmux >/dev/null 2>&1; then
    echo "SKIP: tmux not available"
    exit 0
fi

# shellcheck source=lib/tmux_isolation.sh
. "$SCRIPT_DIR/lib/tmux_isolation.sh"
require_isolated_tmux

# shellcheck source=../.aitask-scripts/lib/tmux_exec.sh
. "$PROJECT_DIR/.aitask-scripts/lib/tmux_exec.sh"

SOCK="ait_panepid_$$"
NOSRV="ait_panepid_nosrv_$$"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/test_panepid_XXXXXX")"
# shellcheck disable=SC2329  # invoked indirectly, by the EXIT trap below
cleanup() {
    tmux -L "$SOCK" kill-server 2>/dev/null || true
    rm -rf "$TMP"
}
trap cleanup EXIT

# The helper, pointed at THIS test's server for the one call.
resolve() { AITASKS_TMUX_SOCKET="$SOCK" ait_tmux_pane_for_pid "$@"; }

# tmux's own rendering of a session's (single) pane: the independent ground truth.
tmux_line() {
    tmux -L "$SOCK" list-panes -t "=$1" \
        -F '#{pane_id}'$'\t''#{session_name}:#{window_id}.#{pane_id}' 2>/dev/null | head -1
}
tmux_pane_pid() {
    tmux -L "$SOCK" list-panes -t "=$1" -F '#{pane_pid}' 2>/dev/null | head -1
}

set +e

echo "=== ait_tmux_pane_for_pid (t1725_4) ==="
echo ""

# A pane whose process stays alive AND has a child we can name, plus a second
# session whose name carries `|`.
tmux -L "$SOCK" new-session -d -s plain -x 80 -y 10 \
    "sh -c 'sleep 300 & echo \$! > \"$TMP/child.pid\"; wait'" 2>/dev/null
tmux -L "$SOCK" new-session -d -s 'a|b' -x 80 -y 10 "sleep 300" 2>/dev/null

PANE_PID=""
for _ in $(seq 1 50); do
    PANE_PID="$(tmux_pane_pid plain)"
    [[ -n "$PANE_PID" && -s "$TMP/child.pid" ]] && break
    sleep 0.1
done
CHILD_PID="$(cat "$TMP/child.pid" 2>/dev/null)"
if [[ -z "$PANE_PID" || -z "$CHILD_PID" ]]; then
    echo "FAIL: could not start the test panes (pane pid='$PANE_PID', child pid='$CHILD_PID')"
    echo ""
    echo "Results: $PASS passed, 1 failed, $((TOTAL + 1)) total"
    echo "SOME TESTS FAILED"
    exit 1
fi
EXPECT="$(tmux_line plain)"

echo "--- 1: the pane's own pid ---"
out="$(resolve "$PANE_PID")"; rc=$?
assert_eq "1a. exit 0" "0" "$rc"
assert_eq "1b. the WHOLE line, as tmux renders it" "$EXPECT" "$out"

echo "--- 2: a descendant, via the walk ---"
TOTAL=$((TOTAL + 1))
if [[ "$CHILD_PID" != "$PANE_PID" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1)); echo "FAIL: 2a. the child IS the pane process - the walk would not be exercised"
fi
out="$(resolve "$CHILD_PID")"; rc=$?
assert_eq "2b. exit 0" "0" "$rc"
assert_eq "2c. resolves to the pane that owns it" "$EXPECT" "$out"

echo "--- 3: a pid no gateway pane owns ---"
out="$(resolve "$$")"; rc=$?
assert_eq "3a. exit 1" "1" "$rc"
assert_eq "3b. no output" "" "$out"

echo "--- 4: malformed pids ---"
for bad in "" abc 0 -5 1.5 "12 34"; do
    out="$(resolve "$bad")"; rc=$?
    assert_eq "4. '$bad' exits 1" "1" "$rc"
    assert_eq "4. '$bad' prints nothing" "" "$out"
done

echo "--- 5: a session name carrying '|' ---"
AB_PID="$(tmux_pane_pid 'a|b')"
out="$(resolve "$AB_PID")"; rc=$?
assert_eq "5a. exit 0" "0" "$rc"
assert_eq "5b. the line tmux renders, '|' intact" "$(tmux_line 'a|b')" "$out"
assert_contains "5c. the target names the session verbatim" $'\ta|b:@' "$out"

echo "--- 6: negative control - a socket nothing serves ---"
tmux -L "$NOSRV" list-sessions >/dev/null 2>&1; nosrv_rc=$?
assert_eq "6a. precondition: no server answers on the control socket" "1" "$((nosrv_rc != 0))"
out="$(AITASKS_TMUX_SOCKET="$NOSRV" ait_tmux_pane_for_pid "$PANE_PID")"; rc=$?
assert_eq "6b. case 1's pid does not resolve there" "1" "$rc"
assert_eq "6c. no output" "" "$out"

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ "$FAIL" -eq 0 ]]; then
    echo "ALL TESTS PASSED"
    exit 0
fi
echo "SOME TESTS FAILED"
exit 1
