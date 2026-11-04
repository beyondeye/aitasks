#!/usr/bin/env bash
# Real-server regression test for `TmuxMonitor.kill_agent_run_guarded` (t2175_5).
#
# harvest-and-close (`h` in the monitor TUIs) closes the agent RUN it harvested,
# never whatever later occupies its pane id. The kill is ONE `if-shell -F`
# whose condition (unfrozen, same `pane_pid`, same server `#{pid}`) a REAL tmux
# server evaluates here, then a read-back decides. Two passes, as in
# test_kill_agent_pane_smart.sh: control-client route and subprocess route.
#
# Per pass:
#   - a `respawn-pane -k` after the identity was read  -> changed, new process lives
#   - `@aitask_frozen` stamped after the read          -> changed, pane lives
#   - a malformed identity                              -> failed, nothing sent
#   - a fresh identity, another agent in the window     -> killed, pane only;
#     a helper bound to it is swept, the companion and the other agent stay
#   - a fresh identity, last agent in the window        -> killed, PANE ONLY:
#     the window and its companion stay (a real minimonitor closes itself once
#     it is alone; the run kill never kills a window)
#   - the pane MOVED (join-pane) into another agent's window after discovery,
#     its cache still naming the source window          -> killed, pane only;
#     the destination window and its agent survive
#   - a helper of the harvested agent SWAPPED (swap-pane) with an unrelated
#     agent after the identity was read                 -> the incoming agent
#     survives; the harvested pane dies
#
# Runs on a private server (require_isolated_tmux). Skips if tmux is missing.
set -euo pipefail

if ! command -v tmux >/dev/null 2>&1; then
    echo "SKIP: tmux not available"
    exit 0
fi

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$REPO_ROOT/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
. "$REPO_ROOT/.aitask-scripts/lib/python_resolve.sh"
PYTHON_BIN="${PYTHON_BIN:-$(require_ait_python 2>/dev/null || echo python3)}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "SKIP: $PYTHON_BIN not available"
    exit 0
fi

# shellcheck source=lib/tmux_isolation.sh
. "$SCRIPT_DIR/lib/tmux_isolation.sh"
require_isolated_tmux

FIXTURE_DIR=$(mktemp -d "${TMPDIR:-/tmp}/ait_kill_guarded_XXXXXX")
trap 'TMUX_TMPDIR="$FIXTURE_DIR" tmux kill-server 2>/dev/null || true; rm -rf "$FIXTURE_DIR"' EXIT

(
    cd "$REPO_ROOT" || exit 1
    export TMUX_TMPDIR="$FIXTURE_DIR"
    unset TMUX
    SESSION="ait_killguard_$$"
    tmux new-session -d -s "$SESSION" -n "primary" -x 240 -y 80 "tail -f /dev/null"

    PYTHONPATH="$REPO_ROOT/.aitask-scripts" \
    AIT_TEST_TMUX_DIR="$FIXTURE_DIR" \
    AIT_TEST_SESSION="$SESSION" \
    "$PYTHON_BIN" - <<'PYEOF'
import asyncio
import os
import subprocess
import sys
import time

import monitor.monitor_core as mc
from monitor.tmux_monitor import TmuxMonitor, TmuxPaneInfo, PaneCategory

session = os.environ["AIT_TEST_SESSION"]
env = {**os.environ, "TMUX_TMPDIR": os.environ["AIT_TEST_TMUX_DIR"]}
env.pop("TMUX", None)
COMPANION_SENTINEL = "AIT_KILLGUARD_COMPANION_SENTINEL"


def _is_companion_test(pid):
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            return COMPANION_SENTINEL in f.read().decode("utf-8", "replace")
    except OSError:
        pass
    try:
        r = subprocess.run(["ps", "-p", str(pid), "-o", "args="],
                           capture_output=True, text=True, timeout=2)
        return r.returncode == 0 and COMPANION_SENTINEL in r.stdout
    except Exception:
        return False


mc._is_companion_process = _is_companion_test


def sub(args):
    r = subprocess.run(["tmux", *args], capture_output=True, text=True,
                       env=env, timeout=10)
    return r.returncode, r.stdout or ""


def fail(msg):
    sys.exit(f"FAIL: {msg}")


def new_pane(target, cmd="tail -f /dev/null", split=True):
    verb = ["split-window", "-d", "-t", target] if split else \
        ["new-window", "-d", "-t", session, "-n", target.split(":")[-1]]
    rc, out = sub([*verb, "-P", "-F", "#{pane_id}", cmd])
    if rc != 0 or not out.strip():
        fail(f"fixture: could not create a pane ({rc}, {out!r})")
    return out.strip()


def identity(pane_id):
    rc, out = sub(["display-message", "-p", "-t", pane_id,
                   mc.RUN_IDENTITY_FORMAT])
    ident = mc.parse_run_identity(rc, out, pane_id)
    if ident is None:
        fail(f"could not read the identity of {pane_id}: {rc} {out!r}")
    return ident


def pane_alive(pane_id):
    rc, out = sub(["list-panes", "-a", "-F", "#{pane_id}"])
    return pane_id in out.split()


def pane_pid(pane_id):
    rc, out = sub(["display-message", "-p", "-t", pane_id, "#{pane_pid}"])
    return out.strip()


def window_exists(name):
    rc, out = sub(["list-windows", "-t", session, "-F", "#{window_name}"])
    return name in out.split()


def cache(monitor, window, agents, companion):
    rc, out = sub(["list-panes", "-t", f"{session}:{window}", "-F", "\t".join([
        "#{window_index}", "#{window_name}", "#{pane_index}", "#{pane_id}",
        "#{pane_pid}", "#{pane_current_command}", "#{pane_width}",
        "#{pane_height}"])])
    for line in out.strip().splitlines():
        wi, wn, pi, pid, ppid, cmd, w, h = line.split("\t")
        if pid not in agents and pid != companion:
            continue
        monitor._pane_cache[pid] = TmuxPaneInfo(
            window_index=wi, window_name=wn, pane_index=pi, pane_id=pid,
            pane_pid=int(ppid), current_command=cmd, width=int(w),
            height=int(h),
            category=PaneCategory.AGENT if pid in agents else PaneCategory.OTHER,
            session_name=session)


def run_pass(label, with_backend):
    print(f"== pass: {label} ==")
    win = f"kg_{label}"
    a1 = new_pane(f"{session}:{win}", split=False)
    a2 = new_pane(f"{session}:{win}")
    companion = new_pane(
        f"{session}:{win}",
        f"sh -c 'exec -a {COMPANION_SENTINEL} sleep 86400'")
    helper = new_pane(f"{session}:{win}")
    sub(["set-option", "-p", "-t", helper, "@aitask_shadow_target", a1])
    time.sleep(0.3)

    monitor = TmuxMonitor(session=session)
    if with_backend:
        if not asyncio.run(monitor.start_control_client()):
            fail(f"{label}: control client failed to start")
    cache(monitor, win, [a1, a2], companion)

    # 1. Same pane id, another process: the guard must refuse.
    stale = identity(a1)
    sub(["respawn-pane", "-k", "-t", a1, "tail -f /dev/null"])
    time.sleep(0.2)
    if pane_pid(a1) == stale.pane_pid:
        fail(f"{label}: fixture respawn kept the pid")
    status, collapsed = monitor.kill_agent_run_guarded(stale)
    if (status, collapsed) != ("changed", False) or not pane_alive(a1):
        fail(f"{label}: respawned pane -> {(status, collapsed)}, "
             f"alive={pane_alive(a1)}")
    if not pane_alive(helper):
        fail(f"{label}: a refused kill swept the helper")

    # 2. Frozen after the read: the guard must refuse.
    fresh = identity(a1)
    sub(["set-option", "-p", "-t", a1, mc.FROZEN_OPTION, "deadbeef"])
    status, _ = monitor.kill_agent_run_guarded(fresh)
    if status != "changed" or not pane_alive(a1):
        fail(f"{label}: frozen pane -> {status}, alive={pane_alive(a1)}")
    sub(["set-option", "-pu", "-t", a1, mc.FROZEN_OPTION])

    # 3. A malformed identity dispatches nothing.
    bad = mc.RunIdentity(a1, "12;kill-server", fresh.server_pid, "")
    if monitor.kill_agent_run_guarded(bad) != ("failed", False):
        fail(f"{label}: malformed identity was not refused")
    if not pane_alive(a1):
        fail(f"{label}: malformed identity killed the pane")

    # 4. The harvested run itself, with another agent beside it: pane only.
    status, collapsed = monitor.kill_agent_run_guarded(identity(a1))
    if (status, collapsed) != ("killed", False):
        fail(f"{label}: kill A1 -> {(status, collapsed)}")
    if pane_alive(a1) or not pane_alive(a2) or not pane_alive(companion):
        fail(f"{label}: wrong panes after the A1 kill")
    if pane_alive(helper):
        fail(f"{label}: A1's bound helper outlived it")

    # 5. The last agent: still the pane only. The window and its companion
    # stay; a real minimonitor companion closes itself once it is alone.
    status, collapsed = monitor.kill_agent_run_guarded(identity(a2))
    if (status, collapsed) != ("killed", False) or pane_alive(a2):
        fail(f"{label}: kill A2 -> {(status, collapsed)}")
    if not window_exists(win) or not pane_alive(companion):
        fail(f"{label}: the run kill took the window or the companion")

    # 6. Moved since discovery: the cache still names the source window, where
    # the harvested agent sat alone with its companion. It now shares the
    # destination window with another agent, so only the pane may go.
    src, dst = f"kgm_{label}", f"kgd_{label}"
    moved = new_pane(f"{session}:{src}", split=False)
    src_companion = new_pane(
        f"{session}:{src}",
        f"sh -c 'exec -a {COMPANION_SENTINEL} sleep 86400'")
    other = new_pane(f"{session}:{dst}", split=False)
    time.sleep(0.3)
    cache(monitor, src, [moved], src_companion)
    harvested = identity(moved)
    rc, _ = sub(["join-pane", "-d", "-s", moved, "-t", other])
    if rc != 0:
        fail(f"{label}: fixture join-pane failed")
    if identity(moved).pane_pid != harvested.pane_pid:
        fail(f"{label}: fixture move changed the pid")
    status, collapsed = monitor.kill_agent_run_guarded(harvested)
    if (status, collapsed) != ("killed", False):
        fail(f"{label}: moved pane -> {(status, collapsed)}")
    if not pane_alive(other) or not window_exists(dst):
        fail(f"{label}: the destination window or its agent was killed")
    if pane_alive(moved):
        fail(f"{label}: the moved harvested pane survived")

    # 7. One swap-pane after the identity was read: the harvested agent's
    # window now holds an unrelated agent in its helper's place, with the same
    # window id and pane count. That agent must survive.
    hw, ow = f"kgs_{label}", f"kgo_{label}"
    harvested_pane = new_pane(f"{session}:{hw}", split=False)
    its_helper = new_pane(f"{session}:{hw}")
    sub(["set-option", "-p", "-t", its_helper, "@aitask_shadow_target",
         harvested_pane])
    stranger = new_pane(f"{session}:{ow}", split=False)
    time.sleep(0.3)
    cache(monitor, hw, [harvested_pane], its_helper)
    harvested = identity(harvested_pane)
    rc, _ = sub(["swap-pane", "-d", "-s", its_helper, "-t", stranger])
    if rc != 0:
        fail(f"{label}: fixture swap-pane failed")
    status, collapsed = monitor.kill_agent_run_guarded(harvested)
    if (status, collapsed) != ("killed", False):
        fail(f"{label}: swapped window -> {(status, collapsed)}")
    if not pane_alive(stranger):
        fail(f"{label}: the agent swapped into the window was killed")
    if pane_alive(harvested_pane):
        fail(f"{label}: the harvested pane survived")

    if with_backend:
        asyncio.run(monitor.close_control_client())
    print(f"OK {label}")


run_pass("ctrl", with_backend=True)
run_pass("sub", with_backend=False)
print("OK kill_agent_run_guarded")
PYEOF
)

echo "PASS: tests/test_kill_agent_run_guarded.sh"
