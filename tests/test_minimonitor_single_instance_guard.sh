#!/usr/bin/env bash
# test_minimonitor_single_instance_guard.sh — aitask_minimonitor.sh's
# single-instance guard, against a live (isolated) tmux server (t1451).
#
# The guard used to match `#{pane_current_command}` against `minimonitor` /
# `monitor_app`, but a live minimonitor pane reports `python`, so it could never
# fire. It now reads the `@aitask_monitor_kind` marker each app stamps on
# itself, and decides liveness by exec'ing `lib/monitor_marker.py` rather than
# reimplementing the rule in shell.
#
# States covered:
#   (i)   live-marked sibling            -> blocks
#   (ii)  dead-pid sibling               -> proceeds, marker self-healed
#   (iii) `garbage:123` sibling          -> blocks, marker LEFT ALONE
#         (the shell-side parity case: a hand-rolled `${marker##*:}` + `kill -0`
#         reads it as a dead pid and would clear it)
#   (iv)  no marked sibling              -> proceeds
#   (v)   live-marked sibling + a broken marker check (exit 1 / 2 / 127 / a real
#         missing file) -> blocks with a DISTINCT message, marker LEFT ALONE.
#         The `exit 1` variant is the one that would previously have cleared a
#         live marker, since an uncaught Python exception exits 1.
#
# Fault injection goes through $AIT_PYTHON — `python_resolve.sh` documents it as
# the explicit interpreter override and tries it first. A $PATH shim would never
# be reached (the venv path is checked before $PATH), and a bare `true` would
# fail `require_ait_python`'s version probe before the guard ever runs — so the
# shim DELEGATES to the real interpreter and misbehaves only for the one call
# under test. `MARKER_TOOL` inside the script is deliberately not overridable.
#
# Run: bash tests/test_minimonitor_single_instance_guard.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
# shellcheck source=lib/tmux_isolation.sh
. "$PROJECT_DIR/tests/lib/tmux_isolation.sh"
require_isolated_tmux

PASS=0
FAIL=0
TOTAL=0

GUARD="$PROJECT_DIR/.aitask-scripts/aitask_minimonitor.sh"
BLOCK_MSG="A monitor is already running in this window"
FAULT_MSG="Could not classify the monitor marker"

command -v tmux >/dev/null 2>&1 || { echo "SKIP: tmux not installed"; exit 0; }

FIXTURE_DIR="$(mktemp -d)"
export TMUX_TMPDIR="$FIXTURE_DIR/tmux"
mkdir -p "$TMUX_TMPDIR"
SESSION="t1451guard"

cleanup() {
    tmux kill-server 2>/dev/null || true
    rm -rf "$FIXTURE_DIR"
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# The delegating interpreter shim (see the header).
# ---------------------------------------------------------------------------
# Resolve the interpreter the same way the script under test will, then hand it
# to the shim. python_resolve.sh is a sourced lib, never executed.
# shellcheck source=../.aitask-scripts/lib/python_resolve.sh disable=SC1091
AIT_PYTHON="" . "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"
REAL_PYTHON="$(resolve_python)"
if [[ -z "$REAL_PYTHON" ]]; then
    echo "SKIP: no usable python interpreter"; exit 0
fi

SHIM="$FIXTURE_DIR/python_shim"
cat > "$SHIM" <<'SHIM_EOF'
#!/usr/bin/env bash
# Test-only interpreter shim. Delegates to the real interpreter unless told to
# misbehave for one specific call. Nothing in production reads these env vars.
real="$AIT_TEST_REAL_PYTHON"
for arg in "$@"; do
    case "$arg" in
        *monitor_marker.py)
            case "${AIT_TEST_MARKER_FAULT:-}" in
                exit:*) exit "${AIT_TEST_MARKER_FAULT#exit:}" ;;
                missing)
                    # Delegate with the script path rewritten to a file that
                    # does not exist, so the REAL "can't open file" status is
                    # observed rather than assumed.
                    args=()
                    for a in "$@"; do
                        case "$a" in
                            *monitor_marker.py) a="$AIT_TEST_MISSING_PATH" ;;
                        esac
                        args+=("$a")
                    done
                    exec "$real" "${args[@]}"
                    ;;
            esac
            ;;
        *minimonitor_app.py)
            # Witness that the script reached its final `exec`, so a
            # "no block message" assertion cannot pass vacuously because the
            # script died somewhere earlier.
            [[ -n "${AIT_TEST_LAUNCH_WITNESS:-}" ]] && : > "$AIT_TEST_LAUNCH_WITNESS"
            [[ -n "${AIT_TEST_NO_LAUNCH:-}" ]] && exit 0
            ;;
    esac
done
exec "$real" "$@"
SHIM_EOF
chmod +x "$SHIM"

export AIT_TEST_REAL_PYTHON="$REAL_PYTHON"
export AIT_TEST_MISSING_PATH="$FIXTURE_DIR/definitely_absent.py"
export AIT_PYTHON="$SHIM"

# ---------------------------------------------------------------------------
# Fixture: one window, two panes. Pane A is "us" (the launching pane), pane B is
# the sibling we stamp.
# ---------------------------------------------------------------------------
setup_window() {
    tmux kill-session -t "=$SESSION" 2>/dev/null || true
    tmux new-session -d -s "$SESSION" -n guardwin "sleep 600"
    tmux split-window -t "=$SESSION:guardwin" "sleep 600"
    mapfile -t PANES < <(tmux list-panes -t "=$SESSION:guardwin" -F '#{pane_id}')
    SELF_PANE="${PANES[0]}"
    SIBLING="${PANES[1]}"
    SOCKET_PATH="$(tmux display-message -p -t "=$SESSION" '#{socket_path}')"
    SERVER_PID="$(tmux display-message -p -t "=$SESSION" '#{pid}')"
    export TMUX="$SOCKET_PATH,$SERVER_PID,0"
    export TMUX_PANE="$SELF_PANE"
}

mark() { tmux set-option -p -t "$2" @aitask_monitor_kind "$1"; }
read_mark() {
    tmux show-options -pqv -t "$1" @aitask_monitor_kind 2>/dev/null || true
}

WITNESS="$FIXTURE_DIR/launched"
export AIT_TEST_LAUNCH_WITNESS="$WITNESS"

# Runs the guard with a fresh witness. `launched` reports whether the script
# reached its final `exec` — the positive control for every "no block message"
# assertion, which would otherwise also pass if the script died early.
run_guard() { rm -f "$WITNESS"; env "$@" bash "$GUARD" 2>&1; }
launched() { [ -e "$WITNESS" ] && echo yes || echo no; }

dead_pid() {
    # Spawn and reap — never guess a number.
    ( exec true ) & local p=$!; wait "$p" 2>/dev/null || true; echo "$p"
}

# ============================================================
echo "--- (i) a live-marked sibling blocks the launch ---"
setup_window
mark "minimonitor:$$" "$SIBLING"
out="$(run_guard AIT_TEST_NO_LAUNCH=1)"
assert_contains "live marker blocks" "$BLOCK_MSG" "$out"
assert_eq "blocked run never reaches exec" "no" "$(launched)"
assert_contains "marker survives a block" "minimonitor:$$" "$(read_mark "$SIBLING")"

# ============================================================
echo "--- (ii) a dead-pid sibling proceeds and is self-healed ---"
setup_window
DEAD="$(dead_pid)"
mark "minimonitor:$DEAD" "$SIBLING"
out="$(run_guard AIT_TEST_NO_LAUNCH=1)"
assert_not_contains "stale marker does not block" "$BLOCK_MSG" "$out"
assert_eq "stale run reaches exec" "yes" "$(launched)"
assert_eq "stale marker is cleared" "" "$(read_mark "$SIBLING")"

# ============================================================
echo "--- (iii) a malformed-but-numeric marker blocks and is NOT cleared ---"
# The shell-parity case. `${marker##*:}` yields 123; if that pid happens to be
# dead, a hand-rolled shell rule clears the marker and lets a second monitor
# start. monitor_marker.py classifies an unknown kind as unverifiable => present.
setup_window
mark "garbage:123" "$SIBLING"
out="$(run_guard AIT_TEST_NO_LAUNCH=1)"
assert_contains "unverifiable marker blocks" "$BLOCK_MSG" "$out"
assert_eq "unverifiable run never reaches exec" "no" "$(launched)"
assert_eq "unverifiable marker is left alone" "garbage:123" "$(read_mark "$SIBLING")"

# ============================================================
echo "--- (iv) no marked sibling proceeds ---"
setup_window
out="$(run_guard AIT_TEST_NO_LAUNCH=1)"
assert_not_contains "unmarked window does not block" "$BLOCK_MSG" "$out"
# Positive control: proves the absence above is the guard passing, not the
# script dying before it.
assert_eq "unmarked run reaches exec" "yes" "$(launched)"

# ============================================================
echo "--- (v) a broken marker check blocks (fail-safe), marker untouched ---"
# Only the two verified verdicts (11 absent / 10 stale) may proceed. Every other
# status means the marker was never classified.
for fault in "exit:1" "exit:2" "exit:127" "missing"; do
    setup_window
    mark "minimonitor:$$" "$SIBLING"
    out="$(run_guard AIT_TEST_NO_LAUNCH=1 "AIT_TEST_MARKER_FAULT=$fault")"
    assert_contains "fault '$fault' blocks the launch" "$FAULT_MSG" "$out"
    assert_not_contains "fault '$fault' does not claim a real monitor" \
        "$BLOCK_MSG" "$out"
    assert_eq "fault '$fault' never reaches exec" "no" "$(launched)"
    assert_eq "fault '$fault' leaves the marker untouched" \
        "minimonitor:$$" "$(read_mark "$SIBLING")"
done

# ============================================================
echo ""
echo "============================================"
echo "Results: $PASS passed, $FAIL failed (of $TOTAL)"
echo "============================================"
[ "$FAIL" -eq 0 ] || exit 1
