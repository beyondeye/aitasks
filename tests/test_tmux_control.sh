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
trap - EXIT

echo "PASS: tests/test_tmux_control.sh"
