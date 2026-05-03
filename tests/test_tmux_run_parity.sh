#!/usr/bin/env bash
# Parity test for `monitor.tmux_monitor.TmuxMonitor.tmux_run`.
#
# For each tmux subcommand the t722 migration touches, runs both
# `monitor.tmux_run([...])` (with the TmuxControlBackend started, exercising
# the request_sync path) and raw `subprocess.run(["tmux", ...])` directly,
# then asserts identical (returncode, stdout). Re-runs the same battery
# with the backend NOT started, exercising the subprocess fallback inside
# tmux_run. Both passes must produce identical results — that is what
# proves the migration is behavior-preserving.
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

FIXTURE_DIR=$(mktemp -d "${TMPDIR:-/tmp}/ait_tmux_parity_XXXXXX")
trap 'TMUX_TMPDIR="$FIXTURE_DIR" tmux kill-server 2>/dev/null || true; rm -rf "$FIXTURE_DIR"' EXIT

(
    cd "$REPO_ROOT"
    export TMUX_TMPDIR="$FIXTURE_DIR"
    unset TMUX
    SESSION="ait_parity_$$"
    tmux new-session -d -s "$SESSION" -n "primary" "tail -f /dev/null"
    tmux new-window -t "${SESSION}:" -n "secondary" "tail -f /dev/null"
    tmux new-window -t "${SESSION}:" -n "tertiary" "tail -f /dev/null"

    PYTHONPATH="$REPO_ROOT/.aitask-scripts" \
    AIT_TEST_TMUX_DIR="$FIXTURE_DIR" \
    AIT_TEST_SESSION="$SESSION" \
    "$PYTHON_BIN" - <<'PYEOF'
import os
import subprocess
import sys
import time

from monitor.tmux_monitor import TmuxMonitor

session = os.environ["AIT_TEST_SESSION"]
tmux_dir = os.environ["AIT_TEST_TMUX_DIR"]
env = {**os.environ, "TMUX_TMPDIR": tmux_dir}
env.pop("TMUX", None)


def sub(args):
    """Raw subprocess invocation (the canonical reference)."""
    r = subprocess.run(
        ["tmux", *args], capture_output=True, text=True, env=env, timeout=10,
    )
    return r.returncode, r.stdout or ""


def assert_parity(label, monitor, args):
    """tmux_run vs subprocess parity contract:
      * rc must match exactly.
      * stdout must match exactly only when rc == 0. On failure paths,
        tmux's control mode emits the error body in the %error reply
        (which the client returns as stdout), whereas subprocess writes
        errors to stderr. Every migrated caller inspects stdout only
        when rc == 0, so the difference is harmless and out of contract.
    """
    rc1, out1 = monitor.tmux_run(args)
    rc2, out2 = sub(args)
    if rc1 != rc2:
        sys.exit(
            f"{label}: rc mismatch\n"
            f"  args={args}\n"
            f"  tmux_run    = ({rc1}, {out1!r})\n"
            f"  subprocess  = ({rc2}, {out2!r})\n"
        )
    if rc1 == 0 and out1 != out2:
        sys.exit(
            f"{label}: success-stdout mismatch\n"
            f"  args={args}\n"
            f"  tmux_run    = ({rc1}, {out1!r})\n"
            f"  subprocess  = ({rc2}, {out2!r})\n"
        )
    return rc1, out1


def list_panes_ids(target):
    rc, out = sub(["list-panes", "-s", "-t", target, "-F", "#{pane_id}"])
    if rc != 0:
        return []
    return [line for line in out.strip().splitlines() if line.startswith("%")]


def list_window_ids(target):
    rc, out = sub(["list-windows", "-t", target, "-F", "#{window_id}"])
    if rc != 0:
        return []
    return [line for line in out.strip().splitlines() if line.startswith("@")]


def run_battery(label_prefix, monitor):
    """All read-mostly subcommands — these are state-stable and can be
    asserted exact."""
    pane_ids = list_panes_ids(session)
    assert pane_ids, "fixture has no panes"
    pane = pane_ids[0]
    win_ids = list_window_ids(session)
    assert win_ids, "fixture has no windows"
    win = win_ids[0]

    # display-message #S
    assert_parity(
        f"{label_prefix} display-message #S",
        monitor, ["display-message", "-p", "#S"],
    )

    # display-message tab-bearing per-pane format
    fmt = "#{window_id}\t#{window_index}\t#{window_name}"
    assert_parity(
        f"{label_prefix} display-message per-pane fmt",
        monitor, ["display-message", "-p", "-t", pane, fmt],
    )

    # list-panes -s -F
    pane_fmt = "\t".join([
        "#{window_index}", "#{window_name}", "#{pane_index}",
        "#{pane_id}", "#{pane_pid}", "#{pane_current_command}",
        "#{pane_width}", "#{pane_height}",
    ])
    assert_parity(
        f"{label_prefix} list-panes -s",
        monitor, ["list-panes", "-s", "-t", session, "-F", pane_fmt],
    )

    # list-panes -t window
    assert_parity(
        f"{label_prefix} list-panes -t window",
        monitor, ["list-panes", "-t", win, "-F",
                  "#{pane_id}\t#{pane_pid}"],
    )

    # list-windows -F
    assert_parity(
        f"{label_prefix} list-windows",
        monitor, ["list-windows", "-t", session, "-F", "#{window_name}"],
    )

    # has-session: ok and missing
    assert_parity(
        f"{label_prefix} has-session ok",
        monitor, ["has-session", "-t", session],
    )
    assert_parity(
        f"{label_prefix} has-session missing",
        monitor, ["has-session", "-t", "no_such_session_xyz"],
    )

    # show-environment: set then read
    set_var = f"AIT_PARITY_{label_prefix.upper().replace(' ', '_')}"
    sub(["set-environment", "-t", session, set_var, "hello-world"])
    assert_parity(
        f"{label_prefix} show-environment after set",
        monitor, ["show-environment", "-t", session, set_var],
    )
    # set-environment unset (mutator; rc only)
    assert_parity(
        f"{label_prefix} set-environment -u",
        monitor, ["set-environment", "-t", session, "-u", set_var],
    )

    # capture-pane (-p, with scrollback). Output content is volatile (the
    # tail-f panes are mostly empty) but body should match exactly within a
    # single invocation window.
    assert_parity(
        f"{label_prefix} capture-pane",
        monitor, ["capture-pane", "-p", "-J", "-S", "-100", "-t", pane],
    )


# Pass A: backend started — exercises request_sync path
print("== pass A: backend started ==")
m_a = TmuxMonitor(session=session)
import asyncio
ok = asyncio.run(m_a.start_control_client())
assert ok, "control client failed to start"
assert m_a.has_control_client()
run_battery("ctrl", m_a)
asyncio.run(m_a.close_control_client())

# Pass B: no backend — exercises subprocess fallback inside tmux_run
print("== pass B: no backend (subprocess fallback) ==")
m_b = TmuxMonitor(session=session)
assert not m_b.has_control_client()
run_battery("sub", m_b)

# Mutator subcommands — exercised in a fresh window so the read-only
# battery isn't sensitive to ordering.
print("== mutator parity ==")
m_c = TmuxMonitor(session=session)
asyncio.run(m_c.start_control_client())

# rename-window (in a brand-new ephemeral window)
sub(["new-window", "-t", session, "-n", "rename_target"])
rc, _ = m_c.tmux_run(["rename-window", "-t",
                      f"{session}:rename_target", "renamed_via_run"])
assert rc == 0
rc2, out2 = sub(["list-windows", "-t", session, "-F", "#{window_name}"])
assert "renamed_via_run" in out2.splitlines(), out2
sub(["kill-window", "-t", f"{session}:renamed_via_run"])

# new-window via tmux_run, then verify via list-windows.
rc, _ = m_c.tmux_run([
    "new-window", "-t", f"{session}:", "-n", "spawned_window",
    "tail -f /dev/null",
])
assert rc == 0
rc2, out2 = sub(["list-windows", "-t", session, "-F", "#{window_name}"])
assert "spawned_window" in out2.splitlines()

# select-window then verify active marker
rc, _ = m_c.tmux_run(["select-window", "-t", f"{session}:spawned_window"])
assert rc == 0
rc2, out2 = sub(["display-message", "-p", "-t", session, "#W"])
assert out2.strip() == "spawned_window", out2

# kill-window via tmux_run
rc, _ = m_c.tmux_run(["kill-window", "-t", f"{session}:spawned_window"])
assert rc == 0
rc2, out2 = sub(["list-windows", "-t", session, "-F", "#{window_name}"])
assert "spawned_window" not in out2.splitlines()

# send-keys + capture-pane sentinel
sub(["new-window", "-t", session, "-n", "keys_target", "cat"])
time.sleep(0.1)
target_pane_rc, target_pane_out = sub([
    "list-panes", "-t", f"{session}:keys_target", "-F", "#{pane_id}",
])
target_pane = target_pane_out.strip().splitlines()[0]
sentinel = "TMUX_PARITY_SENTINEL_42"
rc, _ = m_c.tmux_run(["send-keys", "-t", target_pane, "-l", sentinel])
assert rc == 0
rc, _ = m_c.tmux_run(["send-keys", "-t", target_pane, "Enter"])
assert rc == 0
time.sleep(0.2)
rc, body = m_c.tmux_run(["capture-pane", "-p", "-t", target_pane])
assert rc == 0
assert sentinel in body, f"sentinel not echoed: {body!r}"
sub(["kill-window", "-t", f"{session}:keys_target"])

# select-pane via tmux_run + verify active
sub(["new-window", "-t", session, "-n", "split_target", "tail -f /dev/null"])
sub(["split-window", "-t", f"{session}:split_target", "-v",
     "tail -f /dev/null"])
panes_rc, panes_out = sub([
    "list-panes", "-t", f"{session}:split_target", "-F", "#{pane_id}",
])
pane_ids = panes_out.strip().splitlines()
assert len(pane_ids) >= 2
rc, _ = m_c.tmux_run(["select-pane", "-t", pane_ids[1]])
assert rc == 0
rc, active = sub([
    "list-panes", "-t", f"{session}:split_target",
    "-F", "#{pane_id}\t#{pane_active}",
])
assert f"{pane_ids[1]}\t1" in active
sub(["kill-window", "-t", f"{session}:split_target"])

# kill-pane via tmux_run
sub(["new-window", "-t", session, "-n", "kp_target", "tail -f /dev/null"])
sub(["split-window", "-t", f"{session}:kp_target", "tail -f /dev/null"])
panes_rc, panes_out = sub([
    "list-panes", "-t", f"{session}:kp_target", "-F", "#{pane_id}",
])
pane_ids = panes_out.strip().splitlines()
to_kill = pane_ids[1]
rc, _ = m_c.tmux_run(["kill-pane", "-t", to_kill])
assert rc == 0
remaining_rc, remaining_out = sub([
    "list-panes", "-t", f"{session}:kp_target", "-F", "#{pane_id}",
])
assert to_kill not in remaining_out.strip().splitlines()
sub(["kill-window", "-t", f"{session}:kp_target"])

asyncio.run(m_c.close_control_client())

print("OK parity")
PYEOF
)

echo "PASS: tests/test_tmux_run_parity.sh"
