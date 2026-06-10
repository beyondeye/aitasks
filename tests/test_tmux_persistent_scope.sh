#!/usr/bin/env bash
# test_tmux_persistent_scope.sh - Verify the t943 persistent-scope tmux spawn.
#
# Covers ait_systemd_user_available / ait_tmux_new_session_persistent in
# .aitask-scripts/lib/terminal_compat.sh:
#   * Tier 1 (always-on, fallback rung): with AIT_NO_SYSTEMD_RUN=1 the helper
#     degrades to setsid / plain tmux and STILL creates the detached session
#     with the requested name / cwd / window / command — i.e. the fallback
#     preserves today's behavior. Exercises the real helper end-to-end.
#   * Tier 2 (systemd-guarded): when a systemd --user manager is reachable,
#     the systemd-run invocation lands the new tmux SERVER under session.slice
#     (escaping app.slice) and NOT under app.slice — the load-bearing property.
#     CI runners typically have no reachable user manager, so this tier skips
#     there and only the fallback rung runs.
#
# Run: bash tests/test_tmux_persistent_scope.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Shared assertion helpers (see tests/lib/asserts.sh).
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

# Make the user's default-socket tmux server unreachable for this process, so a
# stray tmux call can never touch it (see tests/lib/tmux_isolation.sh).
# shellcheck source=lib/tmux_isolation.sh
. "$SCRIPT_DIR/lib/tmux_isolation.sh"
require_isolated_tmux

PASS=0
FAIL=0
TOTAL=0

# Unit under test.
# shellcheck source=../.aitask-scripts/lib/terminal_compat.sh
. "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh"

# --- Shared cleanup (single trap; per-fixture dirs/units accumulate here) ---
CLEAN_TMUX_DIRS=()
CLEAN_UNITS=()
CLEAN_PATHS=()
cleanup() {
    for d in "${CLEAN_TMUX_DIRS[@]}"; do
        TMUX_TMPDIR="$d" tmux kill-server 2>/dev/null || true
    done
    for u in "${CLEAN_UNITS[@]}"; do
        systemctl --user stop "$u" 2>/dev/null || true
        systemctl --user reset-failed "$u" 2>/dev/null || true
    done
    for p in "${CLEAN_PATHS[@]}"; do
        rm -rf "$p" 2>/dev/null || true
    done
}
trap cleanup EXIT

# --- Tier 0: helper presence (always runs) ---

defined=no
declare -f ait_tmux_new_session_persistent >/dev/null 2>&1 && defined=yes
assert_eq "ait_tmux_new_session_persistent is defined" "yes" "$defined"

defined=no
declare -f ait_systemd_user_available >/dev/null 2>&1 && defined=yes
assert_eq "ait_systemd_user_available is defined" "yes" "$defined"

# --- Tier 1: fallback rung (always runs when tmux is present) ---

if ! command -v tmux >/dev/null 2>&1; then
    echo "SKIP: tmux not installed — skipping fallback-rung assertions"
else
    T1_DIR=$(mktemp -d "${TMPDIR:-/tmp}/ait_tmux_test_XXXXXX")
    T1_ROOT=$(cd "$(mktemp -d)" && pwd -P)
    CLEAN_TMUX_DIRS+=("$T1_DIR")
    CLEAN_PATHS+=("$T1_DIR" "$T1_ROOT")
    export TMUX_TMPDIR="$T1_DIR"
    unset TMUX
    SESSION1="aitpersist_$$"

    # AIT_NO_SYSTEMD_RUN=1 forces the fallback rung (setsid / plain tmux), which
    # honors TMUX_TMPDIR and so lands on this fixture's isolated socket. The
    # if-form captures the return code without tripping `set -e`.
    if AIT_NO_SYSTEMD_RUN=1 \
        ait_tmux_new_session_persistent "$SESSION1" "$T1_ROOT" monitor 'sleep 300'; then
        rc=0
    else
        rc=$?
    fi
    assert_eq "fallback-rung helper returns 0" "0" "$rc"

    assert_exit_zero "session '=$SESSION1' exists" tmux has-session -t "=$SESSION1"

    # Session-only targets do not resolve pane/window formats in display-message;
    # list-windows / list-panes are the reliable scripting form.
    win=$(tmux list-windows -t "=$SESSION1" -F '#{window_name}' 2>/dev/null | head -1)
    assert_eq "fallback preserves window name 'monitor'" "monitor" "$win"

    # pane_current_path is derived from the pane process's /proc cwd, which the
    # setsid fallback brings up asynchronously — it can momentarily read the
    # launcher's cwd before settling into -c <root>. Poll until it reflects the
    # requested root (window name / start command are tmux metadata, so they are
    # available immediately above and need no poll).
    cwd=""
    for _ in $(seq 1 15); do
        cwd=$(tmux list-panes -t "=$SESSION1" -F '#{pane_current_path}' 2>/dev/null | head -1)
        [[ "$cwd" == "$T1_ROOT" ]] && break
        sleep 0.2
    done
    assert_eq "fallback preserves pane cwd (root)" "$T1_ROOT" "$cwd"

    cmd=$(tmux list-panes -t "=$SESSION1" -F '#{pane_start_command}' 2>/dev/null | head -1)
    assert_contains "fallback preserves the launch command" "sleep 300" "$cmd"
fi

# --- Tier 2: systemd-guarded session.slice placement ---

if ! ait_systemd_user_available; then
    echo "SKIP: systemd --user unavailable — skipping session.slice placement assertions"
else
    T2_DIR=$(mktemp -d "${TMPDIR:-/tmp}/ait_tmux_slice_XXXXXX")
    T2_ROOT=$(cd "$(mktemp -d)" && pwd -P)
    SESSION2="aitslice_$$"
    UNIT2="ait-tmux-slicetest-$$-${RANDOM}"
    CLEAN_TMUX_DIRS+=("$T2_DIR")
    CLEAN_UNITS+=("$UNIT2")
    CLEAN_PATHS+=("$T2_DIR" "$T2_ROOT")

    # We reconstruct the systemd-run invocation the helper uses (same slice +
    # Type=forking / KillMode=none / --collect) rather than calling the helper
    # directly: the production helper intentionally does NOT thread TMUX_TMPDIR
    # (it must spawn on the default socket), so calling it here would create a
    # server on the USER's real tmux server. --setenv=TMUX_TMPDIR keeps the test
    # server on an isolated socket. This still verifies the load-bearing
    # property — session.slice placement — that the helper relies on.
    systemd-run --user --slice=session.slice --unit="$UNIT2" \
        --property=Type=forking --property=KillMode=none \
        --setenv=TMUX_TMPDIR="$T2_DIR" \
        --collect --quiet -- \
        tmux new-session -d -s "$SESSION2" -c "$T2_ROOT" -n monitor 'sleep 300' \
        || true

    # Type=forking: the daemon is tracked as MainPID once it has forked.
    pid=""
    for _ in 1 2 3 4 5 6 7 8 9 10; do
        pid=$(systemctl --user show -p MainPID --value "$UNIT2" 2>/dev/null)
        [[ -n "$pid" && "$pid" != "0" ]] && break
        sleep 0.2
    done

    if [[ -z "$pid" || "$pid" == "0" ]]; then
        FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1))
        echo "FAIL: systemd-run server MainPID resolved (got '$pid')"
    else
        cg=$(cat "/proc/$pid/cgroup" 2>/dev/null || true)
        assert_contains "server cgroup is under session.slice" "/session.slice/" "$cg"
        assert_not_contains "server cgroup escapes app.slice" "/app.slice/" "$cg"
    fi
fi

echo
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
exit $([[ $FAIL -eq 0 ]] && echo 0 || echo 1)
