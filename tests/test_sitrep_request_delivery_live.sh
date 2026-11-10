#!/usr/bin/env bash
# Real-server test for the sitrep TUI's guarded request delivery (t2211_4).
#
# `deliver_sitrep_request` types a request into the sitrep agent and submits it
# in three observed phases (readiness, guarded paste with a nonce ack, a
# composer-proved and mode-gated Enter). Here a REAL tmux server evaluates
# every guard, against a scripted Claude-shaped agent pane
# (tests/lib/fake_composer_agent.py, launched as `claude` so the pane resolves
# to that agent) that logs every byte it receives. The delivery's pause seam
# interleaves respawns, freezes, copy-mode and user typing between phases.
#
# Cases (the task's (a)-(i), plus the plan-review regressions (j)-(l)):
#   (a) ready                      -> submitted; exactly the text + one Enter
#   (b) a dialog                   -> refused:not_ready:dialog; nothing received
#   (c) a user draft               -> refused:not_ready:draft; the draft intact
#   (d) respawn-pane -k after readiness -> skipped; pane alive, no buffer left
#   (e) frozen before the request  -> refused:no_agent (the lookup skips it);
#       frozen after readiness ->
#       skipped; nothing received
#   (f) `;`, quotes, #{...}, $(...), \; and a trailing `;` arrive literally,
#       and no tmux command they spell runs
#   (g) the composer never empties -> typed_not_submitted (bounded Enters)
#   (h) copy-mode after the paste  -> typed_not_submitted:in_mode; no Enter,
#       still in copy-mode, the composer holds the request, sentinel buffer kept
#   (i) copy-mode between an unconfirmed Enter and its retry -> no retry Enter
#   (j) user text appended after the paste -> typed_not_submitted; no Enter
#   (k) the request submitted, then a foreign draft -> unknown; ONE Enter only
#   (l) a request wider than the composer (word + mid-token wrap) -> submitted
#
# Then a mutant per guard, each turning ITS case red (and one control that must
# stay green): no identity term (d); readiness forced (b)/(c); an ack-less
# read-back classified sent (d); the text inlined into the if-shell (f); no
# Python pre-Enter mode read AND no conjunct (h)/(i); only the conjunct removed
# (h stays green via the Python gate); the composer proof replaced by the
# rejected occurrence count (j)/(k).
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

# /tmp, not $TMPDIR: the socket path must fit AF_UNIX's sun_path (t2142).
FIXTURE_DIR=$(mktemp -d /tmp/ait_reqdl_XXXXXX)
trap 'TMUX_TMPDIR="$FIXTURE_DIR" tmux kill-server 2>/dev/null || true; rm -rf "$FIXTURE_DIR"' EXIT

(
    cd "$REPO_ROOT" || exit 1
    export TMUX_TMPDIR="$FIXTURE_DIR"
    unset TMUX
    SESSION="ait_reqdl_$$"
    tmux new-session -d -s "$SESSION" -n "primary" -x 120 -y 40 "tail -f /dev/null"
    # vi copy-mode: Enter there is copy-pipe-and-cancel, the hazard (h)/(i) model.
    tmux set-window-option -g mode-keys vi

    PYTHONPATH="$REPO_ROOT/.aitask-scripts:$REPO_ROOT/.aitask-scripts/lib:$REPO_ROOT/tests" \
    AIT_TEST_TMUX_DIR="$FIXTURE_DIR" \
    AIT_TEST_SESSION="$SESSION" \
    AIT_TEST_PYTHON="$PYTHON_BIN" \
    AIT_TEST_FAKE="$REPO_ROOT/tests/lib/fake_composer_agent.py" \
    "$PYTHON_BIN" - <<'PYEOF'
import asyncio
import contextlib
import os
import re
import shlex
import subprocess
import sys
import time

from monitor import agent_request_delivery as d
from monitor import monitor_core as mc
from monitor import review_loop as rl
from monitor.ansi_utils import strip_ansi
from sitrep_tui.sitrep_tui_requests import TmuxGateway

session = os.environ["AIT_TEST_SESSION"]
fixture = os.environ["AIT_TEST_TMUX_DIR"]
py = os.environ["AIT_TEST_PYTHON"]
fake = os.environ["AIT_TEST_FAKE"]
env = {**os.environ, "TMUX_TMPDIR": fixture}
env.pop("TMUX", None)
root = os.path.realpath(os.path.join(fixture, "root"))
os.makedirs(root, exist_ok=True)
gw = TmuxGateway()                     # the TUI's own gateway, on this server
LOGS = os.path.join(fixture, "logs")
os.makedirs(LOGS, exist_ok=True)
SENTINEL = "ait-sentinel"
HOSTILE = ">q c1 a;b \"d\" 'e' #{pane_id} $(echo x) \\; ; set-buffer -b ait-injected x;"
LONG = (">q c12 " + " ".join(f"word{i:02d}" for i in range(24)) + " "
        + "z" * 140 + " tail")
FAILS = []


def sub(args):
    r = subprocess.run(["tmux", *args], capture_output=True, text=True, env=env, timeout=10)
    return r.returncode, r.stdout or ""


def fatal(msg):
    sys.exit(f"FAIL: {msg}")


def agent_cmd(mode, log):
    inner = f"exec -a claude {shlex.quote(py)} {shlex.quote(fake)} --mode {mode} --log {shlex.quote(log)}"
    return f"bash -c {shlex.quote(inner)}"


def capture(pane):
    rc, out = sub(["capture-pane", "-p", "-e", "-t", pane, "-S", "-15"])
    return out if rc == 0 else None


def wait_state(pane, want, timeout=10.0):
    end = time.time() + timeout
    state = None
    while time.time() < end:
        state = rl.shadow_state(capture(pane), "claude")
        if state == want:
            return
        time.sleep(0.1)
    fatal(f"fixture: pane {pane} never reached {want} (last {state})")


_n = [0]


def start(mode):
    """A fresh stamped agent window; returns (pane, log path)."""
    _n[0] += 1
    log = os.path.join(LOGS, f"a{_n[0]}.log")
    open(log, "wb").close()
    rc, out = sub(["new-window", "-d", "-t", session, "-n", "agent-sitrep", "-c", root,
                   "-P", "-F", "#{pane_id}", agent_cmd(mode, log)])
    pane = out.strip()
    if rc != 0 or not pane:
        fatal(f"fixture: could not start the fake agent ({rc} {out!r})")
    sub(["set-option", "-p", "-t", pane, mc.SITREP_ROOT_OPTION, root])
    wait_state(pane, {"ready": rl.SHADOW_READY, "stuck": rl.SHADOW_READY,
                      "resubmit_draft": rl.SHADOW_READY, "dialog": rl.SHADOW_DIALOG,
                      "draft": rl.SHADOW_BUSY}[mode])
    rc, cmd = sub(["display-message", "-p", "-t", pane, "#{pane_current_command}"])
    if cmd.strip() != "claude":
        fatal(f"fixture: the fake agent pane reads {cmd.strip()!r}, not 'claude'")
    return pane, log


def stop(pane):
    sub(["kill-pane", "-t", pane])
    time.sleep(0.1)


def received(log):
    with open(log, "rb") as f:
        return f.read().decode("utf-8", "replace")


def our_buffers():
    rc, out = sub(["list-buffers", "-F", "#{buffer_name}"])
    return [b for b in out.split() if b.startswith(mc.DISPATCH_BUFFER_PREFIX)]


def in_mode(pane):
    rc, out = sub(["display-message", "-p", "-t", pane, "#{pane_in_mode}"])
    return out.strip() not in ("", "0")


def deliver(text, pause=None):
    return asyncio.run(d.deliver_sitrep_request(gw, root, text, pause=pause))


def at(phase, action):
    async def pause(p):
        if p == phase:
            action()
            await asyncio.sleep(0.3)
    return pause


def check(errors, cond, msg):
    if not cond:
        errors.append(msg)


# -- the cases: each returns its list of failed assertions ---------------------------

def case_a():
    pane, log = start("ready")
    res, e = deliver(">t c12"), []
    check(e, res.code == d.SUBMITTED, f"result {res.code}/{res.detail}")
    check(e, received(log) == ">t c12\r", f"received {received(log)!r}")
    stop(pane)
    return e


def case_b():
    pane, log = start("dialog")
    res, e = deliver(">t c12"), []
    check(e, res.code == "refused:" + d.NOT_READY_DIALOG, f"result {res.code}")
    check(e, received(log) == "", f"the dialog received {received(log)!r}")
    stop(pane)
    return e


def case_c():
    pane, log = start("draft")
    res, e = deliver(">t c12"), []
    check(e, res.code == "refused:" + d.NOT_READY_DRAFT, f"result {res.code}")
    check(e, received(log) == "", f"the draft received {received(log)!r}")
    check(e, "half-typed user draft" in strip_ansi(capture(pane) or ""), "the draft changed")
    stop(pane)
    return e


def case_d():
    pane, log = start("ready")
    log2 = os.path.join(LOGS, "respawned.log")
    open(log2, "wb").close()

    def respawn():
        sub(["respawn-pane", "-k", "-t", pane, agent_cmd("ready", log2)])
        wait_state(pane, rl.SHADOW_READY)

    res, e = deliver(">t c12", pause=at("after_readiness", respawn)), []
    check(e, res.code == d.SKIPPED, f"result {res.code}/{res.detail}")
    check(e, received(log2) == "", f"the respawned run received {received(log2)!r}")
    check(e, sub(["display-message", "-p", "-t", pane, "#{pane_id}"])[1].strip() == pane,
          "the pane died")
    check(e, our_buffers() == [], f"leaked buffers {our_buffers()}")
    stop(pane)
    return e


def case_e():
    e = []
    pane, log = start("ready")
    sub(["set-option", "-p", "-t", pane, mc.FROZEN_OPTION, "rec1"])
    res = deliver(">t c12")
    # The roles lookup never offers a frozen pane, so a pane frozen BEFORE the
    # request is simply no agent; `refused:frozen` is the identity read's answer
    # to a freeze between the lookup and that read (pinned in the pure suite).
    check(e, res.code == "refused:" + d.R_NO_AGENT, f"frozen before: {res.code}")
    sub(["set-option", "-pu", "-t", pane, mc.FROZEN_OPTION])
    res = deliver(">t c12", pause=at("after_readiness", lambda: sub(
        ["set-option", "-p", "-t", pane, mc.FROZEN_OPTION, "rec2"])))
    check(e, res.code == d.SKIPPED and res.detail == mc.SKIP_IDENTITY_CHANGED,
          f"frozen after readiness: {res.code}/{res.detail}")
    check(e, received(log) == "", f"a frozen pane received {received(log)!r}")
    check(e, our_buffers() == [], f"leaked buffers {our_buffers()}")
    stop(pane)
    return e


def case_f():
    pane, log = start("ready")
    sub(["delete-buffer", "-b", "ait-injected"])
    res, e = deliver(HOSTILE), []
    check(e, res.code == d.SUBMITTED, f"result {res.code}/{res.detail}")
    check(e, received(log) == HOSTILE + "\r", f"received {received(log)!r}")
    rc, names = sub(["list-buffers", "-F", "#{buffer_name}"])
    check(e, "ait-injected" not in names.split(), "a tmux command in the text ran")
    check(e, our_buffers() == [], f"leaked buffers {our_buffers()}")
    stop(pane)
    return e


def case_g():
    pane, log = start("stuck")
    res, e = deliver(">t c12"), []
    check(e, (res.code, res.detail) == (d.TYPED, "submit_unconfirmed"),
          f"result {res.code}/{res.detail}")
    check(e, received(log) == ">t c12" + "\r" * (1 + rl.SHADOW_SUBMIT_RETRIES),
          f"received {received(log)!r}")
    stop(pane)
    return e


def _sentinel():
    sub(["set-buffer", "-b", SENTINEL, "SENTINEL"])


def _sentinel_kept(e):
    rc, names = sub(["list-buffers", "-F", "#{buffer_name}"])
    check(e, names.split() == [SENTINEL], f"buffers now {names.split()}")
    check(e, sub(["show-buffer", "-b", SENTINEL])[1] == "SENTINEL", "the sentinel changed")


def case_h():
    pane, log = start("ready")
    _sentinel()
    res = deliver(">t c12", pause=at("after_paste", lambda: sub(["copy-mode", "-t", pane])))
    e = []
    check(e, res.code == d.TYPED_IN_MODE, f"result {res.code}/{res.detail}")
    check(e, received(log) == ">t c12", f"received {received(log)!r}")
    check(e, in_mode(pane), "the pane left copy-mode (an Enter reached the mode)")
    check(e, "❯ >t c12" in strip_ansi(capture(pane) or ""),
          "the composer no longer holds the request")
    _sentinel_kept(e)
    stop(pane)
    return e


def case_i():
    pane, log = start("stuck")
    _sentinel()
    res = deliver(">t c12", pause=at("before_retry", lambda: sub(["copy-mode", "-t", pane])))
    e = []
    check(e, res.code == d.TYPED_IN_MODE, f"result {res.code}/{res.detail}")
    check(e, received(log) == ">t c12\r", f"received {received(log)!r} (a retry Enter?)")
    check(e, in_mode(pane), "the pane left copy-mode")
    _sentinel_kept(e)
    stop(pane)
    return e


def case_j():
    pane, log = start("ready")
    res = deliver(">t c12", pause=at("after_paste", lambda: sub(
        ["send-keys", "-t", pane, "-l", " plus my words"])))
    e = []
    check(e, (res.code, res.detail) == (d.TYPED, "composer_changed"),
          f"result {res.code}/{res.detail}")
    check(e, received(log) == ">t c12 plus my words", f"received {received(log)!r}")
    stop(pane)
    return e


def case_k():
    pane, log = start("resubmit_draft")
    res, e = deliver(">t c12"), []
    check(e, (res.code, res.detail) == (d.UNKNOWN, "composer_changed_after_enter"),
          f"result {res.code}/{res.detail}")
    check(e, received(log).count("\r") == 1, f"received {received(log)!r}")
    stop(pane)
    return e


def case_l():
    pane, log = start("ready")
    res, e = deliver(LONG), []
    check(e, res.code == d.SUBMITTED, f"result {res.code}/{res.detail}")
    check(e, received(log) == LONG + "\r", f"received {received(log)!r}")
    stop(pane)
    return e


CASES = {"a": case_a, "b": case_b, "c": case_c, "d": case_d, "e": case_e, "f": case_f,
         "g": case_g, "h": case_h, "i": case_i, "j": case_j, "k": case_k, "l": case_l}
for name, fn in CASES.items():
    errors = fn()
    if errors:
        FAILS.append(f"({name}): " + "; ".join(errors))
    else:
        print(f"OK ({name})")


# -- mutants: each must turn its own case red -------------------------------------------

@contextlib.contextmanager
def patched(obj, name, value):
    saved = getattr(obj, name)
    setattr(obj, name, value)
    try:
        yield
    finally:
        setattr(obj, name, saved)


def identity_only(identity):
    return mc.run_identity_condition(identity.pane_pid, identity.server_pid, mc.FROZEN_OPTION)


def no_identity(identity):
    return mc.PANE_NOT_IN_MODE


def ackless(rc, out, pane_id, server_pid, nonce):
    return mc.DISPATCH_SENT if rc == 0 else mc.DISPATCH_UNKNOWN


def inline_text(monitor, identity, text, nonce):
    pane = identity.pane_id
    ack = f"set-option -p -t {pane} {mc.DISPATCH_ACK_OPTION} {nonce}:"
    monitor.tmux_run(["if-shell", "-F", "-t", pane, mc.dispatch_condition(identity),
                      f"send-keys -l -t {pane} {text} ; {ack}sent", f"{ack}skipped"])
    rc, out = monitor.tmux_run(["display-message", "-p", "-t", pane, mc.DISPATCH_ACK_FORMAT])
    return mc.dispatch_ack_state(rc, out, pane, identity.server_pid, nonce), ""


async def never_in_mode(monitor, pane_id):
    return False, ""


_last_tail = {}
_real_payload = rl.composer_payload


def stash_payload(raw, agent, width=None):
    _last_tail["raw"] = raw
    return _real_payload(raw, agent, width)


def occurrence_count(payload, expected):
    squash = lambda s: re.sub(r"[\s│┃]+", "", strip_ansi(s or ""))  # noqa: E731
    return payload is not None and squash(_last_tail.get("raw")).count(squash(expected)) > 0


MUTANTS = [
    ("no identity term", [(mc, "dispatch_condition", no_identity)], ["d"], True),
    ("readiness forced ready", [(d, "readiness_verdict", lambda *a: d.READY)], ["b", "c"], True),
    ("ack-less read-back is sent", [(mc, "dispatch_ack_state", ackless)], ["d"], True),
    ("text inlined into the if-shell", [(mc, "guarded_paste_text", inline_text)], ["f"], True),
    ("no pre-Enter mode read and no conjunct",
     [(mc, "query_pane_mode", never_in_mode), (mc, "dispatch_condition", identity_only)],
     ["h", "i"], True),
    ("only the conjunct removed", [(mc, "dispatch_condition", identity_only)], ["h"], False),
    ("occurrence count instead of the composer proof",
     [(rl, "composer_payload", stash_payload), (d, "payload_matches", occurrence_count)],
     ["j", "k"], True),
]
for label, patches, cases, want_red in MUTANTS:
    with contextlib.ExitStack() as stack:
        for obj, name, value in patches:
            stack.enter_context(patched(obj, name, value))
        for case in cases:
            errors = CASES[case]()
            red = bool(errors)
            if red != want_red:
                FAILS.append(f"mutant '{label}': ({case}) stayed "
                             f"{'green' if not red else 'red: ' + '; '.join(errors)}")
            else:
                why = f" -- {'; '.join(errors)}" if red else ""
                print(f"OK mutant '{label}': ({case}) {'red' if red else 'green'}{why}")
    sub(["delete-buffer", "-b", "ait-injected"])
    for b in our_buffers():
        sub(["delete-buffer", "-b", b])

if FAILS:
    for f in FAILS:
        print(f"FAIL: {f}")
    sys.exit(1)
print("OK sitrep request delivery (live)")
PYEOF
)

echo "PASS: tests/test_sitrep_request_delivery_live.sh"
