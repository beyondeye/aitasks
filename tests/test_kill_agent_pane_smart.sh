#!/usr/bin/env bash
# End-to-end regression test for `TmuxMonitor.kill_agent_pane_smart`.
#
# Two passes against the same fixture shape:
#   Pass 1: control-client backend started (TmuxControlBackend route)
#   Pass 2: backend never started (subprocess fallback inside tmux_run)
#
# Each pass verifies the smart-kill heuristic:
#   - Killing one of two agent panes preserves the surviving agent and the
#     companion (minimonitor) pane; window stays alive.
#   - Killing the last agent pane collapses the entire window (which also
#     cleans up the companion pane).
#
# `_is_companion_process` is monkey-patched to recognise the test's
# companion-stand-in (a sleep loop with a unique sentinel argv) — the real
# heuristic depends on `/proc/<pid>/cmdline` containing "minimonitor" or
# "monitor_app", which is too brittle to construct in a unit test fixture.
#
# Skips cleanly if tmux is not on PATH.
set -euo pipefail

if ! command -v tmux >/dev/null 2>&1; then
    echo "SKIP: tmux not available"
    exit 0
fi

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "SKIP: $PYTHON_BIN not available"
    exit 0
fi

FIXTURE_DIR=$(mktemp -d "${TMPDIR:-/tmp}/ait_kill_smart_XXXXXX")
trap 'TMUX_TMPDIR="$FIXTURE_DIR" tmux kill-server 2>/dev/null || true; rm -rf "$FIXTURE_DIR"' EXIT

(
    cd "$REPO_ROOT"
    export TMUX_TMPDIR="$FIXTURE_DIR"
    unset TMUX
    SESSION="ait_killsmart_$$"
    tmux new-session -d -s "$SESSION" -n "primary" "tail -f /dev/null"

    PYTHONPATH="$REPO_ROOT/.aitask-scripts" \
    AIT_TEST_TMUX_DIR="$FIXTURE_DIR" \
    AIT_TEST_SESSION="$SESSION" \
    "$PYTHON_BIN" - <<'PYEOF'
import asyncio
import os
import subprocess
import sys
import time

import monitor.tmux_monitor as tm
from monitor.tmux_monitor import TmuxMonitor, TmuxPaneInfo, PaneCategory

session = os.environ["AIT_TEST_SESSION"]
tmux_dir = os.environ["AIT_TEST_TMUX_DIR"]
env = {**os.environ, "TMUX_TMPDIR": tmux_dir}
env.pop("TMUX", None)

# Sentinel that uniquely identifies the companion stand-in. We monkey-patch
# `_is_companion_process` to flag any pid whose argv contains the sentinel.
COMPANION_SENTINEL = "AIT_KILLSMART_COMPANION_SENTINEL"


def _is_companion_test(pid):
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            cmdline = f.read().decode("utf-8", errors="replace")
        if COMPANION_SENTINEL in cmdline:
            return True
    except OSError:
        pass
    # macOS fallback path
    try:
        r = subprocess.run(
            ["ps", "-p", str(pid), "-o", "args="],
            capture_output=True, text=True, timeout=2,
        )
        return r.returncode == 0 and COMPANION_SENTINEL in r.stdout
    except Exception:
        return False


tm._is_companion_process = _is_companion_test


def sub(args):
    r = subprocess.run(
        ["tmux", *args], capture_output=True, text=True, env=env, timeout=10,
    )
    return r.returncode, r.stdout or ""


def make_window(name):
    """Build a window with two agent panes + one companion pane.

    Layout (3 panes total):
      - pane 0: shell sleep (treated as agent A1)
      - pane 1: shell sleep (treated as agent A2)
      - pane 2: companion (sleep loop with COMPANION_SENTINEL in argv)
    """
    sub(["new-window", "-t", session, "-n", name, "tail -f /dev/null"])
    # Add second agent pane
    sub(["split-window", "-t", f"{session}:{name}", "tail -f /dev/null"])
    # Add companion with the sentinel embedded in argv. We build argv
    # carefully so the sentinel is searchable in /proc/<pid>/cmdline.
    sub([
        "split-window", "-t", f"{session}:{name}",
        f"sh -c 'exec -a {COMPANION_SENTINEL} sleep 86400'",
    ])
    time.sleep(0.2)  # let panes spawn

    rc, out = sub([
        "list-panes", "-t", f"{session}:{name}",
        "-F", "#{pane_id}\t#{pane_pid}",
    ])
    panes = []
    for line in out.strip().splitlines():
        pid_str, pane_pid_str = line.split("\t")
        panes.append((pid_str, int(pane_pid_str)))
    if len(panes) != 3:
        sys.exit(f"fixture build: expected 3 panes, got {panes!r}")

    # Identify which pane is the companion (sentinel match)
    companion_id = None
    agents = []
    for pid_str, pane_pid in panes:
        # Walk children of pane_pid to find the actual sleep process
        is_companion = False
        for cand in [pane_pid, *_descendant_pids(pane_pid)]:
            if _is_companion_test(cand):
                is_companion = True
                break
        if is_companion:
            companion_id = pid_str
        else:
            agents.append(pid_str)

    if companion_id is None or len(agents) != 2:
        sys.exit(
            f"fixture build: companion={companion_id!r} agents={agents!r}"
        )
    return agents, companion_id


def _descendant_pids(pid):
    """Return the set of descendant PIDs of `pid` (best-effort, Linux /proc)."""
    out = []
    try:
        result = subprocess.run(
            ["ps", "--ppid", str(pid), "-o", "pid="],
            capture_output=True, text=True, timeout=2,
        )
    except Exception:
        return out
    if result.returncode != 0:
        return out
    for line in result.stdout.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            child = int(line)
        except ValueError:
            continue
        out.append(child)
        out.extend(_descendant_pids(child))
    return out


def populate_pane_cache(monitor, agents, companion):
    """Seed _pane_cache with TmuxPaneInfo for the test panes so
    kill_agent_pane_smart resolves session_name + window_index correctly.
    """
    rc, out = sub([
        "list-panes", "-t", f"{session}",
        "-F", "\t".join([
            "#{window_index}", "#{window_name}", "#{pane_index}",
            "#{pane_id}", "#{pane_pid}", "#{pane_current_command}",
            "#{pane_width}", "#{pane_height}",
        ]),
    ])
    for line in out.strip().splitlines():
        parts = line.split("\t")
        if len(parts) != 8:
            continue
        win_idx, win_name, pane_idx, pane_id, pane_pid, cmd, w, h = parts
        if pane_id not in agents and pane_id != companion:
            continue
        monitor._pane_cache[pane_id] = TmuxPaneInfo(
            window_index=win_idx,
            window_name=win_name,
            pane_index=pane_idx,
            pane_id=pane_id,
            pane_pid=int(pane_pid),
            current_command=cmd,
            width=int(w),
            height=int(h),
            category=PaneCategory.AGENT if pane_id in agents else PaneCategory.OTHER,
            session_name=session,
        )


def assert_window_panes(window_name, expected_pane_ids):
    rc, out = sub([
        "list-panes", "-t", f"{session}:{window_name}",
        "-F", "#{pane_id}",
    ])
    actual = set(out.strip().splitlines())
    expected = set(expected_pane_ids)
    if actual != expected:
        sys.exit(
            f"window {window_name!r} panes: expected {expected!r}, got {actual!r}"
        )


def assert_window_absent(window_name):
    rc, out = sub([
        "list-windows", "-t", session, "-F", "#{window_name}",
    ])
    if window_name in out.strip().splitlines():
        sys.exit(f"window {window_name!r} should be absent: {out!r}")


def run_pass(label, with_backend):
    print(f"== pass: {label} ==")
    win_name = f"kp_{label}"
    agents, companion = make_window(win_name)
    a1, a2 = agents

    monitor = TmuxMonitor(session=session)
    if with_backend:
        ok = asyncio.run(monitor.start_control_client())
        assert ok, f"{label}: control client failed to start"
        assert monitor.has_control_client()

    populate_pane_cache(monitor, agents, companion)

    # Step 1: kill A1 — should kill pane only, preserve A2 + companion.
    ok, killed_window = monitor.kill_agent_pane_smart(a1)
    assert ok and not killed_window, (
        f"{label}: kill A1 returned ({ok}, {killed_window})"
    )
    assert_window_panes(win_name, [a2, companion])

    # Step 2: kill A2 — last agent → window collapses (taking companion).
    ok, killed_window = monitor.kill_agent_pane_smart(a2)
    assert ok and killed_window, (
        f"{label}: kill A2 returned ({ok}, {killed_window})"
    )
    assert_window_absent(win_name)

    if with_backend:
        asyncio.run(monitor.close_control_client())
    print(f"OK {label}")


run_pass("ctrl", with_backend=True)
run_pass("sub", with_backend=False)

print("OK kill_agent_pane_smart")
PYEOF
)

echo "PASS: tests/test_kill_agent_pane_smart.sh"
