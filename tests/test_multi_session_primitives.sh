#!/usr/bin/env bash
# test_multi_session_primitives.sh - Verify the discovery and cross-session
# focus primitives added in t634_1 for multi-session aitasks support.
#
# Covers:
#   * AitasksSession dataclass shape
#   * discover_aitasks_sessions() pane-cwd heuristic
#   * discover_aitasks_sessions() registry fallback (AITASKS_PROJECT_<sess>)
#   * discover_aitasks_sessions() excludes non-aitasks sessions
#   * switch_to_pane_anywhere() call ordering (mock-based)
#   * switch_to_pane_anywhere() returns False cleanly on tmux error
#
# Run: bash tests/test_multi_session_primitives.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LIB_DIR="$PROJECT_DIR/.aitask-scripts/lib"

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

assert_contains() {
    local desc="$1" needle="$2" haystack="$3"
    TOTAL=$((TOTAL + 1))
    if [[ "$haystack" == *"$needle"* ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected to contain '$needle', got '$haystack')"
    fi
}

# --- Tier 1: Python helpers (always run) ---

out=$(PYTHONPATH="$LIB_DIR" python3 -c "
import inspect
import agent_launch_utils as u
from dataclasses import fields

f = {fld.name for fld in fields(u.AitasksSession)}
print('FIELDS:' + ','.join(sorted(f)))
print('FROZEN:' + str(u.AitasksSession.__dataclass_params__.frozen))
print('DISCOVER_CALLABLE:' + str(callable(u.discover_aitasks_sessions)))
print('SWITCH_CALLABLE:' + str(callable(u.switch_to_pane_anywhere)))
# Signature sanity: switch_to_pane_anywhere takes a single positional arg.
print('SWITCH_PARAMS:' + ','.join(inspect.signature(u.switch_to_pane_anywhere).parameters))
")
mapfile -t lines <<<"$out"
assert_eq "AitasksSession fields" "FIELDS:project_name,project_root,session" "${lines[0]:-}"
assert_eq "AitasksSession is frozen" "FROZEN:True" "${lines[1]:-}"
assert_eq "discover_aitasks_sessions callable" "DISCOVER_CALLABLE:True" "${lines[2]:-}"
assert_eq "switch_to_pane_anywhere callable" "SWITCH_CALLABLE:True" "${lines[3]:-}"
assert_eq "switch_to_pane_anywhere signature" "SWITCH_PARAMS:pane_id" "${lines[4]:-}"

# --- Tier 1b: switch_to_pane_anywhere call ordering (mock-based, no tmux) ---

out=$(PYTHONPATH="$LIB_DIR" python3 <<'PY'
import subprocess
from unittest.mock import patch, MagicMock
import agent_launch_utils as u

calls = []

def fake_run(cmd, *args, **kwargs):
    calls.append(cmd)
    result = MagicMock()
    result.returncode = 0
    # display-message calls read the format string from position 4.
    if len(cmd) >= 4 and cmd[1] == "display-message":
        fmt = cmd[-1]
        if fmt == "#{session_name}":
            result.stdout = "mysess\n"
        elif fmt == "#{window_index}":
            result.stdout = "2\n"
        else:
            result.stdout = ""
    else:
        result.stdout = ""
    return result

with patch.object(subprocess, "run", side_effect=fake_run):
    ok = u.switch_to_pane_anywhere("%42")

print("OK:" + str(ok))
print("NCALLS:" + str(len(calls)))
print("CMD0:" + " ".join(calls[0][1:]) if calls else "CMD0:")
print("CMD1:" + " ".join(calls[1][1:]) if len(calls) > 1 else "CMD1:")
print("CMD2:" + " ".join(calls[2][1:]) if len(calls) > 2 else "CMD2:")
print("CMD3:" + " ".join(calls[3][1:]) if len(calls) > 3 else "CMD3:")
print("CMD4:" + " ".join(calls[4][1:]) if len(calls) > 4 else "CMD4:")
PY
)
mapfile -t lines <<<"$out"
assert_eq "switch_to_pane_anywhere returns True on happy path" "OK:True" "${lines[0]:-}"
assert_eq "issues 5 tmux calls"                                 "NCALLS:5" "${lines[1]:-}"
assert_contains "call 0 is display-message session"  "display-message -p -t %42 #{session_name}" "${lines[2]:-}"
assert_contains "call 1 is display-message window"   "display-message -p -t %42 #{window_index}" "${lines[3]:-}"
assert_contains "call 2 is switch-client"            "switch-client -t =mysess" "${lines[4]:-}"
assert_contains "call 3 is select-window"            "select-window -t =mysess:2" "${lines[5]:-}"
assert_contains "call 4 is select-pane"              "select-pane -t %42" "${lines[6]:-}"

# switch_to_pane_anywhere returns False cleanly when tmux is unavailable.
out=$(PYTHONPATH="$LIB_DIR" python3 <<'PY'
import subprocess
from unittest.mock import patch
import agent_launch_utils as u

with patch.object(subprocess, "run", side_effect=FileNotFoundError("tmux")):
    print("OK:" + str(u.switch_to_pane_anywhere("%0")))
PY
)
assert_eq "switch_to_pane_anywhere returns False when tmux missing" "OK:False" "$out"

# --- Tier 2: Real tmux behavior (skip cleanly if tmux missing or unusable) ---

if ! command -v tmux >/dev/null 2>&1; then
    echo "SKIP: tmux not installed — skipping runtime assertions"
else
    TEST_TMUX_DIR=$(mktemp -d "${TMPDIR:-/tmp}/ait_multisess_test_XXXXXX")
    export TMUX_TMPDIR="$TEST_TMUX_DIR"
    # Unset TMUX so nested invocations don't refuse.
    unset TMUX

    FAKE_PROJ=$(mktemp -d "${TMPDIR:-/tmp}/ait_fake_proj_XXXXXX")
    # Canonicalize: macOS TMPDIR has a trailing slash (so mktemp leaves
    # a `//`) and tmux's pane_current_path resolves /var/folders to
    # /private/var/folders. `cd && pwd -P` collapses both so the expected
    # value matches what discover_aitasks_sessions() returns.
    FAKE_PROJ=$(cd "$FAKE_PROJ" && pwd -P)
    mkdir -p "$FAKE_PROJ/aitasks/metadata"
    : > "$FAKE_PROJ/aitasks/metadata/project_config.yaml"

    PFX_A="aittest_${$}_a"
    PFX_B="aittest_${$}_b"

    # shellcheck disable=SC2329  # invoked via trap
    cleanup() {
        tmux kill-server 2>/dev/null || true
        rm -rf "$TEST_TMUX_DIR" "$FAKE_PROJ"
    }
    trap cleanup EXIT

    if ! tmux new-session -d -s "$PFX_A" -c "$FAKE_PROJ" -n stub 'sleep 300' 2>/dev/null; then
        echo "SKIP: could not start test tmux session — skipping runtime assertions"
    else
        # Start a non-aitasks session rooted in /tmp (no aitasks metadata).
        tmux new-session -d -s "$PFX_B" -c /tmp -n stub 'sleep 300'

        # Case 1: Pane-cwd walk-up detects PFX_A; PFX_B is excluded.
        out=$(TMUX_TMPDIR="$TEST_TMUX_DIR" PYTHONPATH="$LIB_DIR" python3 -c "
import agent_launch_utils as u
sessions = u.discover_aitasks_sessions()
for s in sessions:
    print('SESSION:' + s.session + ':' + str(s.project_root) + ':' + s.project_name)
print('COUNT:' + str(len(sessions)))
")
        assert_contains "discover_aitasks_sessions finds PFX_A via pane cwd" \
            "SESSION:${PFX_A}:${FAKE_PROJ}:$(basename "$FAKE_PROJ")" \
            "$out"
        assert_contains "non-aitasks session PFX_B is excluded" \
            "COUNT:1" \
            "$out"
        # Defensively ensure PFX_B is NOT in the output.
        if [[ "$out" == *"SESSION:${PFX_B}"* ]]; then
            FAIL=$((FAIL + 1))
            TOTAL=$((TOTAL + 1))
            echo "FAIL: non-aitasks session PFX_B leaked into discovery output"
        else
            PASS=$((PASS + 1))
            TOTAL=$((TOTAL + 1))
        fi

        # Case 2: Registry fallback — register PFX_B as aitasks-like.
        tmux set-environment -g "AITASKS_PROJECT_${PFX_B}" "$FAKE_PROJ"

        out=$(TMUX_TMPDIR="$TEST_TMUX_DIR" PYTHONPATH="$LIB_DIR" python3 -c "
import agent_launch_utils as u
sessions = u.discover_aitasks_sessions()
for s in sessions:
    print('SESSION:' + s.session + ':' + str(s.project_root))
print('COUNT:' + str(len(sessions)))
")
        assert_contains "registry fallback discovers PFX_B" \
            "SESSION:${PFX_B}:${FAKE_PROJ}" \
            "$out"
        assert_contains "both sessions now discovered" "COUNT:2" "$out"

        # Case 3: Sorted by session name (PFX_A < PFX_B lexicographically).
        first_line=$(TMUX_TMPDIR="$TEST_TMUX_DIR" PYTHONPATH="$LIB_DIR" python3 -c "
import agent_launch_utils as u
print(u.discover_aitasks_sessions()[0].session)
")
        assert_eq "discovery result sorted by session name" "$PFX_A" "$first_line"

        # Case 4: Registry entry pointing at a non-aitasks path is ignored.
        tmux set-environment -g -u "AITASKS_PROJECT_${PFX_B}"
        BOGUS_DIR=$(mktemp -d "${TMPDIR:-/tmp}/ait_bogus_XXXXXX")
        tmux set-environment -g "AITASKS_PROJECT_${PFX_B}" "$BOGUS_DIR"

        out=$(TMUX_TMPDIR="$TEST_TMUX_DIR" PYTHONPATH="$LIB_DIR" python3 -c "
import agent_launch_utils as u
sessions = u.discover_aitasks_sessions()
print('COUNT:' + str(len(sessions)))
")
        assert_contains "bogus registry value doesn't resurrect non-aitasks session" \
            "COUNT:1" "$out"
        rm -rf "$BOGUS_DIR"
    fi
fi

echo
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
if [[ $FAIL -eq 0 ]]; then
    exit 0
else
    exit 1
fi
