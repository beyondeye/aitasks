#!/usr/bin/env bash
# Integration test for monitor.tmux_control.TmuxControlClient.
#
# Spawns an isolated tmux server (`TMUX_TMPDIR=$(mktemp -d)`, `unset TMUX`),
# creates a session with a few panes, then exercises the control client
# from a Python helper. Each case runs in its own server to keep state
# isolated.
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

# Each test case gets its own scratch dir + server so a server-kill case
# can't poison the others.
make_fixture() {
    local fixture_dir
    fixture_dir=$(mktemp -d "${TMPDIR:-/tmp}/ait_tmux_control_XXXXXX")
    echo "$fixture_dir"
}

teardown_fixture() {
    local fixture_dir="$1"
    if [[ -n "${fixture_dir:-}" && -d "$fixture_dir" ]]; then
        TMUX_TMPDIR="$fixture_dir" tmux kill-server 2>/dev/null || true
        rm -rf "$fixture_dir"
    fi
}

# ---------------------------------------------------------------------------
# Case 1: smoke + parity + concurrent + error
# ---------------------------------------------------------------------------
echo "== case 1: smoke + parity + concurrent + error =="
F1=$(make_fixture)
trap 'teardown_fixture "$F1"; teardown_fixture "${F2:-}"' EXIT

(
    cd "$REPO_ROOT"
    # shellcheck disable=SC2030  # subshell-scoped export is intentional (case isolation)
    export TMUX_TMPDIR="$F1"
    unset TMUX
    SESSION="ait_test_$$_a"
    tmux new-session -d -s "$SESSION" "tail -f /dev/null"
    for i in 1 2 3 4 5; do
        tmux new-window -t "${SESSION}:" -n "agent-${i}" "tail -f /dev/null"
    done

    PYTHONPATH="$REPO_ROOT/.aitask-scripts" \
    AIT_TEST_TMUX_DIR="$F1" \
    AIT_TEST_SESSION="$SESSION" \
    "$PYTHON_BIN" - <<'PYEOF'
import asyncio
import os
import subprocess
import sys

from monitor.tmux_control import TmuxControlClient

session = os.environ["AIT_TEST_SESSION"]
tmux_dir = os.environ["AIT_TEST_TMUX_DIR"]
env = {**os.environ, "TMUX_TMPDIR": tmux_dir}
env.pop("TMUX", None)


def subprocess_tmux(args):
    r = subprocess.run(
        ["tmux", *args], capture_output=True, text=True, env=env, timeout=10,
    )
    return r.returncode, r.stdout


async def main():
    c = TmuxControlClient(session=session)
    assert await c.start(), "start() returned False"
    assert c.is_alive

    # Case 1a: parity smoke — display-message #S
    rc, out = await c.request(["display-message", "-p", "#S"])
    assert rc == 0, f"display-message rc={rc} out={out!r}"
    assert out.strip() == session, f"display-message body={out!r}"

    sub_rc, sub_out = subprocess_tmux(["display-message", "-p", "#S"])
    assert (rc, out.strip()) == (sub_rc, sub_out.strip()), (
        f"parity mismatch: ctrl={(rc, out)} sub={(sub_rc, sub_out)}"
    )

    # Case 1b: parity smoke — list-panes -F with a tab-bearing format
    fmt = "#{window_index}\t#{window_name}\t#{pane_id}"
    rc, out = await c.request(["list-panes", "-s", "-t", session, "-F", fmt])
    assert rc == 0, f"list-panes rc={rc} out={out!r}"
    sub_rc, sub_out = subprocess_tmux(["list-panes", "-s", "-t", session, "-F", fmt])
    assert (rc, out) == (sub_rc, sub_out), (
        f"list-panes parity: ctrl={(rc, out)!r} sub={(sub_rc, sub_out)!r}"
    )

    # Case 1c: parity smoke — capture-pane -p
    # Pick an existing pane id from the previous output.
    first_pane = out.splitlines()[0].split("\t")[2]
    rc, out = await c.request(["capture-pane", "-p", "-t", first_pane])
    assert rc == 0, f"capture-pane rc={rc}"
    sub_rc, sub_out = subprocess_tmux(["capture-pane", "-p", "-t", first_pane])
    assert (rc, out) == (sub_rc, sub_out), "capture-pane parity mismatch"

    # Case 2: concurrent gather of 5 requests — all should resolve, no
    # cross-talk between futures
    results = await asyncio.gather(*(
        c.request(["display-message", "-p", "tick"]) for _ in range(5)
    ))
    for rc, out in results:
        assert rc == 0 and out.strip() == "tick", (rc, out)

    # Case 3: error response — invalid target session; rc should be
    # non-zero, no exception raised, client still alive.
    rc, out = await c.request(["list-panes", "-t", "no_such_session_xyz"])
    assert rc != 0, f"expected non-zero rc, got {rc} {out!r}"
    assert c.is_alive, "client died on bad command"

    await c.close()
    assert not c.is_alive
    print("OK case 1")


asyncio.run(main())
PYEOF
)
teardown_fixture "$F1"
F1=""

# ---------------------------------------------------------------------------
# Case 4: server-kill recovery
# ---------------------------------------------------------------------------
echo "== case 4: server-kill recovery =="
F2=$(make_fixture)

(
    cd "$REPO_ROOT"
    # shellcheck disable=SC2031  # subshell-scoped export is intentional (case isolation)
    export TMUX_TMPDIR="$F2"
    unset TMUX
    SESSION="ait_test_$$_b"
    tmux new-session -d -s "$SESSION" "tail -f /dev/null"
    tmux new-window -t "${SESSION}:" -n "agent-1" "tail -f /dev/null"

    PYTHONPATH="$REPO_ROOT/.aitask-scripts" \
    AIT_TEST_TMUX_DIR="$F2" \
    AIT_TEST_SESSION="$SESSION" \
    "$PYTHON_BIN" - <<'PYEOF'
import asyncio
import os
import subprocess

from monitor.tmux_control import TmuxControlClient

session = os.environ["AIT_TEST_SESSION"]
tmux_dir = os.environ["AIT_TEST_TMUX_DIR"]
env = {**os.environ, "TMUX_TMPDIR": tmux_dir}
env.pop("TMUX", None)


async def main():
    c = TmuxControlClient(session=session, command_timeout=2.0)
    assert await c.start()

    # Sanity: one good request first.
    rc, out = await c.request(["display-message", "-p", "alive"])
    assert rc == 0 and out.strip() == "alive", (rc, out)

    # Kill the server out from under the client.
    subprocess.run(["tmux", "kill-server"], env=env, check=False)

    # Give the reader a moment to observe EOF.
    for _ in range(50):
        if not c.is_alive:
            break
        await asyncio.sleep(0.05)

    assert not c.is_alive, "client should detect server death"

    # Subsequent requests must return (-1, "") without raising.
    rc, out = await c.request(["display-message", "-p", "after-kill"])
    assert rc == -1 and out == "", (rc, out)

    await c.close()
    print("OK case 4")


asyncio.run(main())
PYEOF
)
teardown_fixture "$F2"
F2=""

# ---------------------------------------------------------------------------
# Case 5: TmuxControlBackend smoke + sync wrapper basics
# ---------------------------------------------------------------------------
echo "== case 5: backend smoke =="
F5=$(make_fixture)
trap 'teardown_fixture "${F5:-}"; teardown_fixture "${F6:-}"; teardown_fixture "${F7:-}"; teardown_fixture "${F8:-}"; teardown_fixture "${F9:-}"; teardown_fixture "${F12:-}"' EXIT

(
    cd "$REPO_ROOT"
    # shellcheck disable=SC2030,SC2031  # subshell-scoped export is intentional (case isolation)
    export TMUX_TMPDIR="$F5"
    unset TMUX
    SESSION="ait_test_$$_e"
    tmux new-session -d -s "$SESSION" "tail -f /dev/null"
    for i in 1 2 3; do
        tmux new-window -t "${SESSION}:" -n "agent-${i}" "tail -f /dev/null"
    done

    PYTHONPATH="$REPO_ROOT/.aitask-scripts" \
    AIT_TEST_TMUX_DIR="$F5" \
    AIT_TEST_SESSION="$SESSION" \
    "$PYTHON_BIN" - <<'PYEOF'
import os
import threading
import time

from monitor.tmux_control import TmuxControlBackend

session = os.environ["AIT_TEST_SESSION"]

b = TmuxControlBackend(session=session, command_timeout=3.0)
assert b.start(), "backend.start() returned False"
assert b.is_alive, "backend not alive after start"
assert b._thread is not None and b._thread.is_alive(), "bg thread not alive"

# Smoke: display-message
rc, out = b.request_sync(["display-message", "-p", "#S"])
assert rc == 0, f"display-message rc={rc} out={out!r}"
assert out.strip() == session, f"display-message body={out!r}"

# Smoke: list-panes (multi-pane fixture)
rc, out = b.request_sync(["list-panes", "-s", "-t", session, "-F", "#{pane_id}"])
assert rc == 0
pane_ids = [p for p in out.strip().splitlines() if p.startswith("%")]
assert len(pane_ids) >= 4, f"expected >=4 panes, got {pane_ids!r}"

# Stop and verify thread joins quickly
t0 = time.monotonic()
b.stop()
elapsed = time.monotonic() - t0
assert elapsed < 4.0, f"stop() took {elapsed:.2f}s"
assert not b.is_alive, "backend still alive after stop"
assert b._thread is None, "thread reference not cleared after stop"

# After stop(), request_sync returns (-1, "") without raising
rc, out = b.request_sync(["display-message", "-p", "#S"])
assert rc == -1 and out == "", f"after-stop request returned ({rc}, {out!r})"

# Idempotent stop
b.stop()  # must not raise

# Bg thread name no longer in threading.enumerate()
names = [t.name for t in threading.enumerate()]
assert "tmux-control-loop" not in names, f"thread leaked: {names}"

print("OK case 5")
PYEOF
)
teardown_fixture "$F5"
F5=""

# ---------------------------------------------------------------------------
# Case 6: concurrent sync requests from N threads
# ---------------------------------------------------------------------------
echo "== case 6: concurrent sync requests =="
F6=$(make_fixture)

(
    cd "$REPO_ROOT"
    # shellcheck disable=SC2030,SC2031  # subshell-scoped export is intentional (case isolation)
    export TMUX_TMPDIR="$F6"
    unset TMUX
    SESSION="ait_test_$$_f"
    tmux new-session -d -s "$SESSION" "tail -f /dev/null"

    PYTHONPATH="$REPO_ROOT/.aitask-scripts" \
    AIT_TEST_TMUX_DIR="$F6" \
    AIT_TEST_SESSION="$SESSION" \
    "$PYTHON_BIN" - <<'PYEOF'
import os
from concurrent.futures import ThreadPoolExecutor

from monitor.tmux_control import TmuxControlBackend

session = os.environ["AIT_TEST_SESSION"]
b = TmuxControlBackend(session=session)
assert b.start()

# Each worker queries display-message with a unique payload; verifies that
# FIFO + asyncio.Lock keeps request/response correlation correct under
# contention (no cross-talk).
def worker(i):
    rc, out = b.request_sync(["display-message", "-p", f"tag-{i}"])
    return i, rc, out.strip()

for n in (10, 50):
    with ThreadPoolExecutor(max_workers=n) as pool:
        results = list(pool.map(worker, range(n)))
    for i, rc, out in results:
        assert rc == 0, f"N={n} worker {i} rc={rc}"
        assert out == f"tag-{i}", f"N={n} cross-talk: worker {i} got {out!r}"

b.stop()
print("OK case 6")
PYEOF
)
teardown_fixture "$F6"
F6=""

# ---------------------------------------------------------------------------
# Case 7: mixed sync + async callers on same backend (load-bearing)
# ---------------------------------------------------------------------------
# This case proves the architecture solves the deadlock scenario: a sync
# caller invoked from inside a running asyncio loop on the *main* thread
# succeeds because the control client's reader runs on the bg loop, not on
# the calling thread's loop.
echo "== case 7: mixed sync + async =="
F7=$(make_fixture)

(
    cd "$REPO_ROOT"
    # shellcheck disable=SC2030,SC2031  # subshell-scoped export is intentional (case isolation)
    export TMUX_TMPDIR="$F7"
    unset TMUX
    SESSION="ait_test_$$_g"
    tmux new-session -d -s "$SESSION" "tail -f /dev/null"

    PYTHONPATH="$REPO_ROOT/.aitask-scripts" \
    AIT_TEST_TMUX_DIR="$F7" \
    AIT_TEST_SESSION="$SESSION" \
    "$PYTHON_BIN" - <<'PYEOF'
import asyncio
import os

from monitor.tmux_control import TmuxControlBackend

session = os.environ["AIT_TEST_SESSION"]


async def main():
    b = TmuxControlBackend(session=session)
    assert b.start()

    # Sync call from inside the main asyncio loop. This would deadlock if
    # the control client's reader were running on this same loop. It
    # succeeds because the reader runs on the bg loop.
    rc, out = b.request_sync(["display-message", "-p", "from-sync"])
    assert rc == 0 and out.strip() == "from-sync"

    # Async call on the main loop, served by the bg loop via run_coroutine_threadsafe.
    rc, out = await b.request_async(["display-message", "-p", "from-async"])
    assert rc == 0 and out.strip() == "from-async"

    # Many parallel async + sync (sync via run_in_executor so multiple
    # blocking calls can be in flight from this loop).
    loop = asyncio.get_running_loop()
    async_tasks = [
        b.request_async(["display-message", "-p", f"a{i}"]) for i in range(5)
    ]
    sync_tasks = [
        loop.run_in_executor(
            None, b.request_sync, ["display-message", "-p", f"s{i}"]
        )
        for i in range(5)
    ]
    results = await asyncio.gather(*async_tasks, *sync_tasks)
    for i, (rc, out) in enumerate(results[:5]):
        assert rc == 0 and out.strip() == f"a{i}", (i, rc, out)
    for i, (rc, out) in enumerate(results[5:]):
        assert rc == 0 and out.strip() == f"s{i}", (i, rc, out)

    b.stop()


asyncio.run(main())
print("OK case 7")
PYEOF
)
teardown_fixture "$F7"
F7=""

# ---------------------------------------------------------------------------
# Case 8: lifecycle — idempotent start, restart after stop
# ---------------------------------------------------------------------------
echo "== case 8: lifecycle =="
F8=$(make_fixture)

(
    cd "$REPO_ROOT"
    # shellcheck disable=SC2030,SC2031  # subshell-scoped export is intentional (case isolation)
    export TMUX_TMPDIR="$F8"
    unset TMUX
    SESSION="ait_test_$$_h"
    tmux new-session -d -s "$SESSION" "tail -f /dev/null"

    PYTHONPATH="$REPO_ROOT/.aitask-scripts" \
    AIT_TEST_TMUX_DIR="$F8" \
    AIT_TEST_SESSION="$SESSION" \
    "$PYTHON_BIN" - <<'PYEOF'
import os

from monitor.tmux_control import TmuxControlBackend

session = os.environ["AIT_TEST_SESSION"]
b = TmuxControlBackend(session=session)

# Idempotent start: second start() while alive returns True without
# spawning a second thread.
assert b.start()
t1 = b._thread
assert b.start()
t2 = b._thread
assert t1 is t2, "second start() spawned a new thread"

# Restart after stop() must succeed.
b.stop()
assert not b.is_alive
assert b.start(), "could not restart after stop()"
assert b.is_alive

# One real call to confirm the restarted client works
rc, out = b.request_sync(["display-message", "-p", "restarted"])
assert rc == 0 and out.strip() == "restarted", (rc, out)

b.stop()
b.stop()  # idempotent
print("OK case 8")
PYEOF
)
teardown_fixture "$F8"
F8=""

# ---------------------------------------------------------------------------
# Case 9: transport-failure recovery (server killed)
# ---------------------------------------------------------------------------
echo "== case 9: transport failure =="
F9=$(make_fixture)

(
    cd "$REPO_ROOT"
    # shellcheck disable=SC2030,SC2031  # subshell-scoped export is intentional (case isolation)
    export TMUX_TMPDIR="$F9"
    unset TMUX
    SESSION="ait_test_$$_i"
    tmux new-session -d -s "$SESSION" "tail -f /dev/null"

    PYTHONPATH="$REPO_ROOT/.aitask-scripts" \
    AIT_TEST_TMUX_DIR="$F9" \
    AIT_TEST_SESSION="$SESSION" \
    "$PYTHON_BIN" - <<'PYEOF'
import os
import subprocess
import time

from monitor.tmux_control import TmuxControlBackend

session = os.environ["AIT_TEST_SESSION"]
tmux_dir = os.environ["AIT_TEST_TMUX_DIR"]
env = {**os.environ, "TMUX_TMPDIR": tmux_dir}
env.pop("TMUX", None)

b = TmuxControlBackend(session=session, command_timeout=2.0)
assert b.start()

# Sanity: first call works
rc, out = b.request_sync(["display-message", "-p", "alive"])
assert rc == 0 and out.strip() == "alive"

# Kill the tmux server out from under the backend.
subprocess.run(["tmux", "kill-server"], env=env, check=False)

# Reader detects EOF and marks dead. Poll up to 2.5s.
deadline = time.monotonic() + 2.5
while time.monotonic() < deadline and b.is_alive:
    time.sleep(0.05)
assert not b.is_alive, "backend should detect server death"

# Subsequent requests return (-1, "") cleanly, no raise.
rc, out = b.request_sync(["display-message", "-p", "after-kill"])
assert rc == -1 and out == "", (rc, out)

# stop() still clean after server death
b.stop()
print("OK case 9")
PYEOF
)
teardown_fixture "$F9"
F9=""

# ---------------------------------------------------------------------------
# Case 11: tmux not on PATH
# ---------------------------------------------------------------------------
echo "== case 11: tmux missing on PATH =="

(
    cd "$REPO_ROOT"
    # Resolve to the *real* python interpreter (not a #!/usr/bin/env bash
    # wrapper). When PATH is restricted, the wrapper's shebang would fail
    # before Python even starts.
    PYTHON_ABS="$("$PYTHON_BIN" -c 'import sys; print(sys.executable)')"
    NO_TMUX_DIR=$(mktemp -d "${TMPDIR:-/tmp}/ait_no_tmux_XXXXXX")
    PYTHONPATH="$REPO_ROOT/.aitask-scripts" \
    PATH="$NO_TMUX_DIR" \
    "$PYTHON_ABS" - <<'PYEOF'
from monitor.tmux_control import TmuxControlBackend

b = TmuxControlBackend(session="anything")
ok = b.start()
assert not ok, "backend.start() should fail when tmux is missing"
assert not b.is_alive
# request_sync after failed start: returns (-1, "") cleanly
rc, out = b.request_sync(["display-message", "-p", "x"])
assert rc == -1 and out == "", (rc, out)
# stop() is idempotent even after failed start
b.stop()
print("OK case 11")
PYEOF
    rm -rf "$NO_TMUX_DIR"
)

# ---------------------------------------------------------------------------
# Case 12: shutdown with recently-issued work
# ---------------------------------------------------------------------------
echo "== case 12: shutdown with pending work =="
F12=$(make_fixture)

(
    cd "$REPO_ROOT"
    # shellcheck disable=SC2030,SC2031  # subshell-scoped export is intentional (case isolation)
    export TMUX_TMPDIR="$F12"
    unset TMUX
    SESSION="ait_test_$$_l"
    tmux new-session -d -s "$SESSION" "tail -f /dev/null"

    PYTHONPATH="$REPO_ROOT/.aitask-scripts" \
    AIT_TEST_TMUX_DIR="$F12" \
    AIT_TEST_SESSION="$SESSION" \
    "$PYTHON_BIN" - <<'PYEOF'
import asyncio
import os
import time

from monitor.tmux_control import TmuxControlBackend

session = os.environ["AIT_TEST_SESSION"]
b = TmuxControlBackend(session=session)
assert b.start()

# Schedule 20 coroutine futures directly on the bg loop, then immediately
# call stop(). All futures must resolve (with a real result or (-1, ""));
# none stay pending forever.
loop = b._loop
client = b._client
assert loop is not None and client is not None
coro_futures = [
    asyncio.run_coroutine_threadsafe(
        client.request(["display-message", "-p", f"q{i}"]), loop,
    )
    for i in range(20)
]

t0 = time.monotonic()
b.stop()
elapsed = time.monotonic() - t0
assert elapsed < 4.0, f"stop() took {elapsed:.2f}s"

# All scheduled futures must resolve within a brief window.
deadline = time.monotonic() + 2.0
unresolved = [cf for cf in coro_futures if not cf.done()]
while unresolved and time.monotonic() < deadline:
    time.sleep(0.05)
    unresolved = [cf for cf in coro_futures if not cf.done()]
assert not unresolved, f"{len(unresolved)} futures unresolved after stop()"

# Each result is either a real (rc,out) or the dead-client sentinel.
for cf in coro_futures:
    try:
        rc, out = cf.result(timeout=0.1)
    except Exception:
        continue  # cancelled / loop teardown — acceptable
    assert rc in (0, 1, -1), f"unexpected rc={rc}"

print("OK case 12")
PYEOF
)
teardown_fixture "$F12"
F12=""

trap - EXIT

echo "PASS: tests/test_tmux_control.sh"
