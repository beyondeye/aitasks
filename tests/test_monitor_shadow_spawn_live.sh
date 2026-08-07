#!/usr/bin/env bash
# test_monitor_shadow_spawn_live.sh — LIVE isolated-tmux smoke for the monitor's
# shadow spawn (t1353; the automated counterpart to t1216_5's human walkthrough).
#
# `tests/test_monitor_shadow_pick.py` pins the same contracts through MOCKS: it
# patches `launch_in_tmux`, `resolve_pane_id_by_pid` and
# `attach_companion_cleanup_hook` on `monitor_core` and never issues a tmux call.
# That can prove the ARGUMENTS the monitor passes; it cannot prove the EFFECT.
# This test drives `MonitorApp.action_launch_shadow()` against a real throwaway
# tmux server and asserts what only live tmux can answer:
#
#   1. The `pane-died` hook's companion argument is the newly created SHADOW
#      pane, never the monitor's own pane — asserted structurally AND
#      behaviourally, by letting the hook fire and watching what dies.
#      `aitask_companion_cleanup.sh` job 2 runs `kill-pane -t "$companion"` with
#      NO marker check, so a monitor pane passed here is killed on the agent's
#      exit, arbitrarily later.
#   2a. A pre-existing CLEANUP hook is not overwritten: it still names the
#      original companion and no second cleanup entry is appended.
#   2b. A pre-existing UNRELATED `pane-died[0]` hook survives, and the cleanup
#      hook is appended at `pane-died[1]`.
#   3. The session's active window does not change on EITHER placement branch —
#      i.e. `select_window=False` really reaches tmux as "no select-window"
#      (split) and "`new-window -d`" (separate window).
#
# Every positive assertion is paired with a control that proves it can fail:
# case F arms a WRONG companion and shows that pane really is killed (so case
# E's "the monitor pane survives" is not vacuous), and case G spawns with
# `select_window=True` (minimonitor's policy) and shows the active window really
# does move.
#
# Only ONE seam is replaced: `monitor_app.resolve_dry_run_command` returns a
# harmless `tail -f /dev/null` instead of a real code-agent command line.
# Everything below the action is real — `_resolve_shadow_target` ->
# `monitor_core.spawn_shadow` -> `agent_launch_utils.launch_in_tmux` -> tmux ->
# `resolve_pane_id_by_pid` -> the `@aitask_shadow_target` stamp ->
# `attach_companion_cleanup_hook`. Binding->action wiring (`e`/`E`) is already
# pinned by the mocked suite, so the live leg starts at the action.
#
# THIS TEST IS tmux-DESTRUCTIVE. It arms real `pane-died` hooks, and
# `aitask_companion_cleanup.sh` reaches tmux with raw, un-flagged calls by
# design — no environment override can sandbox it once it fires. It therefore
# calls `require_clean_ait_server` (REFUSES, exit 2) in addition to
# `require_isolated_tmux` (isolates). Override on a dedicated box with
# AIT_LIVE_TMUX_TEST_FORCE=1.
#
# Not part of `tests/run_all_python_tests.sh` (a bash test, deliberately opt-in).
#
# Run: bash tests/test_monitor_shadow_spawn_live.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if ! command -v tmux >/dev/null 2>&1; then
    echo "SKIP: tmux not available"
    exit 0
fi

# shellcheck source=lib/venv_python.sh
. "$SCRIPT_DIR/lib/venv_python.sh"
PYTHON_BIN="${PYTHON_BIN:-$AITASK_PYTHON}"

if ! "$PYTHON_BIN" -c "import textual, yaml" >/dev/null 2>&1; then
    echo "SKIP: $PYTHON_BIN lacks textual/yaml (run 'ait setup' to build the venv)"
    exit 0
fi

# shellcheck source=lib/tmux_isolation.sh
. "$SCRIPT_DIR/lib/tmux_isolation.sh"

# ORDER IS LOAD-BEARING. `require_clean_ait_server` must run FIRST: it reads
# $TMUX and resolves `-L ait` against the user's real socket dir, both of which
# `require_isolated_tmux` destroys (unset TMUX / repoint TMUX_TMPDIR). Swapping
# these two lines makes the guard probe an empty isolated dir and pass
# vacuously — see the negative controls in the header of tmux_isolation.sh.
require_clean_ait_server
require_isolated_tmux

FIXTURE_DIR=$(mktemp -d "${TMPDIR:-/tmp}/ait_shadowlive_XXXXXX")

cleanup() {
    if TMUX_TMPDIR="$FIXTURE_DIR" tmux list-sessions >/dev/null 2>&1; then
        # Defuse every armed pane BEFORE kill-server, so teardown cannot race a
        # `pane-died` job into running the cleanup script on a dying server.
        while read -r pane; do
            [ -n "$pane" ] || continue
            TMUX_TMPDIR="$FIXTURE_DIR" tmux set-hook -pu -t "$pane" pane-died 2>/dev/null || true
            TMUX_TMPDIR="$FIXTURE_DIR" tmux set-option -pu -t "$pane" remain-on-exit 2>/dev/null || true
        done < <(TMUX_TMPDIR="$FIXTURE_DIR" tmux list-panes -a -F '#{pane_id}' 2>/dev/null || true)
        TMUX_TMPDIR="$FIXTURE_DIR" tmux kill-server 2>/dev/null || true
    fi
    rm -rf "$FIXTURE_DIR"
}
trap cleanup EXIT

(
    cd "$REPO_ROOT"
    export TMUX_TMPDIR="$FIXTURE_DIR"
    unset TMUX
    SESSION="ait_shadowlive_$$"

    # -x/-y matter: the split branch launches with `-l 60`, which fails on an
    # 80-column default window.
    tmux new-session -d -x 200 -y 50 -s "$SESSION" -n home "tail -f /dev/null"

    LIB_DIR="$REPO_ROOT/.aitask-scripts/lib"
    MONITOR_DIR="$REPO_ROOT/.aitask-scripts/monitor"
    BOARD_DIR="$REPO_ROOT/.aitask-scripts/board"

    PYTHONPATH="$LIB_DIR:$MONITOR_DIR:$BOARD_DIR:$REPO_ROOT/.aitask-scripts" \
    AIT_TEST_TMUX_DIR="$FIXTURE_DIR" \
    AIT_TEST_SESSION="$SESSION" \
    "$PYTHON_BIN" - <<'PYEOF'
"""Live shadow-spawn assertions. Any failure calls fail() -> exit 1."""
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

SESSION = os.environ["AIT_TEST_SESSION"]
TMUX_DIR = os.environ["AIT_TEST_TMUX_DIR"]

import agent_launch_utils as alu
from monitor import monitor_app as ma
from monitor import monitor_core as mc
from monitor.monitor_app import MonitorApp
from monitor.tmux_monitor import (
    PaneCategory,
    PaneSnapshot,
    TmuxMonitor,
    TmuxPaneInfo,
)

CLEANUP = alu.CLEANUP_SCRIPT_NAME
SHADOW_CMD = "tail -f /dev/null"

_env = {**os.environ, "TMUX_TMPDIR": TMUX_DIR}
_env.pop("TMUX", None)


def fail(msg):
    sys.exit(f"FAIL: {msg}")


def sub(args, timeout=10):
    """Raw tmux against the fixture server (test fixture, not app code)."""
    r = subprocess.run(
        ["tmux", *args], capture_output=True, text=True, env=_env, timeout=timeout
    )
    return r.returncode, (r.stdout or "")


# -- Containment ---------------------------------------------------------------
# Asserted BEFORE any mutation, and asserted positively (a round-trip that lands
# on the fixture socket), not only statically. `require_isolated_tmux` pins
# AITASKS_TMUX_SOCKET="" => the gateway emits no `-L` flag and follows
# $TMUX_TMPDIR, which the bash driver pointed at the fixture dir.

if alu._TMUX.socket_args != []:
    fail(f"gateway not contained: socket_args={alu._TMUX.socket_args!r} (want [])")

rc, out = alu._TMUX.run(["display-message", "-p", "#{socket_path}"])
if rc != 0 or not out.strip().startswith(TMUX_DIR):
    fail(f"gateway does not reach the fixture server: rc={rc} socket_path={out.strip()!r}")
print(f"OK containment (socket_path={out.strip()})")


# -- Fixture helpers -----------------------------------------------------------


def new_agent_window(name):
    """A detached window running `tail`; returns (pane_id, pane_pid)."""
    rc, out = sub(["new-window", "-d", "-P", "-F", "#{pane_id} #{pane_pid}",
                   "-t", f"={SESSION}:", "-n", name, SHADOW_CMD])
    if rc != 0:
        fail(f"could not create window {name!r} (rc={rc})")
    pane_id, _, pid = out.strip().partition(" ")
    return pane_id, int(pid)


def split_into(target):
    """A second pane in `target`'s window; returns (pane_id, pane_pid)."""
    rc, out = sub(["split-window", "-d", "-P", "-F", "#{pane_id} #{pane_pid}",
                   "-t", target, SHADOW_CMD])
    if rc != 0:
        fail(f"could not split {target!r} (rc={rc})")
    pane_id, _, pid = out.strip().partition(" ")
    return pane_id, int(pid)


def active_window():
    rc, out = sub(["list-windows", "-t", f"={SESSION}",
                   "-F", "#{window_active} #{window_name}"])
    if rc != 0:
        fail(f"list-windows failed (rc={rc})")
    for line in out.splitlines():
        flag, _, name = line.strip().partition(" ")
        if flag == "1":
            return name
    return None


def select_home():
    sub(["select-window", "-t", f"={SESSION}:home"])
    if active_window() != "home":
        fail("could not park the active window on 'home'")


def all_panes():
    rc, out = sub(["list-panes", "-a", "-F", "#{pane_id}"])
    return set(out.split()) if rc == 0 else set()


def panes_in_window(name):
    rc, out = sub(["list-panes", "-t", f"={SESSION}:{name}", "-F", "#{pane_id}"])
    return set(out.split()) if rc == 0 else set()


def window_names():
    rc, out = sub(["list-windows", "-t", f"={SESSION}", "-F", "#{window_name}"])
    return set(out.split()) if rc == 0 else set()


def shadows_of(agent_pane):
    """Panes whose @aitask_shadow_target is agent_pane (the classifier stamp)."""
    rc, out = sub(["list-panes", "-a", "-F", "#{pane_id}\t#{@aitask_shadow_target}"])
    if rc != 0:
        fail(f"list-panes failed (rc={rc})")
    found = []
    for line in out.splitlines():
        pane, _, target = line.partition("\t")
        if target.strip() == agent_pane:
            found.append(pane.strip())
    return found


def pane_option(pane, option):
    rc, out = sub(["show-options", "-pqv", "-t", pane, option])
    return out.strip() if rc == 0 else ""


_PANE_DIED = re.compile(r"^pane-died(?:\[(\d+)\])?\s+(.*)$")


def pane_died_hooks(pane):
    """[(index, body)] for every pane-died hook on `pane`, index-ordered."""
    rc, out = sub(["show-hooks", "-p", "-t", pane])
    if rc != 0:
        fail(f"show-hooks failed for {pane} (rc={rc})")
    entries = []
    for line in out.splitlines():
        m = _PANE_DIED.match(line.strip())
        if m:
            entries.append((int(m.group(1) or 0), m.group(2)))
    return sorted(entries), out


def cleanup_hook_args(body):
    """Tokens after the cleanup script name, e.g. ['%1', '%9'].

    Token-split on purpose: `'%1' in text` false-positives on '%10'.
    """
    idx = body.index(CLEANUP)
    tail = body[idx + len(CLEANUP):]
    for ch in "'\"":
        tail = tail.replace(ch, " ")
    return tail.split()


def pane_ids_mentioned(text):
    return set(re.findall(r"%\d+", text))


def wait_hook_armed(pane, timeout=5.0):
    """Block until the cleanup hook is really visible on `pane`.

    `attach_companion_cleanup_hook` issues `set-option` / `set-hook` through the
    gateway's FIRE-AND-FORGET `_TMUX.spawn()` (`lib/tmux_exec.py`: a bare Popen
    with no wait), so it returns "installed" before the write is guaranteed to
    have landed. Harmless in production — an agent does not die microseconds
    after its shadow is spawned — but a test that kills the agent immediately
    races the install and would report a contract violation that is really a
    fixture bug.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        entries, _ = pane_died_hooks(pane)
        if any(CLEANUP in body for _, body in entries) and \
                pane_option(pane, "remain-on-exit") == "on":
            return True
        time.sleep(0.05)
    fail(f"cleanup hook never became visible on {pane} within {timeout}s")


def wait_gone(pane, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pane not in all_panes():
            return True
        time.sleep(0.1)
    return False


def kill_pane_process(pid):
    """Kill the pane's process so tmux fires `pane-died` (kill-pane does not)."""
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass


# -- App construction ----------------------------------------------------------


class _TaskCache:
    def __init__(self, task_id):
        self._task_id = task_id

    def get_task_id_for_pane(self, pane):
        return self._task_id


def _snapshot(pane_id, window_name):
    return PaneSnapshot(
        pane=TmuxPaneInfo(
            window_index="0", window_name=window_name, pane_index="0",
            pane_id=pane_id, pane_pid=0, current_command="bash",
            width=80, height=24, category=PaneCategory.AGENT,
            session_name=SESSION, shadow_target="",
        ),
        content="", timestamp=0.0, idle_seconds=0.0, is_idle=False,
    )


def mk_monitor():
    monitor = TmuxMonitor(session=SESSION)
    # The ONLY stub on the monitor: session->project discovery is unrelated to
    # the contracts under test, and pinning it to {} makes `_root_for_snap`
    # deterministically fall back to the app's `_project_root` (which is how the
    # test selects the split vs new-window placement config).
    monitor.get_session_to_project_mapping = lambda: {}
    return monitor


def mk_app(monitor, pane_id, window_name, project_root, task_id="42"):
    app = MonitorApp.__new__(MonitorApp)
    app._monitor = monitor
    app._session = SESSION
    app._project_root = project_root
    app._focused_pane_id = pane_id
    app._snapshots = {pane_id: _snapshot(pane_id, window_name)}
    app._task_cache = _TaskCache(task_id)
    app.notified = []
    app.later = []
    app.notify = lambda msg, **kw: app.notified.append(
        (msg, kw.get("severity", "information"))
    )
    app.call_later = lambda *a, **k: app.later.append(a)
    app.push_screen = lambda screen, callback=None: fail(
        "action_launch_shadow must not push a screen"
    )
    return app


def spawn_via_monitor(monitor, pane_id, window_name, project_root, task_id="42"):
    """Drive the real `e` action; only the command resolver is replaced."""
    app = mk_app(monitor, pane_id, window_name, project_root, task_id)
    with patch.object(ma, "resolve_dry_run_command", return_value=SHADOW_CMD):
        app.action_launch_shadow()
    return app


def notified(app, needle):
    return any(needle.lower() in m.lower() for m, _ in app.notified)


# -- Project roots -------------------------------------------------------------

PROJ_SPLIT = Path(TMUX_DIR) / "proj_split"          # no config -> same-window split
PROJ_WINDOW = Path(TMUX_DIR) / "proj_window"        # shadow_same_window: false
PROJ_SPLIT.mkdir(parents=True, exist_ok=True)
_meta = PROJ_WINDOW / "aitasks" / "metadata"
_meta.mkdir(parents=True, exist_ok=True)
(_meta / "project_config.yaml").write_text("tmux:\n  shadow_same_window: false\n")

if mc.load_project_tmux_config(PROJ_SPLIT) != {}:
    fail("PROJ_SPLIT should yield an empty tmux config")
if mc.load_project_tmux_config(PROJ_WINDOW).get("shadow_same_window") is not False:
    fail("PROJ_WINDOW config did not parse (is PyYAML importable?)")

MONITOR = mk_monitor()
MONITOR_PANE = sorted(panes_in_window("home"))[0]   # stands in for `ait monitor`


# -- Case A: split placement ---------------------------------------------------

select_home()
agent_a, agent_a_pid = new_agent_window("agent-A")
app_a = spawn_via_monitor(MONITOR, agent_a, "agent-A", PROJ_SPLIT, task_id="42")

shadows = shadows_of(agent_a)
if len(shadows) != 1:
    fail(f"A: expected exactly 1 stamped shadow for {agent_a}, got {shadows!r} "
         f"(notifications: {app_a.notified!r})")
shadow_a = shadows[0]
if shadow_a not in panes_in_window("agent-A"):
    fail(f"A: shadow {shadow_a} is not in the followed agent's window")
if active_window() != "home":
    fail(f"A: split placement moved the active window to {active_window()!r} "
         "(select_window=False must emit no select-window)")
if pane_option(agent_a, "remain-on-exit") != "on":
    fail("A: remain-on-exit was not set on the agent pane")

entries_a, raw_a = pane_died_hooks(agent_a)
cleanups_a = [(i, b) for i, b in entries_a if CLEANUP in b]
if len(cleanups_a) != 1:
    fail(f"A: expected exactly 1 cleanup hook, got {entries_a!r}")
args_a = cleanup_hook_args(cleanups_a[0][1])
if args_a != [agent_a, shadow_a]:
    fail(f"A: PINNED companion contract broken — hook args {args_a!r}, "
         f"want [{agent_a!r}, {shadow_a!r}]")
mentioned = pane_ids_mentioned(raw_a)
if MONITOR_PANE in mentioned:
    fail(f"A: the monitor's own pane {MONITOR_PANE} appears in the agent's hooks: {raw_a!r}")
if not notified(app_a, "launched shadow agent"):
    fail(f"A: expected a success notification, got {app_a.notified!r}")
print(f"OK A split placement (agent={agent_a} shadow={shadow_a})")


# -- Case B: separate-window placement ----------------------------------------

select_home()
agent_b, _ = new_agent_window("agent-B")
app_b = spawn_via_monitor(MONITOR, agent_b, "agent-B", PROJ_WINDOW, task_id="77")

shadows = shadows_of(agent_b)
if len(shadows) != 1:
    fail(f"B: expected exactly 1 stamped shadow, got {shadows!r} "
         f"(notifications: {app_b.notified!r})")
shadow_b = shadows[0]
if "agent-shadow-77" not in window_names():
    fail(f"B: expected a separate window 'agent-shadow-77', windows={window_names()!r}")
if shadow_b not in panes_in_window("agent-shadow-77"):
    fail(f"B: shadow {shadow_b} is not in the agent-shadow-77 window")
if active_window() != "home":
    fail(f"B: new-window placement moved the active window to {active_window()!r} "
         "(select_window=False must add -d)")

entries_b, raw_b = pane_died_hooks(agent_b)
cleanups_b = [(i, b) for i, b in entries_b if CLEANUP in b]
if len(cleanups_b) != 1 or cleanup_hook_args(cleanups_b[0][1]) != [agent_b, shadow_b]:
    fail(f"B: hook does not name the shadow: {entries_b!r}")
if MONITOR_PANE in pane_ids_mentioned(raw_b):
    fail(f"B: the monitor's own pane {MONITOR_PANE} appears in the agent's hooks")
print(f"OK B separate-window placement (agent={agent_b} shadow={shadow_b})")


# -- Case C (AC 2a): a pre-existing CLEANUP hook is left alone ------------------

select_home()
agent_c, _ = new_agent_window("agent-C")
companion_a, _ = split_into(agent_c)
status = alu.attach_companion_cleanup_hook(agent_c, companion_a)
if status != "installed":
    fail(f"C: fixture pre-arm returned {status!r}, want 'installed'")

app_c = spawn_via_monitor(MONITOR, agent_c, "agent-C", PROJ_SPLIT, task_id="43")

shadows = shadows_of(agent_c)
if len(shadows) != 1:
    fail(f"C: the spawn must still succeed; stamped shadows={shadows!r} "
         f"(notifications: {app_c.notified!r})")
shadow_c = shadows[0]
entries_c, raw_c = pane_died_hooks(agent_c)
cleanups_c = [(i, b) for i, b in entries_c if CLEANUP in b]
if len(cleanups_c) != 1:
    fail(f"C: a second cleanup entry was appended — hooks={entries_c!r}")
args_c = cleanup_hook_args(cleanups_c[0][1])
if args_c != [agent_c, companion_a]:
    fail(f"C: the prior companion was overwritten — hook args {args_c!r}, "
         f"want [{agent_c!r}, {companion_a!r}]")
if shadow_c in pane_ids_mentioned(raw_c):
    fail(f"C: the new shadow {shadow_c} replaced the recorded companion")
if notified(app_c, "could not be wired"):
    fail(f"C: 'existing' must not surface the fail-closed warning: {app_c.notified!r}")
if not notified(app_c, "launched shadow agent"):
    fail(f"C: expected a success notification, got {app_c.notified!r}")
print(f"OK C pre-existing cleanup hook preserved (companion still {companion_a})")


# -- Case D (AC 2b): an UNRELATED pane-died hook survives, cleanup appends ------

select_home()
agent_d, _ = new_agent_window("agent-D")
SENTINEL = "ait-unrelated-sentinel"
rc, _ = sub(["set-hook", "-p", "-t", agent_d, "pane-died[0]",
             f"display-message {SENTINEL}"])
if rc != 0:
    fail("D: could not install the unrelated fixture hook")

app_d = spawn_via_monitor(MONITOR, agent_d, "agent-D", PROJ_SPLIT, task_id="44")

shadows = shadows_of(agent_d)
if len(shadows) != 1:
    fail(f"D: expected exactly 1 stamped shadow, got {shadows!r}")
shadow_d = shadows[0]
entries_d, raw_d = pane_died_hooks(agent_d)
by_index = dict(entries_d)
# BOTH entries are asserted: checking only "our hook is present" would pass even
# if the unrelated one had been destroyed.
if 0 not in by_index or SENTINEL not in by_index[0]:
    fail(f"D: the unrelated pane-died[0] hook was destroyed — hooks={entries_d!r}")
if 1 not in by_index or CLEANUP not in by_index[1]:
    fail(f"D: the cleanup hook was not appended at pane-died[1] — hooks={entries_d!r}")
args_d = cleanup_hook_args(by_index[1])
if args_d != [agent_d, shadow_d]:
    fail(f"D: appended hook args {args_d!r}, want [{agent_d!r}, {shadow_d!r}]")
print(f"OK D unrelated hook preserved, cleanup appended at [1] (shadow={shadow_d})")


# -- Case G: focus negative control -------------------------------------------
# Same shared sink, minimonitor's policy value (select_window=True). If these
# assertions did not discriminate, cases A/B would be passing because the
# fixture is static rather than because select_window=False works.

select_home()
agent_g1, _ = new_agent_window("agent-G1")
mc.spawn_shadow(
    MONITOR, full_cmd=SHADOW_CMD, followed_pane=agent_g1,
    followed_window="agent-G1", session=SESSION, task_id="91",
    target_root=PROJ_SPLIT, companion_pane=None, select_window=True,
    notify=lambda *a, **k: None, schedule_refresh=lambda: None,
)
if active_window() != "agent-G1":
    fail("G1: select_window=True did NOT move the active window on the split "
         f"branch (active={active_window()!r}) — case A's assertion is vacuous")

select_home()
agent_g2, _ = new_agent_window("agent-G2")
mc.spawn_shadow(
    MONITOR, full_cmd=SHADOW_CMD, followed_pane=agent_g2,
    followed_window="agent-G2", session=SESSION, task_id="92",
    target_root=PROJ_WINDOW, companion_pane=None, select_window=True,
    notify=lambda *a, **k: None, schedule_refresh=lambda: None,
)
if active_window() != "agent-shadow-92":
    fail("G2: select_window=True did NOT move the active window on the "
         f"new-window branch (active={active_window()!r})")
print("OK G focus control (select_window=True does move the active window)")


# -- Case F: bypass control for the companion contract -------------------------
# Arm an agent with the WRONG companion — a pane outside its window, which is
# exactly what passing the monitor's own TMUX_PANE would produce — and prove
# `aitask_companion_cleanup.sh` really kills it. Without this, case E's "the
# monitor pane survives" could pass simply because no hook ever fired.

select_home()
victim, _ = new_agent_window("victim-home")
agent_f, agent_f_pid = new_agent_window("agent-F")
status = alu.attach_companion_cleanup_hook(agent_f, victim)
if status != "installed":
    fail(f"F: fixture pre-arm returned {status!r}, want 'installed'")
wait_hook_armed(agent_f)

kill_pane_process(agent_f_pid)
if not wait_gone(victim):
    fail(f"F: the wrongly-named companion {victim} survived the agent's death — "
         "the cleanup hook did not fire, so case E proves nothing")
print(f"OK F bypass control (a wrong companion {victim} IS killed)")


# -- Case E (AC 1, behavioural): the hook fires and kills the right pane --------

if MONITOR_PANE not in all_panes():
    fail("E: the monitor stand-in pane vanished before the test could run")
wait_hook_armed(agent_a)
kill_pane_process(agent_a_pid)
if not wait_gone(shadow_a):
    fail(f"E: the shadow {shadow_a} outlived its agent — the cleanup hook did "
         "not reach it")
if not wait_gone(agent_a):
    fail(f"E: the dead agent pane {agent_a} was not reaped by the cleanup script")
if MONITOR_PANE not in all_panes():
    fail(f"E: the monitor's own pane {MONITOR_PANE} was killed by the followed "
         "agent's exit — the PINNED companion contract is broken")
print(f"OK E hook fired: shadow {shadow_a} died, monitor {MONITOR_PANE} survived")

print("OK monitor_shadow_spawn_live")
PYEOF
)

echo "PASS: tests/test_monitor_shadow_spawn_live.sh"
