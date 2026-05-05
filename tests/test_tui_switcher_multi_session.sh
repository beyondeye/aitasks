#!/usr/bin/env bash
# test_tui_switcher_multi_session.sh — Verify the multi-session extensions to
# TuiSwitcherOverlay added in t634_3.
#
# Covers:
#   * _init_multi_state: single-session vs multi-session multi_mode computation
#   * _cycle_session: Left/Right cycles _session (operating/selected), leaves
#     _attached_session untouched; SkipAction when not in multi mode
#   * _switch_to: same-session (regression, 1 Popen) vs cross-session (2 Popens,
#     select-window then switch-client)
#   * Shortcut keys act on the SELECTED session (not attached) — confirms the
#     user-clarified inversion of the task description's Step 4
#   * _teleport_if_cross: 0 calls when same, 1 call when cross
#   * Real tmux: two fake aitasks sessions discovered correctly
#
# Run: bash tests/test_tui_switcher_multi_session.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LIB_DIR="$PROJECT_DIR/.aitask-scripts/lib"

# shellcheck source=lib/venv_python.sh
. "$SCRIPT_DIR/lib/venv_python.sh"
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

# --- Tier 1: logic-level tests (no Textual runtime, no tmux) ---

out=$(PYTHONPATH="$LIB_DIR" "$AITASK_PYTHON" <<'PY'
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import tui_switcher as ts
from agent_launch_utils import AitasksSession


def make_overlay(session="s1", current_tui=""):
    return ts.TuiSwitcherOverlay(session=session, current_tui=current_tui)


def with_screen(ov, query_side_effect=None):
    """Return a context-manager that patches TuiSwitcherOverlay.screen to a mock."""
    mock_screen = MagicMock()
    if query_side_effect is not None:
        mock_screen.query_one.side_effect = query_side_effect
    else:
        mock_screen.query_one.return_value = MagicMock()
    return patch.object(
        ts.TuiSwitcherOverlay, "screen",
        new_callable=PropertyMock, return_value=mock_screen,
    )


# --- _init_multi_state ---

# Single-session (1 session): _multi_mode False
ov = make_overlay(session="s1")
ov._init_multi_state([AitasksSession("s1", Path("/p1"), "p1")])
print("SINGLE_MULTI_MODE:" + str(ov._multi_mode))
print("SINGLE_SESSION:" + ov._session)
print("SINGLE_ATTACHED:" + ov._attached_session)

# Multi-session (2 sessions, attached listed): _multi_mode True
ov = make_overlay(session="s1")
ov._init_multi_state([
    AitasksSession("s1", Path("/p1"), "p1"),
    AitasksSession("s2", Path("/p2"), "p2"),
])
print("MULTI_MULTI_MODE:" + str(ov._multi_mode))
print("MULTI_SESSION:" + ov._session)
print("MULTI_ATTACHED:" + ov._attached_session)

# 2 sessions but attached NOT listed (overlay opened outside aitasks): False
ov = make_overlay(session="elsewhere")
ov._init_multi_state([
    AitasksSession("s1", Path("/p1"), "p1"),
    AitasksSession("s2", Path("/p2"), "p2"),
])
print("OUTSIDE_MULTI_MODE:" + str(ov._multi_mode))


# --- _cycle_session: forward, back, wrap ---

ov = make_overlay(session="s1")
ov._all_sessions = [
    AitasksSession("s1", Path("/p1"), "p1"),
    AitasksSession("s2", Path("/p2"), "p2"),
]
ov._multi_mode = True
ov._render_session_row = MagicMock()
ov._populate_list_for = MagicMock()
with with_screen(ov):
    ov._cycle_session(+1)
print("CYCLE_FWD_SESSION:" + ov._session)
print("CYCLE_FWD_ATTACHED:" + ov._attached_session)
print("CYCLE_FWD_POPULATE_CALLS:" + str(ov._populate_list_for.call_count))
print("CYCLE_FWD_POPULATE_ARG:" + ov._populate_list_for.call_args[0][0])

with with_screen(ov):
    ov._cycle_session(-1)
print("CYCLE_BACK_SESSION:" + ov._session)

with with_screen(ov):
    ov._cycle_session(+1)
    ov._cycle_session(+1)
print("CYCLE_WRAP_SESSION:" + ov._session)


# --- _cycle_session SkipAction paths ---

from textual.actions import SkipAction

# Not multi-mode
ov = make_overlay(session="s1")
ov._multi_mode = False
try:
    with with_screen(ov):
        ov._cycle_session(+1)
    print("CYCLE_SINGLE_RAISED:no")
except SkipAction:
    print("CYCLE_SINGLE_RAISED:yes")

# Query fails -> SkipAction
ov = make_overlay(session="s1")
ov._multi_mode = True
ov._all_sessions = [
    AitasksSession("s1", Path("/p1"), "p1"),
    AitasksSession("s2", Path("/p2"), "p2"),
]
try:
    with with_screen(ov, query_side_effect=RuntimeError("no widget")):
        ov._cycle_session(+1)
    print("CYCLE_NOWIDGET_RAISED:no")
except SkipAction:
    print("CYCLE_NOWIDGET_RAISED:yes")


# --- _switch_to same-session (regression) ---

ov = make_overlay(session="s1")
ov._running_names = {"board"}
ov.dismiss = MagicMock()
with patch("tui_switcher.subprocess.Popen") as mock_popen:
    ov._switch_to("board", running=True, window_index="2")
    calls = [c.args[0] for c in mock_popen.call_args_list]
print("SAME_POPEN_COUNT:" + str(len(calls)))
print("SAME_POPEN_0:" + " ".join(calls[0]))


# --- _switch_to cross-session running=True ---

ov = make_overlay(session="s1")
ov._session = "s2"                  # browsed to s2
ov._running_names = {"board"}
ov.dismiss = MagicMock()
with patch("tui_switcher.subprocess.Popen") as mock_popen:
    ov._switch_to("board", running=True, window_index="2")
    calls = [c.args[0] for c in mock_popen.call_args_list]
print("CROSS_RUN_POPEN_COUNT:" + str(len(calls)))
print("CROSS_RUN_POPEN_0:" + " ".join(calls[0]))
print("CROSS_RUN_POPEN_1:" + " ".join(calls[1]))


# --- _switch_to cross-session running=False (new window) ---

ov = make_overlay(session="s1")
ov._session = "s2"
ov._all_sessions = [
    AitasksSession("s1", Path("/p1"), "p1"),
    AitasksSession("s2", Path("/p2"), "p2"),
]
ov._running_names = set()
ov.dismiss = MagicMock()
with patch("tui_switcher.subprocess.Popen") as mock_popen:
    ov._switch_to("codebrowser", running=False)
    calls = [c.args[0] for c in mock_popen.call_args_list]
print("CROSS_NEW_POPEN_COUNT:" + str(len(calls)))
print("CROSS_NEW_POPEN_0:" + " ".join(calls[0]))
print("CROSS_NEW_POPEN_1:" + " ".join(calls[1]))


# --- _switch_to same-session new-window (regression: -c <cwd> fallback) ---

ov = make_overlay(session="s1")
ov._all_sessions = []          # single-session mode → fallback to Path.cwd()
ov._running_names = set()
ov.dismiss = MagicMock()
with patch("tui_switcher.subprocess.Popen") as mock_popen:
    ov._switch_to("codebrowser", running=False)
    calls = [c.args[0] for c in mock_popen.call_args_list]
print("SAME_NEW_POPEN_0:" + " ".join(calls[0]))


# --- action_shortcut_explore cross-session ---

ov = make_overlay(session="s1")
ov._session = "s2"
ov._all_sessions = [
    AitasksSession("s1", Path("/p1"), "p1"),
    AitasksSession("s2", Path("/p2"), "p2"),
]
ov._running_names = set()
ov.dismiss = MagicMock()
with patch("tui_switcher.subprocess.Popen") as mock_popen, \
     patch("agent_launch_utils.maybe_spawn_minimonitor") as mock_mm:
    ov.action_shortcut_explore()
    calls = [c.args[0] for c in mock_popen.call_args_list]
    mm_kwargs = mock_mm.call_args.kwargs if mock_mm.call_args else {}
print("SHORTCUT_X_POPEN_0:" + " ".join(calls[0]))
print("SHORTCUT_X_MM_PROOT:" + str(mm_kwargs.get("project_root")))


# --- _teleport_if_cross ---

ov = make_overlay(session="s1")
with patch("tui_switcher.subprocess.Popen") as mock_popen:
    ov._teleport_if_cross()
print("TELEPORT_SAME_COUNT:" + str(mock_popen.call_count))

ov._session = "s2"
with patch("tui_switcher.subprocess.Popen") as mock_popen:
    ov._teleport_if_cross()
    teleport_args = mock_popen.call_args_list[0].args[0]
print("TELEPORT_CROSS_COUNT:" + str(mock_popen.call_count))
print("TELEPORT_CROSS_ARGS:" + " ".join(teleport_args))


# --- Shortcut acts on SELECTED session (user-clarified) ---

ov = make_overlay(session="s1", current_tui="monitor")
ov._session = "s2"                  # browsed to s2
ov._running_names = {"board"}       # board running in s2
ov.dismiss = MagicMock()
with patch("tui_switcher.subprocess.Popen") as mock_popen:
    ov.action_shortcut_board()
    calls = [c.args[0] for c in mock_popen.call_args_list]
print("SHORTCUT_B_POPEN_COUNT:" + str(len(calls)))
print("SHORTCUT_B_POPEN_0:" + " ".join(calls[0]))
print("SHORTCUT_B_POPEN_1:" + " ".join(calls[1]))


# --- Shortcut `n` (new task) acts on SELECTED session ---

ov = make_overlay(session="s1", current_tui="monitor")
ov._session = "s2"
ov._all_sessions = [
    AitasksSession("s1", Path("/p1"), "p1"),
    AitasksSession("s2", Path("/p2"), "p2"),
]
ov._running_names = set()
ov.dismiss = MagicMock()
with patch("tui_switcher.subprocess.Popen") as mock_popen, \
     patch("agent_launch_utils.maybe_spawn_minimonitor") as mock_mm:
    mock_popen.return_value.wait = MagicMock()
    ov.action_shortcut_create()
    calls = [c.args[0] for c in mock_popen.call_args_list]
    n_mm_kwargs = mock_mm.call_args.kwargs if mock_mm.call_args else {}
print("SHORTCUT_N_POPEN_COUNT:" + str(len(calls)))
print("SHORTCUT_N_POPEN_0:" + " ".join(calls[0]))
print("SHORTCUT_N_POPEN_LAST:" + " ".join(calls[-1]))
print("SHORTCUT_N_MM_PROOT:" + str(n_mm_kwargs.get("project_root")))


# --- Same-session shortcut on attached.current_tui: still a no-op ---

ov = make_overlay(session="s1", current_tui="board")
ov._running_names = {"board"}
ov.dismiss = MagicMock()
with patch("tui_switcher.subprocess.Popen") as mock_popen:
    ov.action_shortcut_board()
print("NOOP_POPEN_COUNT:" + str(mock_popen.call_count))
print("NOOP_DISMISSED:" + str(ov.dismiss.called))


# --- Same-target shortcut in BROWSED session: NOT a no-op (must teleport) ---

ov = make_overlay(session="s1", current_tui="board")
ov._session = "s2"                  # browsed to s2
ov._running_names = {"board"}       # board also running in s2
ov.dismiss = MagicMock()
with patch("tui_switcher.subprocess.Popen") as mock_popen:
    ov.action_shortcut_board()
    calls = [c.args[0] for c in mock_popen.call_args_list]
print("BROWSED_SAMENAME_COUNT:" + str(len(calls)))
if len(calls) >= 2:
    print("BROWSED_SAMENAME_LAST:" + " ".join(calls[-1]))
PY
)

mapfile -t lines <<<"$out"

declare -A R
for line in "${lines[@]}"; do
    key="${line%%:*}"
    val="${line#*:}"
    R["$key"]="$val"
done

assert_eq "single-session -> _multi_mode False" "False" "${R[SINGLE_MULTI_MODE]:-}"
assert_eq "single-session _session == attached" "s1" "${R[SINGLE_SESSION]:-}"
assert_eq "single-session _attached_session" "s1" "${R[SINGLE_ATTACHED]:-}"

assert_eq "multi-session -> _multi_mode True" "True" "${R[MULTI_MULTI_MODE]:-}"
assert_eq "multi-session _session initial" "s1" "${R[MULTI_SESSION]:-}"
assert_eq "multi-session _attached_session" "s1" "${R[MULTI_ATTACHED]:-}"

assert_eq "attached not in aitasks-sessions -> _multi_mode False" "False" "${R[OUTSIDE_MULTI_MODE]:-}"

assert_eq "cycle +1 mutates _session (s1 -> s2)" "s2" "${R[CYCLE_FWD_SESSION]:-}"
assert_eq "cycle +1 leaves _attached_session" "s1" "${R[CYCLE_FWD_ATTACHED]:-}"
assert_eq "cycle +1 calls _populate_list_for once" "1" "${R[CYCLE_FWD_POPULATE_CALLS]:-}"
assert_eq "cycle +1 populates for new selected" "s2" "${R[CYCLE_FWD_POPULATE_ARG]:-}"
assert_eq "cycle -1 returns to s1" "s1" "${R[CYCLE_BACK_SESSION]:-}"
assert_eq "cycle wrap (+1 twice from s1 via s2) returns to s1" "s1" "${R[CYCLE_WRAP_SESSION]:-}"

assert_eq "_cycle_session raises SkipAction when _multi_mode=False" "yes" "${R[CYCLE_SINGLE_RAISED]:-}"
assert_eq "_cycle_session raises SkipAction when query_one fails" "yes" "${R[CYCLE_NOWIDGET_RAISED]:-}"

assert_eq "same-session Enter: 1 Popen call (regression)" "1" "${R[SAME_POPEN_COUNT]:-}"
assert_contains "same-session Enter uses select-window with =s1:2" "select-window -t =s1:2" "${R[SAME_POPEN_0]:-}"

assert_eq "cross-session Enter running=True: 2 Popen calls" "2" "${R[CROSS_RUN_POPEN_COUNT]:-}"
assert_contains "cross Enter 1st = select-window =s2:2" "select-window -t =s2:2" "${R[CROSS_RUN_POPEN_0]:-}"
assert_contains "cross Enter 2nd = switch-client =s2" "switch-client -t =s2" "${R[CROSS_RUN_POPEN_1]:-}"

assert_eq "cross-session Enter new-window: 2 Popen calls" "2" "${R[CROSS_NEW_POPEN_COUNT]:-}"
assert_contains "cross new 1st = new-window -t =s2:" "new-window -t =s2:" "${R[CROSS_NEW_POPEN_0]:-}"
assert_contains "cross new 1st has -n codebrowser" "-n codebrowser" "${R[CROSS_NEW_POPEN_0]:-}"
assert_contains "cross new 1st passes -c /p2 (t649)" "-c /p2" "${R[CROSS_NEW_POPEN_0]:-}"
assert_contains "cross new 2nd = switch-client =s2" "switch-client -t =s2" "${R[CROSS_NEW_POPEN_1]:-}"

assert_contains "same-session new-window falls back to -c <cwd> (t649)" "-c $(pwd)" "${R[SAME_NEW_POPEN_0]:-}"

assert_contains "shortcut 'x' new-window targets =s2:" "new-window -t =s2:" "${R[SHORTCUT_X_POPEN_0]:-}"
assert_contains "shortcut 'x' has -n agent-explore-1" "-n agent-explore-1" "${R[SHORTCUT_X_POPEN_0]:-}"
assert_contains "shortcut 'x' passes -c /p2 (t649)" "-c /p2" "${R[SHORTCUT_X_POPEN_0]:-}"
assert_eq "shortcut 'x' threads project_root to minimonitor (t649)" "/p2" "${R[SHORTCUT_X_MM_PROOT]:-}"

assert_eq "_teleport_if_cross same-session: 0 Popen" "0" "${R[TELEPORT_SAME_COUNT]:-}"
assert_eq "_teleport_if_cross cross: 1 Popen" "1" "${R[TELEPORT_CROSS_COUNT]:-}"
assert_contains "_teleport_if_cross cross uses switch-client =s2" "switch-client -t =s2" "${R[TELEPORT_CROSS_ARGS]:-}"

assert_eq "shortcut 'b' browsed to s2 (running): 2 Popen calls" "2" "${R[SHORTCUT_B_POPEN_COUNT]:-}"
assert_contains "shortcut 'b' routes to s2, NOT attached s1" "select-window -t =s2:board" "${R[SHORTCUT_B_POPEN_0]:-}"
assert_contains "shortcut 'b' teleports to s2" "switch-client -t =s2" "${R[SHORTCUT_B_POPEN_1]:-}"

assert_contains "shortcut 'n' browsed to s2: new-window targets =s2:" "new-window -t =s2:" "${R[SHORTCUT_N_POPEN_0]:-}"
assert_contains "shortcut 'n' browsed to s2: passes -c /p2 (t649)" "-c /p2" "${R[SHORTCUT_N_POPEN_0]:-}"
assert_contains "shortcut 'n' browsed to s2: teleport switch-client =s2" "switch-client -t =s2" "${R[SHORTCUT_N_POPEN_LAST]:-}"
assert_eq "shortcut 'n' threads project_root to minimonitor (t649)" "/p2" "${R[SHORTCUT_N_MM_PROOT]:-}"

assert_eq "same-session shortcut on attached.current_tui: 0 Popen (no-op)" "0" "${R[NOOP_POPEN_COUNT]:-}"
assert_eq "same-session shortcut on attached.current_tui: no dismiss" "False" "${R[NOOP_DISMISSED]:-}"

assert_contains "browsed session shortcut on current_tui name: does NOT no-op — teleports" "switch-client -t =s2" "${R[BROWSED_SAMENAME_LAST]:-}"

# --- Tier 2: real tmux (skip cleanly if tmux missing) ---

if ! command -v tmux >/dev/null 2>&1; then
    echo "SKIP: tmux not available — Tier 2 skipped"
    echo ""
    echo "===================="
    echo "Passed: $PASS / $TOTAL"
    [[ $FAIL -gt 0 ]] && echo "Failed: $FAIL"
    if [[ $FAIL -gt 0 ]]; then
        exit 1
    else
        exit 0
    fi
fi

TMUX_TMPDIR_REAL="$(mktemp -d "${TMPDIR:-/tmp}/ait_switcher_tmuxtmp_XXXXXX")"
export TMUX_TMPDIR="$TMUX_TMPDIR_REAL"
unset TMUX

PFX="aitswitcher_$$"

T_A="$(mktemp -d "${TMPDIR:-/tmp}/ait_switcher_a_XXXXXX")"
T_B="$(mktemp -d "${TMPDIR:-/tmp}/ait_switcher_b_XXXXXX")"
mkdir -p "$T_A/aitasks/metadata" "$T_B/aitasks/metadata"
: > "$T_A/aitasks/metadata/project_config.yaml"
: > "$T_B/aitasks/metadata/project_config.yaml"

tmux new-session -d -s "${PFX}_a" -c "$T_A" 'sleep 300' 2>/dev/null || true
tmux new-session -d -s "${PFX}_b" -c "$T_B" 'sleep 300' 2>/dev/null || true

# shellcheck disable=SC2329
cleanup() {
    tmux kill-session -t "${PFX}_a" 2>/dev/null || true
    tmux kill-session -t "${PFX}_b" 2>/dev/null || true
    tmux kill-server 2>/dev/null || true
    rm -rf "$T_A" "$T_B" "$TMUX_TMPDIR_REAL"
}
trap cleanup EXIT

out=$(PYTHONPATH="$LIB_DIR" TMUX_TMPDIR="$TMUX_TMPDIR_REAL" "$AITASK_PYTHON" -c "
import agent_launch_utils as u
sessions = {s.session for s in u.discover_aitasks_sessions()}
print('HAS_A:' + str('${PFX}_a' in sessions))
print('HAS_B:' + str('${PFX}_b' in sessions))
print('COUNT:' + str(len(sessions)))
")
mapfile -t lines <<<"$out"
for line in "${lines[@]}"; do
    key="${line%%:*}"
    val="${line#*:}"
    R["T2_$key"]="$val"
done

assert_eq "Tier 2: session A discovered" "True" "${R[T2_HAS_A]:-}"
assert_eq "Tier 2: session B discovered" "True" "${R[T2_HAS_B]:-}"

echo ""
echo "===================="
echo "Passed: $PASS / $TOTAL"
[[ $FAIL -gt 0 ]] && echo "Failed: $FAIL"
if [[ $FAIL -gt 0 ]]; then
    exit 1
else
    exit 0
fi
