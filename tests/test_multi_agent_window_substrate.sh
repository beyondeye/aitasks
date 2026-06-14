#!/usr/bin/env bash
# Tests for the multi-agent-per-window substrate + shadow helper-pane
# exclusion (t986_1).
#
# Tier 1 (always runs): pure-unit coverage of the headless helpers —
#   - task_id_from_window_name  (pane->task mapping)
#   - is_shadow_target          (shadow marker predicate)
#   - count_other_real_agents   (per-window real-agent counting)
#   - TmuxMonitor._parse_list_panes filters shadow helper panes
#   - TaskInfoCache.get_task_id_for_pane resolves per pane (cached)
#
# Tier 2 (skips without tmux): real-tmux integration —
#   - aitask_companion_cleanup.sh kills the shadow bound to a dying agent
#     (same window AND a separate window), leaves an unrelated agent + its
#     shadow alone, and keeps/collapses the companion correctly.
#   - kill_agent_pane_smart treats a shadow as a helper (window collapses when
#     the only sibling is a shadow; survives when a real agent remains).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "SKIP: $PYTHON_BIN not available"
    exit 0
fi

# ---------------------------------------------------------------------------
# Tier 1: pure-unit tests (no tmux)
# ---------------------------------------------------------------------------
(
    cd "$REPO_ROOT"
    PYTHONPATH="$REPO_ROOT/.aitask-scripts" "$PYTHON_BIN" - <<'PYEOF'
import sys
from pathlib import Path

import monitor.monitor_core as mc
from monitor.monitor_core import (
    TmuxMonitor, TaskInfoCache, TmuxPaneInfo, PaneCategory,
    task_id_from_window_name, is_shadow_target, count_other_real_agents,
)

failures = []


def check(label, cond):
    if cond:
        print(f"  ok: {label}")
    else:
        print(f"  FAIL: {label}")
        failures.append(label)


# -- task_id_from_window_name -------------------------------------------------
check("pick window -> id", task_id_from_window_name("agent-pick-100") == "100")
check("qa child window -> id", task_id_from_window_name("agent-qa-100_1") == "100_1")
check("non-agent window -> None", task_id_from_window_name("git") is None)
check("shadow-named window not a pick/qa task",
      task_id_from_window_name("agent-shadow-foo") is None)

# -- is_shadow_target ---------------------------------------------------------
check("empty target not shadow", is_shadow_target("") is False)
check("whitespace target not shadow", is_shadow_target("   ") is False)
check("pane-id target is shadow", is_shadow_target("%7") is True)

# -- count_other_real_agents --------------------------------------------------
check("counts real siblings excluding self",
      count_other_real_agents([("%1", False), ("%2", True), ("%3", False)], "%1") == 1)
check("two real siblings",
      count_other_real_agents([("%1", False), ("%2", False)], "%1") == 1)
check("only helper sibling -> zero",
      count_other_real_agents([("%1", False), ("%2", True)], "%1") == 0)
check("empty -> zero", count_other_real_agents([], "%1") == 0)

# -- _parse_list_panes filters shadow + companion panes -----------------------
mc._is_companion_process = lambda pid: pid == 9999  # patch: pid 9999 == companion
monitor = TmuxMonitor(session="testsess")
FMT_LINE = "\t".join  # 9 tab-separated fields per the discovery format

stdout = "\n".join([
    # agent pane (target empty, pid not companion) -> kept
    FMT_LINE(["0", "agent-pick-100", "0", "%1", "1234", "node", "80", "24", ""]),
    # shadow helper pane (target set) -> filtered even though pid not companion
    FMT_LINE(["0", "agent-pick-100", "1", "%2", "1235", "node", "80", "24", "%1"]),
    # companion pane (pid 9999) -> filtered
    FMT_LINE(["0", "agent-pick-100", "2", "%3", "9999", "python", "80", "24", ""]),
])
panes = monitor._parse_list_panes(stdout, "testsess")
check("discovery keeps exactly one real agent", len(panes) == 1)
check("discovery kept the agent pane (%1)",
      len(panes) == 1 and panes[0].pane_id == "%1")
kept_ids = {p.pane_id for p in panes}
check("shadow pane %2 excluded", "%2" not in kept_ids)
check("companion pane %3 excluded", "%3" not in kept_ids)

# -- TaskInfoCache.get_task_id_for_pane (pane-keyed, cached) ------------------
cache = TaskInfoCache(Path("/tmp"))
agent_pane = TmuxPaneInfo(
    window_index="0", window_name="agent-pick-100_2", pane_index="0",
    pane_id="%5", pane_pid=1, current_command="node", width=80, height=24,
    category=PaneCategory.AGENT, session_name="testsess",
)
check("pane-keyed resolve -> task id",
      cache.get_task_id_for_pane(agent_pane) == "100_2")
check("pane-keyed resolve cached (same value second call)",
      cache.get_task_id_for_pane(agent_pane) == "100_2")
check("pane-keyed cache stored under pane_id",
      cache._pane_to_task_id.get("%5") == "100_2")
non_agent = TmuxPaneInfo(
    window_index="0", window_name="git", pane_index="0",
    pane_id="%6", pane_pid=1, current_command="git", width=80, height=24,
    category=PaneCategory.OTHER, session_name="testsess",
)
check("non-agent pane resolves to None",
      cache.get_task_id_for_pane(non_agent) is None)

if failures:
    sys.exit(f"Tier 1 FAILED: {failures}")
print("Tier 1 OK")
PYEOF
)

# ---------------------------------------------------------------------------
# Tier 2: real-tmux integration (skips if tmux unavailable)
# ---------------------------------------------------------------------------
if ! command -v tmux >/dev/null 2>&1; then
    echo "SKIP Tier 2: tmux not available"
    echo "PASS: tests/test_multi_agent_window_substrate.sh (Tier 1 only)"
    exit 0
fi

# shellcheck source=lib/tmux_isolation.sh
. "$SCRIPT_DIR/lib/tmux_isolation.sh"
require_isolated_tmux

FIXTURE_DIR=$(mktemp -d "${TMPDIR:-/tmp}/ait_multiagent_XXXXXX")
trap 'TMUX_TMPDIR="$FIXTURE_DIR" tmux kill-server 2>/dev/null || true; rm -rf "$FIXTURE_DIR"' EXIT

(
    cd "$REPO_ROOT"
    export TMUX_TMPDIR="$FIXTURE_DIR"
    export REPO_ROOT
    unset TMUX
    SESSION="ait_multiagent_$$"
    tmux new-session -d -s "$SESSION" -n "scratch" "tail -f /dev/null"

    AIT_TEST_TMUX_DIR="$FIXTURE_DIR" \
    AIT_TEST_SESSION="$SESSION" \
    PYTHONPATH="$REPO_ROOT/.aitask-scripts" \
    "$PYTHON_BIN" - <<'PYEOF'
import os
import subprocess
import sys
import time

from pathlib import Path

import monitor.monitor_core as mc
from monitor.monitor_core import (
    TmuxMonitor, TmuxPaneInfo, PaneCategory, TaskInfoCache,
)

session = os.environ["AIT_TEST_SESSION"]
tmux_dir = os.environ["AIT_TEST_TMUX_DIR"]
repo_root = os.environ["REPO_ROOT"]
cleanup_sh = os.path.join(repo_root, ".aitask-scripts", "aitask_companion_cleanup.sh")
env = {**os.environ, "TMUX_TMPDIR": tmux_dir}
env.pop("TMUX", None)

failures = []


def check(label, cond):
    if cond:
        print(f"  ok: {label}")
    else:
        print(f"  FAIL: {label}")
        failures.append(label)


def sub(args):
    r = subprocess.run(["tmux", *args], capture_output=True, text=True,
                       env=env, timeout=10)
    return r.returncode, (r.stdout or "").strip()


def new_window(name):
    sub(["new-window", "-t", session, "-n", name, "tail -f /dev/null"])
    rc, out = sub(["display-message", "-p", "-t", f"{session}:{name}", "#{pane_id}"])
    return out


def split(window_name):
    """Split the named window, returning the new pane id."""
    rc, out = sub(["split-window", "-P", "-F", "#{pane_id}",
                   "-t", f"{session}:{window_name}", "tail -f /dev/null"])
    return out


def mark_shadow(pane_id, target_pane_id):
    sub(["set-option", "-p", "-t", pane_id, "@aitask_shadow_target", target_pane_id])


def window_panes(window_name):
    rc, out = sub(["list-panes", "-t", f"{session}:{window_name}", "-F", "#{pane_id}"])
    if rc != 0:
        return set()
    return set(out.splitlines()) if out else set()


def window_exists(window_name):
    rc, out = sub(["list-windows", "-t", session, "-F", "#{window_name}"])
    return window_name in out.splitlines()


def run_cleanup(primary, companion):
    r = subprocess.run(["bash", cleanup_sh, primary, companion],
                       capture_output=True, text=True, env=env, timeout=10)
    if r.returncode != 0:
        print(f"  cleanup stderr: {r.stderr}")
    return r.returncode


# == Scenario A: shadow lifecycle via the cleanup hook ====================
# Window W: agent A (.0), agent B, companion C, shadow SA bound to A.
# Separate window W2: shadow SA2 also bound to A (tests session-wide scope).
agent_a = new_window("W")
agent_b = split("W")
companion = split("W")
shadow_a = split("W")
mark_shadow(shadow_a, agent_a)

shadow_a2 = new_window("W2")
mark_shadow(shadow_a2, agent_a)
time.sleep(0.2)

check("fixture: W has 4 panes", len(window_panes("W")) == 4)

# Fire cleanup for the dying agent A.
run_cleanup(agent_a, companion)
time.sleep(0.2)

panes_w = window_panes("W")
check("A killed", agent_a not in panes_w)
check("A's same-window shadow killed", shadow_a not in panes_w)
check("unrelated agent B survives", agent_b in panes_w)
check("companion survives (real sibling B remains)", companion in panes_w)
check("A's separate-window shadow killed (session-scoped)",
      not window_exists("W2"))

# Now B dies — no real agents remain, companion should be collapsed with it.
run_cleanup(agent_b, companion)
time.sleep(0.2)
check("window W gone once last agent + companion cleaned", not window_exists("W"))

# == Scenario B: kill_agent_pane_smart treats shadow as a helper ==========
mc._is_companion_process = lambda pid: False  # no companion stand-in here

def populate(monitor, window_name):
    rc, out = sub(["list-panes", "-t", f"{session}:{window_name}", "-F", "\t".join([
        "#{window_index}", "#{window_name}", "#{pane_index}", "#{pane_id}",
        "#{pane_pid}", "#{pane_current_command}", "#{pane_width}",
        "#{pane_height}",
    ])])
    for line in out.splitlines():
        p = line.split("\t")
        if len(p) != 8:
            continue
        monitor._pane_cache[p[3]] = TmuxPaneInfo(
            window_index=p[0], window_name=p[1], pane_index=p[2], pane_id=p[3],
            pane_pid=int(p[4]), current_command=p[5], width=int(p[6]),
            height=int(p[7]), category=PaneCategory.AGENT, session_name=session,
        )

# Window S1: agent + shadow only -> killing the agent collapses the window
# (the shadow is a helper, so no real sibling remains).
s1_agent = new_window("S1")
s1_shadow = split("S1")
mark_shadow(s1_shadow, s1_agent)
time.sleep(0.2)
mon = TmuxMonitor(session=session)
populate(mon, "S1")
ok, killed_window = mon.kill_agent_pane_smart(s1_agent)
check("kill agent with only a shadow sibling -> window collapses",
      ok and killed_window and not window_exists("S1"))

# Window S2: two real agents + a shadow -> killing one keeps the window
# (the other real agent survives; only the pane is killed).
s2_a = new_window("S2")
s2_b = split("S2")
s2_shadow = split("S2")
mark_shadow(s2_shadow, s2_a)
time.sleep(0.2)
mon2 = TmuxMonitor(session=session)
populate(mon2, "S2")
ok, killed_window = mon2.kill_agent_pane_smart(s2_a)
check("kill one of two real agents (shadow present) -> pane only",
      ok and not killed_window and window_exists("S2"))

# == Scenario C: live discovery filters shadow panes (real format) =========
# Exercises the actual _LIST_PANES_FORMAT (9 fields incl. @aitask_shadow_target)
# against live tmux, through discover_panes() -> _parse_list_panes().
d_agent = new_window("agent-pick-777")
d_shadow = split("agent-pick-777")
mark_shadow(d_shadow, d_agent)
time.sleep(0.2)
disc = TmuxMonitor(session=session)
ids = {p.pane_id for p in disc.discover_panes()}
check("live discovery excludes the shadow pane", d_shadow not in ids)
check("live discovery includes the real agent pane", d_agent in ids)
agent_info = next((p for p in disc.discover_panes()
                   if p.pane_id == d_agent), None)
tic = TaskInfoCache(Path("/tmp"))
check("discovered agent resolves a task id (pane-keyed)",
      agent_info is not None and tic.get_task_id_for_pane(agent_info) == "777")

if failures:
    sys.exit(f"Tier 2 FAILED: {failures}")
print("Tier 2 OK")
PYEOF
)

echo "PASS: tests/test_multi_agent_window_substrate.sh"
