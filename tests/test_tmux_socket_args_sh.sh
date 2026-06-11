#!/usr/bin/env bash
# test_tmux_socket_args_sh.sh - Pins the SHELL gateway's socket-knob semantics
# (lib/tmux_exec.sh::ait_tmux_socket_args / ait_tmux_socket_name), mirroring
# tests/test_tmux_exec.py::TestSocketArgs for the Python gateway (t953):
#   * unset AITASKS_TMUX_SOCKET => `-L ait` (the dedicated default)
#   * non-empty               => `-L <value>` (`default` = explicit opt-out)
#   * set-but-empty/whitespace => no flag (legacy escape hatch)
# Pure string-level assertions — no tmux server is spawned.
# Run: bash tests/test_tmux_socket_args_sh.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

GATEWAY="$PROJECT_DIR/.aitask-scripts/lib/tmux_exec.sh"

# emit_args <env-spec> — run ait_tmux_socket_args in a fresh bash with the
# given env handling and join the emitted lines with '|'. env-spec is one of:
#   unset       — AITASKS_TMUX_SOCKET removed from the environment
#   <value>     — AITASKS_TMUX_SOCKET set to <value> (may be empty: pass "")
emit_args() {
    local spec="$1" fn="$2"
    if [[ "$spec" == "__UNSET__" ]]; then
        env -u AITASKS_TMUX_SOCKET bash -c \
            "source '$GATEWAY'; $fn | paste -sd'|' -"
    else
        AITASKS_TMUX_SOCKET="$spec" bash -c \
            "source '$GATEWAY'; $fn | paste -sd'|' -"
    fi
}

# --- ait_tmux_socket_args ---------------------------------------------------

assert_eq "unset env emits the dedicated ait socket" "-L|ait" "$(emit_args __UNSET__ ait_tmux_socket_args)"

assert_eq "non-empty value emits -L <value>" "-L|mysock" "$(emit_args mysock ait_tmux_socket_args)"

assert_eq "'default' opt-out emits -L default" "-L|default" "$(emit_args default ait_tmux_socket_args)"

assert_eq "set-but-empty emits no flag (legacy escape hatch)" "" "$(emit_args "" ait_tmux_socket_args)"

assert_eq "whitespace-only emits no flag (matches Python .strip())" "" "$(emit_args "   " ait_tmux_socket_args)"

# --- ait_tmux_socket_name ---------------------------------------------------

assert_eq "unset env resolves socket name 'ait'" "ait" "$(emit_args __UNSET__ ait_tmux_socket_name)"

assert_eq "non-empty value resolves verbatim" "mysock" "$(emit_args mysock ait_tmux_socket_name)"

assert_eq "set-but-empty resolves to empty (no-flag escape hatch)" "" "$(emit_args "" ait_tmux_socket_name)"

# --- Python-mirror parity ----------------------------------------------------
# The two gateways must agree on every spelling of the knob. Compare the shell
# emitter against tmux_exec.tmux_socket_args for each case.
PYTHON_BIN="${PYTHON_BIN:-python3}"
if command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    py_args() {
        local spec="$1"
        if [[ "$spec" == "__UNSET__" ]]; then
            env -u AITASKS_TMUX_SOCKET "$PYTHON_BIN" -c \
                "import sys; sys.path.insert(0, '$PROJECT_DIR/.aitask-scripts/lib'); import tmux_exec; print('|'.join(tmux_exec.tmux_socket_args()))"
        else
            AITASKS_TMUX_SOCKET="$spec" "$PYTHON_BIN" -c \
                "import sys; sys.path.insert(0, '$PROJECT_DIR/.aitask-scripts/lib'); import tmux_exec; print('|'.join(tmux_exec.tmux_socket_args()))"
        fi
    }
    for spec in __UNSET__ mysock default "" "   "; do
        label="${spec:-<empty>}"
        [[ "$spec" == "__UNSET__" ]] && label="<unset>"
        assert_eq "shell/python parity for $label" \
            "$(py_args "$spec")" "$(emit_args "$spec" ait_tmux_socket_args)"
    done
else
    echo "SKIP: $PYTHON_BIN not available — parity cases skipped"
fi

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
echo "ALL TESTS PASSED"
