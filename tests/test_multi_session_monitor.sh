#!/usr/bin/env bash
# test_multi_session_monitor.sh - Verify the multi-session extensions to
# TmuxMonitor and MonitorApp added in t634_2.
#
# Covers:
#   * TmuxPaneInfo.session_name field (added, default "")
#   * TmuxMonitor(multi_session=True/False) discovery paths
#   * switch_to_pane cross-session vs same-session branching
#   * kill_agent_pane_smart uses pane.session_name (not self.session)
#   * _is_companion_process filtering still applies in multi mode
#   * exclude_pane still applies in multi mode
#   * MonitorApp M binding + action_toggle_multi_session behavior
#   * Real tmux: two fake aitasks sessions aggregated in one list
#
# Run: bash tests/test_multi_session_monitor.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LIB_DIR="$PROJECT_DIR/.aitask-scripts/lib"
MONITOR_DIR="$PROJECT_DIR/.aitask-scripts/monitor"

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

assert_not_contains() {
    local desc="$1" needle="$2" haystack="$3"
    TOTAL=$((TOTAL + 1))
    if [[ "$haystack" == *"$needle"* ]]; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected NOT to contain '$needle', got '$haystack')"
    else
        PASS=$((PASS + 1))
    fi
}

# --- Tier 1: Python dataclass + TmuxMonitor (mock-based, always run) ---

out=$(PYTHONPATH="$LIB_DIR:$MONITOR_DIR" python3 -c "
from dataclasses import fields
import tmux_monitor as tm

names = {f.name for f in fields(tm.TmuxPaneInfo)}
print('HAS_SESSION_NAME:' + str('session_name' in names))

defaults = {f.name: f.default for f in fields(tm.TmuxPaneInfo)}
print('DEFAULT_SESSION_NAME:' + repr(defaults.get('session_name')))
")
mapfile -t lines <<<"$out"
assert_eq "TmuxPaneInfo has session_name field" "HAS_SESSION_NAME:True" "${lines[0]:-}"
assert_eq "TmuxPaneInfo.session_name default is ''" "DEFAULT_SESSION_NAME:''" "${lines[1]:-}"

# --- Tier 1b: discover_panes aggregates across sessions (mock-based) ---

out=$(PYTHONPATH="$LIB_DIR:$MONITOR_DIR" python3 <<'PY'
from unittest.mock import patch, MagicMock
import tmux_monitor as tm
from agent_launch_utils import AitasksSession
from pathlib import Path

# Fake two aitasks sessions.
fake_sessions = [
    AitasksSession(session="sessA", project_root=Path("/tmp/projA"), project_name="projA"),
    AitasksSession(session="sessB", project_root=Path("/tmp/projB"), project_name="projB"),
]

# Build a synthetic list-panes stdout (one agent pane per session).
def make_row(widx, wname, pidx, pane_id, pid):
    parts = [widx, wname, pidx, pane_id, str(pid), "bash", "80", "24"]
    return "\t".join(parts)

rows_a = make_row("1", "agent-t42-claudecode", "0", "%1", 1001) + "\n"
rows_b = make_row("1", "agent-t43-claudecode", "0", "%2", 1002) + "\n"

def fake_run(cmd, *args, **kwargs):
    result = MagicMock()
    result.returncode = 0
    # list-panes -s -t =sessA or =sessB
    if len(cmd) >= 6 and cmd[1] == "list-panes":
        target = cmd[4] if "-t" in cmd else ""
        if "sessA" in target:
            result.stdout = rows_a
        elif "sessB" in target:
            result.stdout = rows_b
        else:
            result.stdout = ""
    else:
        result.stdout = ""
    return result

# _is_companion_process must return False so panes aren't filtered out.
with patch.object(tm, "discover_aitasks_sessions", return_value=fake_sessions), \
     patch.object(tm, "_is_companion_process", return_value=False), \
     patch.object(tm.subprocess, "run", side_effect=fake_run):
    mon = tm.TmuxMonitor(session="ignored", multi_session=True)
    panes = mon.discover_panes()

print("COUNT:" + str(len(panes)))
for p in panes:
    print("PANE:" + p.session_name + ":" + p.pane_id + ":" + p.window_name)
PY
)
mapfile -t lines <<<"$out"
assert_eq "multi-session discover_panes aggregates both sessions" "COUNT:2" "${lines[0]:-}"
assert_contains "panes from sessA are tagged" "PANE:sessA:%1:agent-t42-claudecode" "$out"
assert_contains "panes from sessB are tagged" "PANE:sessB:%2:agent-t43-claudecode" "$out"

# Sort order: sessA < sessB lexicographically.
assert_contains "sessA panes come first after sort" "PANE:sessA:%1" "${lines[1]:-}"

# --- Tier 1c: single-session mode still issues exactly one list-panes call ---

out=$(PYTHONPATH="$LIB_DIR:$MONITOR_DIR" python3 <<'PY'
from unittest.mock import patch, MagicMock
import tmux_monitor as tm

calls = []

def fake_run(cmd, *args, **kwargs):
    calls.append(list(cmd))
    result = MagicMock()
    result.returncode = 0
    result.stdout = ""
    return result

with patch.object(tm, "_is_companion_process", return_value=False), \
     patch.object(tm.subprocess, "run", side_effect=fake_run):
    mon = tm.TmuxMonitor(session="solo", multi_session=False)
    mon.discover_panes()

list_pane_calls = [c for c in calls if len(c) > 2 and c[1] == "list-panes"]
print("LP_CALLS:" + str(len(list_pane_calls)))
if list_pane_calls:
    target = list_pane_calls[0]
    # -t =solo should appear
    has_solo = any("=solo" in part for part in target)
    print("TARGETS_SOLO:" + str(has_solo))
PY
)
assert_contains "single-session mode issues exactly one list-panes call" \
    "LP_CALLS:1" "$out"
assert_contains "single-session mode targets self.session" \
    "TARGETS_SOLO:True" "$out"

# --- Tier 1d: switch_to_pane cross-session routes through switch_to_pane_anywhere ---

out=$(PYTHONPATH="$LIB_DIR:$MONITOR_DIR" python3 <<'PY'
from unittest.mock import patch, MagicMock
import tmux_monitor as tm
from tmux_monitor import TmuxPaneInfo, PaneCategory

pane = TmuxPaneInfo(
    window_index="1", window_name="agent-t42-cc", pane_index="0",
    pane_id="%7", pane_pid=999, current_command="claude",
    width=80, height=24, category=PaneCategory.AGENT,
    session_name="other_sess",
)

switch_calls = []

def fake_switch_anywhere(pane_id):
    switch_calls.append(pane_id)
    return True

direct_tmux_calls = []

def fake_run(cmd, *args, **kwargs):
    direct_tmux_calls.append(list(cmd))
    result = MagicMock()
    result.returncode = 0
    return result

with patch.object(tm, "switch_to_pane_anywhere", side_effect=fake_switch_anywhere), \
     patch.object(tm.subprocess, "run", side_effect=fake_run):
    mon = tm.TmuxMonitor(session="self_sess", multi_session=True)
    mon._pane_cache["%7"] = pane
    ok = mon.switch_to_pane("%7")

print("OK:" + str(ok))
print("TELEPORT_CALLS:" + str(len(switch_calls)))
print("TELEPORT_PANE:" + (switch_calls[0] if switch_calls else ""))
# Direct tmux select-window / select-pane MUST NOT have fired in cross-session path.
select_window = [c for c in direct_tmux_calls if len(c) > 1 and c[1] == "select-window"]
print("DIRECT_SELECT_WINDOW:" + str(len(select_window)))
PY
)
assert_contains "cross-session switch returns True" "OK:True" "$out"
assert_contains "cross-session switch calls switch_to_pane_anywhere once" \
    "TELEPORT_CALLS:1" "$out"
assert_contains "cross-session switch targets correct pane id" \
    "TELEPORT_PANE:%7" "$out"
assert_contains "cross-session switch does NOT call select-window directly" \
    "DIRECT_SELECT_WINDOW:0" "$out"

# --- Tier 1e: switch_to_pane same-session uses existing path ---

out=$(PYTHONPATH="$LIB_DIR:$MONITOR_DIR" python3 <<'PY'
from unittest.mock import patch, MagicMock
import tmux_monitor as tm
from tmux_monitor import TmuxPaneInfo, PaneCategory

pane = TmuxPaneInfo(
    window_index="2", window_name="agent-t42-cc", pane_index="0",
    pane_id="%8", pane_pid=999, current_command="claude",
    width=80, height=24, category=PaneCategory.AGENT,
    session_name="self_sess",  # same session
)

teleport_calls = []

def fake_switch_anywhere(pane_id):
    teleport_calls.append(pane_id)
    return True

direct_calls = []

def fake_run(cmd, *args, **kwargs):
    direct_calls.append(list(cmd))
    result = MagicMock()
    result.returncode = 0
    return result

with patch.object(tm, "switch_to_pane_anywhere", side_effect=fake_switch_anywhere), \
     patch.object(tm.subprocess, "run", side_effect=fake_run):
    mon = tm.TmuxMonitor(session="self_sess", multi_session=True)
    mon._pane_cache["%8"] = pane
    ok = mon.switch_to_pane("%8")

print("OK:" + str(ok))
print("TELEPORT_CALLS:" + str(len(teleport_calls)))
# select-window should have been called for same-session.
select_window = [c for c in direct_calls if len(c) > 1 and c[1] == "select-window"]
print("DIRECT_SELECT_WINDOW:" + str(len(select_window)))
PY
)
assert_contains "same-session switch returns True" "OK:True" "$out"
assert_contains "same-session switch does NOT teleport" \
    "TELEPORT_CALLS:0" "$out"
assert_contains "same-session switch DOES call select-window directly" \
    "DIRECT_SELECT_WINDOW:1" "$out"

# --- Tier 1f: kill_agent_pane_smart uses pane.session_name ---

out=$(PYTHONPATH="$LIB_DIR:$MONITOR_DIR" python3 <<'PY'
from unittest.mock import patch, MagicMock
import tmux_monitor as tm
from tmux_monitor import TmuxPaneInfo, PaneCategory

pane = TmuxPaneInfo(
    window_index="3", window_name="agent-t42-cc", pane_index="0",
    pane_id="%9", pane_pid=999, current_command="claude",
    width=80, height=24, category=PaneCategory.AGENT,
    session_name="other_sess",
)

captured_targets = []

def fake_run(cmd, *args, **kwargs):
    # Capture the list-panes -t target argument.
    if len(cmd) > 3 and cmd[1] == "list-panes" and "-t" in cmd:
        idx = cmd.index("-t")
        captured_targets.append(cmd[idx + 1])
    result = MagicMock()
    result.returncode = 0
    # Simulate one sibling agent pane so we go through kill_pane path (not kill_window)
    result.stdout = "%99\t1234\n%9\t999\n"
    return result

with patch.object(tm, "_is_companion_process", return_value=False), \
     patch.object(tm.subprocess, "run", side_effect=fake_run):
    mon = tm.TmuxMonitor(session="self_sess", multi_session=True)
    mon._pane_cache["%9"] = pane
    mon.kill_agent_pane_smart("%9")

# The list-panes target MUST reference other_sess, not self_sess.
for t in captured_targets:
    print("TARGET:" + t)
PY
)
assert_contains "kill_agent_pane_smart uses pane's own session" \
    "TARGET:=other_sess:3" "$out"
assert_not_contains "kill_agent_pane_smart does NOT use self.session" \
    "=self_sess:3" "$out"

# --- Tier 1g: _is_companion_process filter still applies in multi mode ---

out=$(PYTHONPATH="$LIB_DIR:$MONITOR_DIR" python3 <<'PY'
from unittest.mock import patch, MagicMock
import tmux_monitor as tm
from agent_launch_utils import AitasksSession
from pathlib import Path

fake_sessions = [
    AitasksSession(session="sessX", project_root=Path("/tmp/x"), project_name="x"),
]

def make_row(widx, wname, pidx, pane_id, pid):
    return "\t".join([widx, wname, pidx, pane_id, str(pid), "python3", "80", "24"])

# Two agent panes, one is a companion (minimonitor).
stdout = make_row("1", "agent-t1", "0", "%1", 1001) + "\n" + \
         make_row("1", "agent-t1", "1", "%2", 1002) + "\n"

def fake_run(cmd, *args, **kwargs):
    result = MagicMock()
    result.returncode = 0
    result.stdout = stdout if cmd[1] == "list-panes" else ""
    return result

# Mark PID 1002 as a companion.
def fake_companion(pid):
    return pid == 1002

with patch.object(tm, "discover_aitasks_sessions", return_value=fake_sessions), \
     patch.object(tm, "_is_companion_process", side_effect=fake_companion), \
     patch.object(tm.subprocess, "run", side_effect=fake_run):
    mon = tm.TmuxMonitor(session="sessX", multi_session=True)
    panes = mon.discover_panes()

print("COUNT:" + str(len(panes)))
for p in panes:
    print("PANE:" + p.pane_id)
PY
)
assert_contains "companion filter still excludes companions in multi mode" \
    "COUNT:1" "$out"
assert_contains "non-companion pane survives" "PANE:%1" "$out"
assert_not_contains "companion pane is filtered out" "PANE:%2" "$out"

# --- Tier 1h: exclude_pane still filters in multi mode ---

out=$(PYTHONPATH="$LIB_DIR:$MONITOR_DIR" python3 <<'PY'
from unittest.mock import patch, MagicMock
import tmux_monitor as tm
from agent_launch_utils import AitasksSession
from pathlib import Path

fake_sessions = [
    AitasksSession(session="sessY", project_root=Path("/tmp/y"), project_name="y"),
]

def make_row(widx, wname, pidx, pane_id, pid):
    return "\t".join([widx, wname, pidx, pane_id, str(pid), "bash", "80", "24"])

stdout = make_row("1", "agent-t1", "0", "%exclude_me", 1001) + "\n" + \
         make_row("1", "agent-t2", "0", "%keep_me", 1002) + "\n"

def fake_run(cmd, *args, **kwargs):
    result = MagicMock()
    result.returncode = 0
    result.stdout = stdout if cmd[1] == "list-panes" else ""
    return result

with patch.object(tm, "discover_aitasks_sessions", return_value=fake_sessions), \
     patch.object(tm, "_is_companion_process", return_value=False), \
     patch.object(tm.subprocess, "run", side_effect=fake_run):
    mon = tm.TmuxMonitor(
        session="sessY", multi_session=True, exclude_pane="%exclude_me",
    )
    panes = mon.discover_panes()

print("COUNT:" + str(len(panes)))
for p in panes:
    print("PANE:" + p.pane_id)
PY
)
assert_contains "exclude_pane works in multi mode" "COUNT:1" "$out"
assert_not_contains "excluded pane is gone" "PANE:%exclude_me" "$out"
assert_contains "other pane survives" "PANE:%keep_me" "$out"

# --- Tier 1i: MonitorApp M binding + action_toggle_multi_session ---

out=$(PYTHONPATH="$LIB_DIR:$MONITOR_DIR" python3 <<'PY'
import monitor_app as mon_app

# Ensure M is present in BINDINGS.
keys = []
for b in mon_app.MonitorApp.BINDINGS:
    # Binding may be a tuple or a Binding instance depending on Textual version.
    key = getattr(b, "key", None) or (b[0] if isinstance(b, tuple) else None)
    if key:
        keys.append(key)
print("M_IN_BINDINGS:" + str("M" in keys))
print("HAS_ACTION:" + str(hasattr(mon_app.MonitorApp, "action_toggle_multi_session")))
PY
)
assert_contains "MonitorApp has M binding registered" "M_IN_BINDINGS:True" "$out"
assert_contains "MonitorApp has action_toggle_multi_session handler" \
    "HAS_ACTION:True" "$out"

# --- Tier 2: Real tmux — two fake aitasks sessions aggregated ---

if ! command -v tmux >/dev/null 2>&1; then
    echo "SKIP: tmux not installed — skipping Tier 2 runtime assertions"
else
    TEST_TMUX_DIR=$(mktemp -d "${TMPDIR:-/tmp}/ait_multisess_mon_XXXXXX")
    export TMUX_TMPDIR="$TEST_TMUX_DIR"
    unset TMUX

    FAKE_A=$(mktemp -d "${TMPDIR:-/tmp}/ait_fake_ma_XXXXXX")
    FAKE_B=$(mktemp -d "${TMPDIR:-/tmp}/ait_fake_mb_XXXXXX")
    mkdir -p "$FAKE_A/aitasks/metadata" "$FAKE_B/aitasks/metadata"
    : > "$FAKE_A/aitasks/metadata/project_config.yaml"
    : > "$FAKE_B/aitasks/metadata/project_config.yaml"

    SA="aitmon_${$}_a"
    SB="aitmon_${$}_b"

    # shellcheck disable=SC2329  # invoked via trap
    cleanup() {
        tmux kill-server 2>/dev/null || true
        rm -rf "$TEST_TMUX_DIR" "$FAKE_A" "$FAKE_B"
    }
    trap cleanup EXIT

    if ! tmux new-session -d -s "$SA" -c "$FAKE_A" -n agent-t1 'sleep 300' 2>/dev/null; then
        echo "SKIP: could not start test tmux session"
    else
        tmux new-session -d -s "$SB" -c "$FAKE_B" -n agent-t2 'sleep 300'

        out=$(TMUX_TMPDIR="$TEST_TMUX_DIR" PYTHONPATH="$LIB_DIR:$MONITOR_DIR" python3 -c "
import tmux_monitor as tm
mon = tm.TmuxMonitor(session='$SA', multi_session=True)
panes = mon.discover_panes()
print('COUNT:' + str(len(panes)))
for p in panes:
    print('PANE:' + p.session_name + ':' + p.window_name)
")
        # At least one agent pane per session (agent- prefix + sleep window).
        # The default classify path treats 'agent-t1' / 'agent-t2' as AGENT.
        assert_contains "real tmux: sessA pane discovered" \
            "PANE:${SA}:agent-t1" "$out"
        assert_contains "real tmux: sessB pane discovered" \
            "PANE:${SB}:agent-t2" "$out"
    fi
fi

echo
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
if [[ $FAIL -eq 0 ]]; then
    exit 0
else
    exit 1
fi
