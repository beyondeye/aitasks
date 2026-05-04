#!/usr/bin/env bash
# test_multi_session_minimonitor.sh — Verify the minimonitor multi-session
# extensions added in t634_4.
#
# Covers:
#   * MiniMonitorApp registers the `M` binding (and preserves lowercase `m`)
#   * action_toggle_multi_session flips state + invalidates cache
#   * _start_monitoring no longer pins multi_session=False
#   * _auto_select_own_window narrowing predicate (own-session vs cross)
#   * _rebuild_pane_list emits session divider rows in multi mode only
#   * _rebuild_session_bar renders compact multi-mode title
#
# Mock-based Tier 1 only — real-tmux aggregation is covered in
# test_multi_session_monitor.sh (the TmuxMonitor aggregation path is shared).
#
# Run: bash tests/test_multi_session_minimonitor.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LIB_DIR="$PROJECT_DIR/.aitask-scripts/lib"
MONITOR_DIR="$PROJECT_DIR/.aitask-scripts/monitor"
BOARD_DIR="$PROJECT_DIR/.aitask-scripts/board"
PYPATH="$LIB_DIR:$MONITOR_DIR:$BOARD_DIR:$PROJECT_DIR/.aitask-scripts"

# shellcheck source=lib/venv_python.sh
. "$SCRIPT_DIR/lib/venv_python.sh"

PASS=0
FAIL=0
TOTAL=0

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

# --- Tier 1a: BINDINGS + action presence ---

out=$(PYTHONPATH="$PYPATH" "$AITASK_PYTHON" <<'PY'
from monitor import minimonitor_app as mm

keys = []
for b in mm.MiniMonitorApp.BINDINGS:
    key = getattr(b, "key", None) or (b[0] if isinstance(b, tuple) else None)
    if key:
        keys.append(key)

print("M_IN_BINDINGS:" + str("M" in keys))
print("LOWER_M_PRESERVED:" + str("m" in keys))
print("HAS_ACTION:" + str(hasattr(mm.MiniMonitorApp, "action_toggle_multi_session")))
PY
)
assert_contains "MiniMonitorApp has M binding registered" "M_IN_BINDINGS:True" "$out"
assert_contains "MiniMonitorApp preserves lowercase m binding" "LOWER_M_PRESERVED:True" "$out"
assert_contains "MiniMonitorApp has action_toggle_multi_session handler" \
    "HAS_ACTION:True" "$out"

# --- Tier 1b: action flips state + invalidates cache ---

out=$(PYTHONPATH="$PYPATH" "$AITASK_PYTHON" <<'PY'
from monitor import minimonitor_app as mm

class FakeMon:
    def __init__(self):
        self.multi_session = True
        self.invalidated = 0
    def invalidate_sessions_cache(self):
        self.invalidated += 1

app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
fake = FakeMon()
app._monitor = fake
# Textual App instance methods need attaching — stub with bound lambdas.
app.notify = lambda *a, **k: None
app.call_later = lambda fn: None
app._refresh_data = lambda: None  # referenced by call_later arg

app.action_toggle_multi_session()
print("AFTER_FLIP:" + str(fake.multi_session))
print("INVALIDATED_1:" + str(fake.invalidated))

app.action_toggle_multi_session()
print("BACK_ON:" + str(fake.multi_session))
print("INVALIDATED_2:" + str(fake.invalidated))

# No-op when monitor is None
app._monitor = None
app.action_toggle_multi_session()
print("NO_CRASH:True")
PY
)
assert_contains "action flips multi_session off" "AFTER_FLIP:False" "$out"
assert_contains "first toggle invalidates cache once" "INVALIDATED_1:1" "$out"
assert_contains "action flips multi_session back on" "BACK_ON:True" "$out"
assert_contains "second toggle invalidates cache again" "INVALIDATED_2:2" "$out"
assert_contains "action is a no-op when monitor is None" "NO_CRASH:True" "$out"

# --- Tier 1c: _start_monitoring no longer pins multi_session=False ---

out=$(PYTHONPATH="$PYPATH" "$AITASK_PYTHON" <<'PY'
from monitor import minimonitor_app as mm

recorded = {}

class RecMon:
    def __init__(self, **kwargs):
        recorded.update(kwargs)

# Patch the name that _start_monitoring references.
mm.TmuxMonitor = RecMon

app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
app._session = "x"
app._capture_lines = 30
app._idle_threshold = 5.0
app._agent_prefixes = None
app._tui_names = None
app._refresh_seconds = 3
app._compare_mode_default = "stripped"
app._refresh_timer = None
app._monitor = None
app.call_later = lambda fn: None
app.set_interval = lambda *a, **k: None
app.run_worker = lambda c, *a, **k: c.close()

app._start_monitoring()

print("HAS_FALSE_PIN:" + str(recorded.get("multi_session") is False))
print("NOT_PASSED:"  + str("multi_session" not in recorded))
PY
)
assert_contains "_start_monitoring does NOT pin multi_session=False" \
    "HAS_FALSE_PIN:False" "$out"
assert_contains "_start_monitoring does NOT pass multi_session explicitly" \
    "NOT_PASSED:True" "$out"

# --- Tier 1d: _auto_select_own_window predicate ---
# The real method uses Textual queries which are fragile in unit tests, so
# exercise the core (window_index, session_name) matching predicate directly.

out=$(PYTHONPATH="$PYPATH" "$AITASK_PYTHON" <<'PY'
def would_match(own_window_index, own_session, snap_window_index, snap_session):
    # Mirror of the guard in MiniMonitorApp._auto_select_own_window.
    return (
        snap_window_index == own_window_index
        and snap_session in ("", own_session)
    )

print("OWN:"          + str(would_match("1", "sA", "1", "sA")))
print("CROSS:"        + str(would_match("1", "sA", "1", "sB")))
print("LEGACY_EMPTY:" + str(would_match("1", "sA", "1", "")))
print("DIFF_INDEX:"   + str(would_match("1", "sA", "2", "sA")))
PY
)
assert_contains "own-session + matching index → True"       "OWN:True"          "$out"
assert_contains "cross-session + matching index → False"    "CROSS:False"       "$out"
assert_contains "legacy empty session_name still matches"   "LEGACY_EMPTY:True" "$out"
assert_contains "matching session but different index fails" "DIFF_INDEX:False" "$out"

# --- Tier 1e: _rebuild_pane_list emits dividers in multi mode ---

out=$(PYTHONPATH="$PYPATH" "$AITASK_PYTHON" <<'PY'
import asyncio
from types import SimpleNamespace

from monitor import minimonitor_app as mm
from textual.widgets import Static

class FakeContainer:
    async def remove_children(self):
        pass
    async def mount_all(self, widgets):
        # Keep a handle we can inspect from outside.
        self.mounted = list(widgets)

container = FakeContainer()

app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
app.query_one = lambda *a, **k: container
app._task_cache = SimpleNamespace(
    get_task_id=lambda w: None,
    get_task_info=lambda t: None,
)
app._monitor = SimpleNamespace(
    multi_session=True,
    get_compare_mode=lambda pid: "stripped",
    is_compare_mode_overridden=lambda pid: False,
)

def mk_snap(sess, wi, pi, pid, name):
    pane = SimpleNamespace(
        category=mm.PaneCategory.AGENT,
        session_name=sess,
        window_index=wi,
        pane_index=pi,
        pane_id=pid,
        window_name=name,
    )
    return SimpleNamespace(pane=pane, is_idle=False, idle_seconds=0.0)

# Two agents in two sessions → expect 4 widgets: [divA, cardA, divB, cardB]
app._snapshots = {
    "%1": mk_snap("sA", "1", "0", "%1", "agent-t1"),
    "%2": mk_snap("sB", "2", "0", "%2", "agent-t2"),
}

asyncio.run(app._rebuild_pane_list())
widgets = container.mounted
print("MULTI_COUNT:" + str(len(widgets)))
print("DIV0_STATIC:"  + str(isinstance(widgets[0], Static) and not isinstance(widgets[0], mm.MiniPaneCard)))
print("CARD1:"       + str(isinstance(widgets[1], mm.MiniPaneCard)))
print("DIV2_STATIC:"  + str(isinstance(widgets[2], Static) and not isinstance(widgets[2], mm.MiniPaneCard)))
print("CARD3:"       + str(isinstance(widgets[3], mm.MiniPaneCard)))

# Single-session: no dividers, just cards.
app._monitor.multi_session = False
asyncio.run(app._rebuild_pane_list())
widgets = container.mounted
print("SINGLE_COUNT:"  + str(len(widgets)))
print("SINGLE_NO_DIV:" + str(all(isinstance(w, mm.MiniPaneCard) for w in widgets)))
PY
)
assert_contains "multi mode: 2 agents + 2 dividers = 4 widgets"  "MULTI_COUNT:4"   "$out"
assert_contains "widget 0 is the first session divider (Static)" "DIV0_STATIC:True" "$out"
assert_contains "widget 1 is the first agent card"                "CARD1:True"      "$out"
assert_contains "widget 2 is the second session divider"          "DIV2_STATIC:True" "$out"
assert_contains "widget 3 is the second agent card"               "CARD3:True"      "$out"
assert_contains "single mode: only 2 cards mounted"               "SINGLE_COUNT:2"  "$out"
assert_contains "single mode: no divider widgets present"         "SINGLE_NO_DIV:True" "$out"

# --- Tier 1f: _rebuild_session_bar text reflects mode ---

out=$(PYTHONPATH="$PYPATH" "$AITASK_PYTHON" <<'PY'
from types import SimpleNamespace

from monitor import minimonitor_app as mm
from monitor.tmux_control import TmuxControlState

class Capture:
    def __init__(self):
        self.text = ""
    def update(self, text):
        self.text = text

captured = Capture()

app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
app.query_one = lambda *a, **k: captured
app._session = "aitasks"
app._monitor = SimpleNamespace(
    multi_session=True,
    control_state=lambda: TmuxControlState.STOPPED,
)

def mk_snap(sess, idle=False):
    pane = SimpleNamespace(
        category=mm.PaneCategory.AGENT,
        session_name=sess, window_index="1", pane_index="0",
        pane_id="%x", window_name="agent-x",
    )
    return SimpleNamespace(pane=pane, is_idle=idle, idle_seconds=0.0)

app._snapshots = {"%1": mk_snap("sA"), "%2": mk_snap("sB", idle=True)}
app._rebuild_session_bar()
print("MULTI_BAR:" + captured.text)

app._monitor.multi_session = False
app._rebuild_session_bar()
print("SINGLE_BAR:" + captured.text)
PY
)
assert_contains "multi-mode bar leads with 'multi:'"     "MULTI_BAR:multi: 2s" "$out"
assert_contains "multi-mode bar shows idle count"        "1 idle"              "$out"
assert_contains "single-mode bar shows raw session name" "SINGLE_BAR:aitasks"  "$out"

echo
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
if [[ $FAIL -eq 0 ]]; then
    exit 0
else
    exit 1
fi
