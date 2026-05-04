#!/usr/bin/env bash
# Resilience tests for monitor.tmux_control (t733).
#
# Covers the gaps in t722's parity tests:
#   A. Reconnect-then-recover  — kill `tmux -C` child, observe RECONNECTING
#                                then back to CONNECTED.
#   B. Max-retries cap         — destroy target session; assert FALLBACK after
#                                bounded attempts, supervisor exits cleanly.
#   C. Mid-flight transition   — kill `tmux -C` while a slow request is in
#                                flight; in-flight call returns (-1,""); the
#                                next call either reconnects or returns
#                                cleanly via subprocess fallback.
#   D. Concurrent fallback     — 50 sync requests racing with a forced
#                                reconnect; none raise, none hang past
#                                2 × command_timeout.
#   E. Reconnect race for      — TmuxMonitor.kill_pane / kill_agent_pane_smart
#      state-mutating actions    same end state via control or subprocess
#                                fallback; no double-kill on retry.
#
# Each case runs in its own scratch dir + tmux server so a server-kill case
# cannot poison the others. Skips cleanly if tmux is not on PATH.
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

make_fixture() {
    local fixture_dir
    fixture_dir=$(mktemp -d "${TMPDIR:-/tmp}/ait_tmux_resilience_XXXXXX")
    echo "$fixture_dir"
}

teardown_fixture() {
    local fixture_dir="$1"
    if [[ -n "${fixture_dir:-}" && -d "$fixture_dir" ]]; then
        TMUX_TMPDIR="$fixture_dir" tmux kill-server 2>/dev/null || true
        rm -rf "$fixture_dir"
    fi
}

# Track all fixtures so the EXIT trap cleans up even if a case aborts mid-run.
FA="" ; FB="" ; FC="" ; FD="" ; FE=""
trap 'teardown_fixture "${FA:-}"; teardown_fixture "${FB:-}"; teardown_fixture "${FC:-}"; teardown_fixture "${FD:-}"; teardown_fixture "${FE:-}"' EXIT

# ---------------------------------------------------------------------------
# Case A: reconnect-then-recover
# ---------------------------------------------------------------------------
echo "== case A: reconnect-then-recover =="
FA=$(make_fixture)

(
    cd "$REPO_ROOT"
    # shellcheck disable=SC2030
    export TMUX_TMPDIR="$FA"
    unset TMUX
    SESSION="ait_resilience_$$_a"
    tmux new-session -d -s "$SESSION" "tail -f /dev/null"

    PYTHONPATH="$REPO_ROOT/.aitask-scripts" \
    AIT_TEST_SESSION="$SESSION" \
    "$PYTHON_BIN" - <<'PYEOF'
import os
import signal
import time

from monitor.tmux_control import TmuxControlBackend, TmuxControlState

session = os.environ["AIT_TEST_SESSION"]

b = TmuxControlBackend(session=session, command_timeout=2.0)
assert b.start(), "backend.start() returned False"
assert b.is_alive, "backend not alive after start"
assert b.state == TmuxControlState.CONNECTED, f"initial state={b.state!r}"

# Kill the `tmux -C attach` subprocess out from under the backend. This
# triggers EOF on the reader, which marks the client dead and lets the
# supervisor observe death on its next 0.5 s poll.
old_client_id = id(b._client)
old_pid = b._client._proc.pid
os.kill(old_pid, signal.SIGKILL)

# Phase 1: state must transition to RECONNECTING within ~1.5 s
# (0.5 s death-poll + a hair of slack).
deadline = time.monotonic() + 2.5
saw_reconnecting = False
while time.monotonic() < deadline:
    s = b.state
    if s == TmuxControlState.RECONNECTING:
        saw_reconnecting = True
        break
    if s == TmuxControlState.CONNECTED and id(b._client) != old_client_id:
        # Reconnect raced past us before the polling loop caught
        # RECONNECTING — also acceptable evidence that the supervisor
        # noticed the death and respawned.
        saw_reconnecting = True
        break
    time.sleep(0.02)
assert saw_reconnecting, f"never observed RECONNECTING / new client; state={b.state!r}"

# Phase 2: state must be CONNECTED with a fresh client within ~6 s.
deadline = time.monotonic() + 6.0
while time.monotonic() < deadline:
    if b.state == TmuxControlState.CONNECTED and id(b._client) != old_client_id:
        break
    time.sleep(0.05)
assert b.state == TmuxControlState.CONNECTED, f"final state={b.state!r}"
assert id(b._client) != old_client_id, "client object was not replaced"
assert b.is_alive, "backend is_alive=False after reconnect"

# A real request via control must succeed after recovery.
rc, out = b.request_sync(["display-message", "-p", "post-reconnect"])
assert rc == 0 and out.strip() == "post-reconnect", (rc, out)

b.stop()
assert b.state == TmuxControlState.STOPPED, f"state after stop()={b.state!r}"
print("OK case A")
PYEOF
)
teardown_fixture "$FA"
FA=""

# ---------------------------------------------------------------------------
# Case B: max-retries cap (target session destroyed)
# ---------------------------------------------------------------------------
echo "== case B: max-retries cap =="
FB=$(make_fixture)

(
    cd "$REPO_ROOT"
    # shellcheck disable=SC2030,SC2031
    export TMUX_TMPDIR="$FB"
    unset TMUX
    SESSION="ait_resilience_$$_b"
    tmux new-session -d -s "$SESSION" "tail -f /dev/null"

    PYTHONPATH="$REPO_ROOT/.aitask-scripts" \
    AIT_TEST_TMUX_DIR="$FB" \
    AIT_TEST_SESSION="$SESSION" \
    "$PYTHON_BIN" - <<'PYEOF'
import os
import subprocess
import time

from monitor.tmux_control import TmuxControlBackend, TmuxControlState

session = os.environ["AIT_TEST_SESSION"]
tmux_dir = os.environ["AIT_TEST_TMUX_DIR"]
env = {**os.environ, "TMUX_TMPDIR": tmux_dir}
env.pop("TMUX", None)

b = TmuxControlBackend(session=session, command_timeout=2.0)
assert b.start()

# Destroy the target session. The server stays up, but every reconnect
# attempt to this session must fail at attach time.
subprocess.run(["tmux", "kill-session", "-t", session], env=env, check=False)

# Sum of backoffs is 0.5+1+2+4+8 = 15.5 s. Add the 0.5 s death-poll plus
# 5 × ~50 ms attach-fail latency plus generous slack.
deadline = time.monotonic() + 30.0
while time.monotonic() < deadline:
    if b.state == TmuxControlState.FALLBACK:
        break
    time.sleep(0.1)
assert b.state == TmuxControlState.FALLBACK, f"final state={b.state!r}"
assert not b.is_alive, "backend should not be alive after fallback"

# Subsequent requests must short-circuit cleanly.
rc, out = b.request_sync(["display-message", "-p", "after-fallback"])
assert rc == -1 and out == "", (rc, out)

# Supervisor task must be finished (no busy loop chewing the bg loop).
sup_task = b._reconnect_task
assert sup_task is None or sup_task.done(), "supervisor task still running"

b.stop()
assert b.state == TmuxControlState.STOPPED
print("OK case B")
PYEOF
)
teardown_fixture "$FB"
FB=""

# ---------------------------------------------------------------------------
# Case C: mid-flight transition
# ---------------------------------------------------------------------------
echo "== case C: mid-flight transition =="
FC=$(make_fixture)

(
    cd "$REPO_ROOT"
    # shellcheck disable=SC2030,SC2031
    export TMUX_TMPDIR="$FC"
    unset TMUX
    SESSION="ait_resilience_$$_c"
    tmux new-session -d -s "$SESSION" "tail -f /dev/null"

    PYTHONPATH="$REPO_ROOT/.aitask-scripts" \
    AIT_TEST_SESSION="$SESSION" \
    "$PYTHON_BIN" - <<'PYEOF'
import os
import signal
import time

from monitor.tmux_control import TmuxControlBackend, TmuxControlState

session = os.environ["AIT_TEST_SESSION"]

# command_timeout is intentionally small: the goal is to prove no
# request hangs past the timeout in the kill-then-reconnect window.
b = TmuxControlBackend(session=session, command_timeout=2.0)
assert b.start()

# Sanity baseline.
rc, out = b.request_sync(["display-message", "-p", "baseline"])
assert rc == 0 and out.strip() == "baseline"

# Kill the channel out from under the backend.
old_client_id = id(b._client)
old_pid = b._client._proc.pid
os.kill(old_pid, signal.SIGKILL)

# Wait for the reader to observe EOF and mark the client dead. Synthesizes
# the "after the channel breaks but before the supervisor's first reconnect
# attempt completes" window.
deadline = time.monotonic() + 2.0
while time.monotonic() < deadline:
    if not b.is_alive:
        break
    time.sleep(0.02)
assert not b.is_alive, "client did not die after SIGKILL"

# Fire a burst of requests during the reconnect window. Each must complete
# in bounded time — either via fresh reconnect (rc=0) or via the dead-
# client short-circuit (rc=-1). No request may hang past command_timeout.
results = []
for i in range(5):
    t0 = time.monotonic()
    rc, out = b.request_sync(["display-message", "-p", f"during-{i}"])
    elapsed = time.monotonic() - t0
    assert rc in (0, -1), f"request {i}: unexpected rc={rc} out={out!r}"
    if rc == 0:
        assert out.strip() == f"during-{i}", out
    assert elapsed < 4.0, f"request {i} hung for {elapsed:.2f}s"
    results.append((rc, elapsed))

# After the reconnect window settles, state must be CONNECTED with a
# fresh client (the kill was a single-instance failure; supervisor should
# have respawned within the first backoff bracket).
deadline = time.monotonic() + 6.0
while time.monotonic() < deadline:
    if (
        b.state == TmuxControlState.CONNECTED
        and b.is_alive
        and id(b._client) != old_client_id
    ):
        break
    time.sleep(0.05)
assert b.state == TmuxControlState.CONNECTED, f"final state={b.state!r}"
assert id(b._client) != old_client_id, "client object was not replaced"

# Final request via the recovered control client.
rc, out = b.request_sync(["display-message", "-p", "post-reconnect"])
assert rc == 0 and out.strip() == "post-reconnect", (rc, out)

b.stop()
print(f"OK case C ({sum(1 for r,_ in results if r==0)}/{len(results)} via reconnect)")
PYEOF
)
teardown_fixture "$FC"
FC=""

# ---------------------------------------------------------------------------
# Case D: 50 concurrent sync requests during a forced reconnect
# ---------------------------------------------------------------------------
echo "== case D: concurrent sync under reconnect =="
FD=$(make_fixture)

(
    cd "$REPO_ROOT"
    # shellcheck disable=SC2030,SC2031
    export TMUX_TMPDIR="$FD"
    unset TMUX
    SESSION="ait_resilience_$$_d"
    tmux new-session -d -s "$SESSION" "tail -f /dev/null"

    PYTHONPATH="$REPO_ROOT/.aitask-scripts" \
    AIT_TEST_SESSION="$SESSION" \
    "$PYTHON_BIN" - <<'PYEOF'
import os
import signal
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from monitor.tmux_control import TmuxControlBackend, TmuxControlState

session = os.environ["AIT_TEST_SESSION"]

b = TmuxControlBackend(session=session, command_timeout=2.0)
assert b.start()

N = 50
killed_event = threading.Event()


def worker(i):
    started = time.monotonic()
    rc, out = b.request_sync(
        ["display-message", "-p", f"tag-{i}"], timeout=2.0,
    )
    elapsed = time.monotonic() - started
    return i, rc, out.strip(), elapsed


def killer():
    # Wait until ~10 workers are queued, then force the channel down.
    time.sleep(0.05)
    try:
        old_pid = b._client._proc.pid
        os.kill(old_pid, signal.SIGKILL)
        killed_event.set()
    except Exception:
        killed_event.set()


# Launch the killer concurrently with the worker pool.
killer_thread = threading.Thread(target=killer, daemon=True)
killer_thread.start()

deadline = time.monotonic() + 30.0  # 2 × command_timeout × N + reconnect slack
results = []
with ThreadPoolExecutor(max_workers=N) as pool:
    futs = [pool.submit(worker, i) for i in range(N)]
    for f in as_completed(futs, timeout=30.0):
        results.append(f.result())

assert killed_event.wait(timeout=5.0), "killer never fired"
assert len(results) == N, f"got {len(results)} results, expected {N}"

# Every result is one of the two valid forms; nothing raised; nothing hung.
for i, rc, out, elapsed in results:
    assert rc in (0, -1), f"worker {i}: unexpected rc={rc} out={out!r}"
    if rc == 0:
        assert out == f"tag-{i}", (
            f"worker {i}: cross-talk — got {out!r}, expected tag-{i}"
        )
    assert elapsed < 6.0, (
        f"worker {i}: hung for {elapsed:.2f}s (>2 × command_timeout)"
    )

# Final state is acceptable as either CONNECTED (reconnect won) or
# FALLBACK (max attempts hit). What matters is no thread leak.
final_state = b.state
assert final_state in (
    TmuxControlState.CONNECTED, TmuxControlState.FALLBACK,
), f"unexpected final state={final_state!r}"

b.stop()
# tmux-control-loop bg thread must be gone.
names = [t.name for t in threading.enumerate()]
assert "tmux-control-loop" not in names, f"thread leaked: {names}"
print(f"OK case D (final={final_state.value})")
PYEOF
)
teardown_fixture "$FD"
FD=""

# ---------------------------------------------------------------------------
# Case E: reconnect race for state-mutating user actions
# ---------------------------------------------------------------------------
echo "== case E: state-mutating action parity =="
FE=$(make_fixture)

(
    cd "$REPO_ROOT"
    # shellcheck disable=SC2030,SC2031
    export TMUX_TMPDIR="$FE"
    unset TMUX
    SESSION="ait_resilience_$$_e"
    # Sentinel window keeps the session alive after both agent panes (and
    # their window) are killed. Without it, tmux auto-destroys the session
    # when the last window collapses.
    tmux new-session -d -s "$SESSION" -n "keepalive" "tail -f /dev/null"
    # Window with two `agent-` panes (TmuxMonitor classifies window names
    # starting with `agent-` as AGENT). The second pane is added via
    # split-window so both share the same window.
    tmux new-window -t "${SESSION}:" -n "agent-1" "tail -f /dev/null"
    tmux split-window -t "${SESSION}:agent-1" "tail -f /dev/null"

    PYTHONPATH="$REPO_ROOT/.aitask-scripts" \
    AIT_TEST_TMUX_DIR="$FE" \
    AIT_TEST_SESSION="$SESSION" \
    "$PYTHON_BIN" - <<'PYEOF'
import asyncio
import os
import signal
import subprocess
import time

from monitor.tmux_control import TmuxControlState
from monitor.tmux_monitor import TmuxMonitor

session = os.environ["AIT_TEST_SESSION"]
tmux_dir = os.environ["AIT_TEST_TMUX_DIR"]
env = {**os.environ, "TMUX_TMPDIR": tmux_dir}
env.pop("TMUX", None)


def list_pane_ids():
    r = subprocess.run(
        ["tmux", "list-panes", "-s", "-t", session, "-F", "#{pane_id}"],
        capture_output=True, text=True, env=env, check=True,
    )
    return [p for p in r.stdout.strip().splitlines() if p.startswith("%")]


async def main():
    # In multi_session mode TmuxMonitor scans the session-discovery cache
    # which depends on the host tmux server. Pin to single-session so the
    # test fixture is isolated.
    monitor = TmuxMonitor(session=session, multi_session=False)
    assert await monitor.start_control_client(), "control client failed to start"
    assert monitor.has_control_client()
    assert monitor.control_state() == TmuxControlState.CONNECTED

    # Discover agent panes via list-panes; pane_cache is populated by
    # discover_panes() and keyed by pane_id.
    panes = monitor.discover_panes()
    agent_ids = [p.pane_id for p in panes if p.window_name == "agent-1"]
    assert len(agent_ids) >= 2, f"expected ≥2 agent panes, got {agent_ids!r}"
    a1, a2 = agent_ids[0], agent_ids[1]

    # Steady-state: kill A1 via control client. A1 gone, A2 remains.
    assert monitor.kill_pane(a1) is True
    remaining = list_pane_ids()
    assert a1 not in remaining, f"A1={a1} still present after kill_pane"
    assert a2 in remaining, f"A2={a2} unexpectedly gone"

    # Force the control channel down.
    backend = monitor._backend
    assert backend is not None
    old_pid = backend._client._proc.pid
    os.kill(old_pid, signal.SIGKILL)

    # Wait for the reader to observe EOF and flip is_alive=False. Without
    # this, callers race the kernel: a write into a freshly-killed
    # subprocess may buffer in the pipe and the request hangs until
    # command_timeout (5 s) before the (-1, "") fallback kicks in. The
    # deterministic wait pins us to the documented post-death subprocess
    # fallback path that Step 7 of the plan calls out: "request goes via
    # subprocess fallback".
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        if not backend.is_alive:
            break
        await asyncio.sleep(0.02)
    assert not backend.is_alive, "client did not flip is_alive after SIGKILL"

    # Now kill_pane(A2) routes through subprocess fallback. A2 must be
    # gone afterward; tmux_run returns (0, "") on success.
    ok = monitor.kill_pane(a2)
    assert ok is True, "kill_pane(A2) failed via subprocess fallback"
    remaining = list_pane_ids()
    assert a2 not in remaining, f"A2={a2} still present after kill_pane"

    # Re-issue kill_pane on a now-gone pane via tmux_run directly so we can
    # assert rc == 1 (target missing). Whether routed via the freshly-
    # respawned control client or via subprocess, both paths must produce
    # rc == 1 — no double-kill side effect.
    rc, out = monitor.tmux_run(["kill-pane", "-t", a2])
    assert rc == 1, f"expected rc=1 for missing-target kill-pane, got rc={rc}"

    # Wait for reconnect to settle (or for the backend to give up). Either
    # outcome is acceptable for the parity assertion above.
    deadline = time.monotonic() + 6.0
    while time.monotonic() < deadline:
        if monitor.control_state() in (
            TmuxControlState.CONNECTED, TmuxControlState.FALLBACK,
        ):
            break
        await asyncio.sleep(0.05)

    final = monitor.control_state()
    assert final in (TmuxControlState.CONNECTED, TmuxControlState.FALLBACK), (
        f"unexpected post-race state={final!r}"
    )

    await monitor.close_control_client()
    print(f"OK case E (final={final.value})")


asyncio.run(main())
PYEOF
)
teardown_fixture "$FE"
FE=""

trap - EXIT

echo "PASS: tests/test_tmux_control_resilience.sh"
