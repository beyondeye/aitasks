#!/usr/bin/env bash
# test_monitor_server_restart_hook.sh — the `ait upgrade` hook that restarts the
# monitor status servers started from the upgraded tree (t2246):
# aitask_setup.sh:report_monitor_server_restart, called by install.sh.
#
# Drives the REAL function (sourced from aitask_setup.sh --source-only) against
# REAL fake-server processes (tests/lib/fake_status_server.py) in a scratch
# XDG_RUNTIME_DIR. The function's SCRIPT_DIR is pointed at a scratch tree whose
# monitor/status_server.py IS the fake server script, so a fake started from it
# carries that tree's owner path in its argv — exactly how a real server names
# the tree it was started from.
#
# Pins: only servers owned by the scratch tree are stopped (another tree's
# survives untouched), a stale socket is silent, a server that ignores SIGTERM
# is reported with a hint and left alive, AIT_MONITOR_RESTART=0 does nothing,
# and a missing python is reported, never fatal.
#
# Run: bash tests/test_monitor_server_restart_hook.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

if ! command -v ps >/dev/null 2>&1 || ! command -v python3 >/dev/null 2>&1; then
    echo "SKIP: ps and python3 are required"
    exit 0
fi
PY="$(command -v python3)"
FAKE="$PROJECT_DIR/tests/lib/fake_status_server.py"

TMP="$(mktemp -d /tmp/ait2246h.XXXXXX)" || exit 1
PIDS=()
cleanup() {
    local p
    for p in ${PIDS[@]+"${PIDS[@]}"}; do
        kill -9 "$p" 2>/dev/null
        wait "$p" 2>/dev/null
    done
    rm -rf "$TMP"
}
trap cleanup EXIT

TREE="$TMP/proj/.aitask-scripts"
mkdir -p "$TREE/monitor"
cp "$PROJECT_DIR/.aitask-scripts/monitor/status_restart.py" \
   "$PROJECT_DIR/.aitask-scripts/monitor/status_paths.py" "$TREE/monitor/"
cp "$FAKE" "$TREE/monitor/status_server.py"     # the scratch tree's owner path

export XDG_RUNTIME_DIR="$TMP/xdg"
RUN="$XDG_RUNTIME_DIR/aitasks"
mkdir -p "$RUN"
chmod 700 "$XDG_RUNTIME_DIR" "$RUN"
MINE_KEY="0123456789abcdef"
THEIRS_KEY="fedcba9876543210"

# start_fake <script> <socket> [mode] — start a fake server, wait for READY,
# set STARTED_PID.
start_fake() {
    local script="$1" sock="$2" mode="${3:-graceful}" ready="$TMP/ready.$RANDOM$RANDOM" i
    "$PY" "$script" serve --socket "$sock" --mode "$mode" >"$ready" 2>/dev/null &
    STARTED_PID=$!
    PIDS+=("$STARTED_PID")
    for ((i = 0; i < 100; i++)); do
        grep -q READY "$ready" 2>/dev/null && return 0
        sleep 0.05
    done
    echo "FAIL: fake server on $sock never became ready"
    return 1
}

# alive <pid> — running and not a zombie (a reaped-later child still answers kill -0).
alive() {
    local args
    args="$(ps -ww -o args= -p "$1" 2>/dev/null)" || return 1
    [[ -n "$args" && "$args" != *"<defunct>"* ]]
}

# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" --source-only
# Sourcing turns errexit/nounset ON in this shell; relax them as the sibling
# setup tests do, so a failing probe reports instead of aborting the suite.
set +eu
SCRIPT_DIR="$TREE"
# shellcheck disable=SC2034  # read by the sourced report_monitor_server_restart
VENV_DIR="$TMP/no-venv"          # no venv: the function falls back to resolve_python
export AIT_PYTHON="$PY"
unset _AIT_RESOLVED_PYTHON

echo "=== monitor status server restart hook (t2246) ==="

echo ""
echo "--- 1: only servers started from this tree are stopped ---"
MINE_SOCK="$RUN/monitor-$MINE_KEY-9.9.9.sock"
THEIRS_SOCK="$RUN/monitor-$THEIRS_KEY-9.9.9.sock"
STALE_SOCK="$RUN/monitor-$MINE_KEY-8.8.8.sock"
start_fake "$TREE/monitor/status_server.py" "$MINE_SOCK" || exit 1
MINE=$STARTED_PID
start_fake "$FAKE" "$THEIRS_SOCK" || exit 1
THEIRS=$STARTED_PID
"$PY" -c 'import socket,sys; s=socket.socket(socket.AF_UNIX); s.bind(sys.argv[1]); s.close()' "$STALE_SOCK"
out="$(report_monitor_server_restart)"
assert_eq "1: exactly the owned server is reported" \
    "MONITOR_SERVER:RETIRED:$MINE_SOCK|pid=$MINE" "$out"
if alive "$MINE"; then
    assert_eq "1: the owned server is gone" "gone" "alive"
else
    assert_eq "1: the owned server is gone" "gone" "gone"
fi
if alive "$THEIRS"; then
    assert_eq "1: another tree's server survives" "alive" "alive"
else
    assert_eq "1: another tree's server survives" "alive" "gone"
fi

echo ""
echo "--- 2: AIT_MONITOR_RESTART=0 does nothing ---"
start_fake "$TREE/monitor/status_server.py" "$MINE_SOCK" || exit 1
MINE2=$STARTED_PID
out="$(AIT_MONITOR_RESTART=0 report_monitor_server_restart)"
assert_eq "2: no output" "" "$out"
if alive "$MINE2"; then
    assert_eq "2: the owned server is untouched" "alive" "alive"
else
    assert_eq "2: the owned server is untouched" "alive" "gone"
fi

echo ""
echo "--- 3: a server that ignores SIGTERM is reported, with a hint, and left alive ---"
kill -9 "$MINE2" 2>/dev/null
wait "$MINE2" 2>/dev/null
rm -f "$MINE_SOCK"
start_fake "$TREE/monitor/status_server.py" "$MINE_SOCK" hung || exit 1
HUNG=$STARTED_PID
out="$(report_monitor_server_restart)"
assert_contains "3: the failure is reported" \
    "MONITOR_SERVER:RETIRE_FAILED:$MINE_SOCK|pid=$HUNG|still_running" "$out"
assert_contains "3: with the manual-recovery hint" "MONITOR_SERVER:hint:" "$out"
if alive "$HUNG"; then
    assert_eq "3: never force-killed" "alive" "alive"
else
    assert_eq "3: never force-killed" "alive" "gone"
fi

echo ""
echo "--- 4: no python is reported, not fatal ---"
resolve_python() { :; }
out="$(report_monitor_server_restart)"
rc=$?
assert_eq "4: exit status 0" "0" "$rc"
assert_eq "4: skipped line" "MONITOR_SERVER:skipped:no_python" "$out"

echo ""
echo "--- 5: a helper that cannot run is reported, never read as 'nothing to do' ---"
# The shape found while verifying: a resolved interpreter that is a shim to a
# missing venv exits 127 with no protocol output.
printf '#!/bin/sh\nexit 127\n' > "$TMP/broken-python"
chmod +x "$TMP/broken-python"
resolve_python() { echo "$TMP/broken-python"; }
out="$(report_monitor_server_restart)"
rc=$?
assert_eq "5: exit status 0 (never fatal)" "0" "$rc"
assert_contains "5: failure line" "MONITOR_SERVER:failed:helper_exit_127" "$out"
assert_contains "5: with the manual-recovery hint" "MONITOR_SERVER:hint:" "$out"

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]] || exit 1
