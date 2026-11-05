#!/usr/bin/env bash
# test_monitor_harvest_close_live.sh — LIVE isolated-tmux smoke for the monitor's
# `h` (harvest-and-close) flow, end to end (t2206; risk follow-up of t2175_5).
#
# `tests/test_monitor_sitrep_harvest_close.py` pins the flow through MOCKS: its
# host fakes both tmux and the harvest. `tests/test_kill_agent_run_guarded.sh`
# proves the guarded kill alone against a real server. This test drives the
# composed path through the real code against a private tmux server:
#
#   MonitorApp.action_harvest_close()   real `_kill_target_state` (live
#                                        `@aitask_frozen` read) + strict root
#   -> SitrepCloseMixin._harvest_close  real run identity before AND after,
#                                        real gateway `capture-pane`
#   -> _run_sitrep_harvest              the real `aitask_sitrep_harvest.sh
#                                        capture`, writing a real scratch store
#   -> HarvestReport / the dialog's callback
#   -> MonitorApp._close_live_after_harvest -> TmuxMonitor.kill_agent_run_guarded
#
# Cases:
#   A  happy path, twice (control-client route and subprocess route): a Complete
#      banner with follow-ups and a trail handle -> 4 store items, store
#      git-ignored, confirm closes the PANE only (window + companion stay)
#   B  a harvest that fails (`store_not_ignorable`) keeps the pane, and the
#      confirm callback refuses even with a valid run identity
#   C  an `agent-sitrep` window: nothing captured, nothing harvested, no store
#   D  a `respawn-pane -k` between the harvest and the confirm: the guarded kill
#      reports `changed` and the new process keeps running (control: a fresh
#      identity then kills it)
#
# Only UI seams are replaced: the focused-card lookup (a `__new__`-built app has
# no Textual focus), notify / push_screen / call_later (recorded), and
# `_dispatch_harvest_close` (the worker seam — the coroutine is awaited
# directly). `_tmux_async` and `_run_sitrep_harvest` are wrapped by
# PASS-THROUGH spies that record and forward; nothing below them is stubbed.
#
# Isolation: `require_clean_ait_server` (REFUSES inside tmux or with `-L ait`
# alive) then `require_isolated_tmux`; scratch git repos, a scratch HOME /
# session store / projects index, every seam exported before the private server
# starts (aidocs/framework/testing_conventions.md, "Composed acceptance"). A
# sha256 manifest of this repository's `.aitask-sitrep/` and the real
# `~/.config/aitasks` session file + receipts is compared before/after.
#
# Not part of `tests/run_all_python_tests.sh` (a bash test, deliberately opt-in).
# Override the refusal on a dedicated box only: AIT_LIVE_TMUX_TEST_FORCE=1.
#
# Run: bash tests/test_monitor_harvest_close_live.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$REPO_ROOT/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

if ! command -v tmux >/dev/null 2>&1; then
    echo "SKIP: tmux not available"
    exit 0
fi

# Interpreters are resolved BEFORE HOME moves: both are found through $HOME.
# shellcheck source=lib/venv_python.sh
. "$SCRIPT_DIR/lib/venv_python.sh"
PYTHON_BIN="${PYTHON_BIN:-$AITASK_PYTHON}"
if ! "$PYTHON_BIN" -c "import textual, yaml" >/dev/null 2>&1; then
    echo "SKIP: $PYTHON_BIN lacks textual/yaml (run 'ait setup' to build the venv)"
    exit 0
fi
AIT_PYTHON="$(source "$REPO_ROOT/.aitask-scripts/lib/python_resolve.sh" && require_ait_python)"
export AIT_PYTHON

# shellcheck source=lib/tmux_isolation.sh
. "$SCRIPT_DIR/lib/tmux_isolation.sh"
# ORDER IS LOAD-BEARING: the guard reads $TMUX and the real `-L ait` socket,
# both of which `require_isolated_tmux` destroys.
require_clean_ait_server
require_isolated_tmux

REAL_HOME="$HOME"
TOKEN="HCLSMOKE_$$"

# A sha256 manifest of state this test must never write: this repository's
# sitrep store, and the real session store + harvest receipts.
manifest() {
    "$AIT_PYTHON" - "$REPO_ROOT/.aitask-sitrep" "$REAL_HOME/.config/aitasks" <<'PYEOF'
import hashlib, os, sys
store, cfg = sys.argv[1], sys.argv[2]
paths = []
if os.path.isdir(store):
    for d, _dirs, files in os.walk(store):
        paths += [os.path.join(d, f) for f in files]
if os.path.isdir(cfg):
    for d, _dirs, files in os.walk(cfg):
        paths += [os.path.join(d, f) for f in files
                  if f.endswith(".harvested") or f == "agent_sessions.json"]
for p in sorted(paths):
    try:
        with open(p, "rb") as fh:
            print(hashlib.sha256(fh.read()).hexdigest() + "  " + p)
    except OSError as exc:
        print("unreadable  " + p + "  " + type(exc).__name__)
PYEOF
}
MANIFEST_BEFORE="$(manifest)"

SCR="$(mktemp -d "${TMPDIR:-/tmp}/ait_hcl_XXXXXX")"
SCR="$(cd "$SCR" && pwd -P)"
# Short on purpose: tmux appends tmux-<uid>/default, and a long macOS $TMPDIR
# pushes the socket past AF_UNIX's sun_path limit (t2142).
FIXTURE_DIR="$(mktemp -d /tmp/ait_hcl_tmux_XXXXXX)"

cleanup() {
    TMUX_TMPDIR="$FIXTURE_DIR" tmux kill-server 2>/dev/null || true
    chmod -R u+w "$SCR" 2>/dev/null || true
    rm -rf "$SCR" "$FIXTURE_DIR"
}
trap cleanup EXIT

# Every seam is exported BEFORE the private server starts: panes and anything
# the server runs inherit the server's environment, not the caller's.
export HOME="$SCR/home"
mkdir -p "$HOME/.config/aitasks"
export AITASKS_AGENT_SESSIONS_FILE="$HOME/.config/aitasks/agent_sessions.json"
export AITASKS_FROZEN_DIR="$SCR/frozen"
export AITASKS_PROJECTS_INDEX="$SCR/projects.yaml"
printf 'projects:\n' > "$AITASKS_PROJECTS_INDEX"
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t
unset AITASK_SITREP_DIR AITASK_SITREP_HARVEST_PAUSE_FIFO \
      AITASK_SITREP_HARVEST_LOCK_TIMEOUT AITASK_SITREP_HARVEST_RUN_ID \
      AITASK_SITREP_PAUSE_FIFO AITASK_SITREP_LOCK_TIMEOUT TMUX_PANE

new_repo() {   # new_repo <name> -> a fresh git repo (its own main worktree)
    local d="$SCR/$1"
    mkdir -p "$d/aitasks/metadata"
    : > "$d/aitasks/metadata/project_config.yaml"
    printf -- '---\nstatus: Ready\n---\n\nSynthetic follow-up of the smoke run.\n' \
        > "$d/aitasks/t154_hcl_followup.md"
    git -C "$d" init -q
    git -C "$d" add -A
    git -C "$d" commit -q -m init
    printf '%s' "$d"
}

banner() {   # banner <task id> -> a synthetic captured wrap-up (README shape)
    local f="$SCR/banner_$1.txt"
    cat > "$f" <<EOF
● Bash(./.aitask-scripts/aitask_archive.sh $1)
  ⎿  COMMITTED:5531518
     rollout tracked in art:trail-hclsmoke-$$

● t$1 is archived ($TOKEN). Two follow-ups were created for the risks the review found.
  - Pick t154 before the next deploy.

  ✔ aitask workflow complete — t$1 hcl_smoke
    outcome: archived (commit 5531518) · pushed: yes
    follow-ups created: t154, t155

✻ Worked for 3m 1s · done 9:42 AM

❯
EOF
    printf '%s' "$f"
}

REPO_CTRL="$(new_repo repo_ctrl)"
REPO_SUB="$(new_repo repo_sub)"
REPO_SITREP="$(new_repo repo_sitrep)"
REPO_RESP="$(new_repo repo_resp)"
REPO_NEG="$(new_repo repo_neg)"
# A tracked .gitignore negation outranks info/exclude: the helper's local rule
# cannot ignore the store, so the harvest must refuse (test_sitrep_harvest.sh §9).
printf '!.aitask-sitrep/\n!.aitask-sitrep/**\n' > "$REPO_NEG/.gitignore"
git -C "$REPO_NEG" add .gitignore
git -C "$REPO_NEG" commit -q -m negate

for t in 153 163 170 177 180; do banner "$t" >/dev/null; done

(
    cd "$REPO_ROOT" || exit 1
    export TMUX_TMPDIR="$FIXTURE_DIR"
    unset TMUX
    SESSION="ait_hcl_$$"
    tmux new-session -d -x 240 -y 80 -s "$SESSION" -n home "tail -f /dev/null"

    LIB_DIR="$REPO_ROOT/.aitask-scripts/lib"
    MONITOR_DIR="$REPO_ROOT/.aitask-scripts/monitor"
    BOARD_DIR="$REPO_ROOT/.aitask-scripts/board"

    PYTHONPATH="$LIB_DIR:$MONITOR_DIR:$BOARD_DIR:$REPO_ROOT/.aitask-scripts" \
    AIT_TEST_TMUX_DIR="$FIXTURE_DIR" \
    AIT_TEST_SESSION="$SESSION" \
    AIT_TEST_SCR="$SCR" \
    AIT_TEST_TOKEN="$TOKEN" \
    AIT_TEST_REPO_ROOT="$REPO_ROOT" \
    AIT_TEST_REPOS="$REPO_CTRL:$REPO_SUB:$REPO_SITREP:$REPO_RESP:$REPO_NEG" \
    "$PYTHON_BIN" - <<'PYEOF'
"""Live harvest-and-close assertions. Any failure calls fail() -> exit 1."""
import asyncio
import os
import subprocess
import sys
import time

SESSION = os.environ["AIT_TEST_SESSION"]
TMUX_DIR = os.environ["AIT_TEST_TMUX_DIR"]
SCR = os.environ["AIT_TEST_SCR"]
TOKEN = os.environ["AIT_TEST_TOKEN"]
REPO_ROOT = os.environ["AIT_TEST_REPO_ROOT"]
REPO_CTRL, REPO_SUB, REPO_SITREP, REPO_RESP, REPO_NEG = \
    os.environ["AIT_TEST_REPOS"].split(":")
WRITER = os.path.join(REPO_ROOT, ".aitask-scripts", "aitask_sitrep_todo.sh")
COMPANION_SENTINEL = "AIT_HCL_COMPANION_SENTINEL"

import agent_launch_utils as alu
from monitor import monitor_core as mc
from monitor import sitrep_close as sc
from monitor.monitor_app import MonitorApp
from monitor.tmux_monitor import PaneCategory, PaneSnapshot, TmuxMonitor

_env = {**os.environ, "TMUX_TMPDIR": TMUX_DIR}
_env.pop("TMUX", None)


def fail(msg):
    sys.exit(f"FAIL: {msg}")


def sub(args, timeout=10):
    """Raw tmux against the fixture server (test fixture, not app code)."""
    r = subprocess.run(["tmux", *args], capture_output=True, text=True,
                       env=_env, timeout=timeout)
    return r.returncode, (r.stdout or "")


# -- containment: asserted before anything mutates ----------------------------

if alu._TMUX.socket_args != []:
    fail(f"gateway not contained: socket_args={alu._TMUX.socket_args!r}")
rc, out = alu._TMUX.run(["display-message", "-p", "#{socket_path}"])
# realpath on both sides: macOS reports /tmp as /private/tmp.
if rc != 0 or not os.path.realpath(out.strip()).startswith(
        os.path.realpath(TMUX_DIR) + os.sep):
    fail(f"gateway does not reach the fixture server: rc={rc} {out.strip()!r}")
for repo in (REPO_CTRL, REPO_SUB, REPO_SITREP, REPO_RESP, REPO_NEG):
    if not os.path.realpath(repo).startswith(os.path.realpath(SCR) + os.sep):
        fail(f"scratch repo outside the scratch dir: {repo}")
print(f"OK containment (socket_path={out.strip()})")
_rc, _out = sub(["list-panes", "-t", f"={SESSION}:home", "-F", "#{pane_id}"])
HOME_PANE = _out.split()[0] if _rc == 0 and _out.split() else ""
if not HOME_PANE:
    fail("could not find the home pane")


def _is_companion_test(pid):
    try:
        r = subprocess.run(["ps", "-p", str(pid), "-o", "args="],
                           capture_output=True, text=True, timeout=2)
        return r.returncode == 0 and COMPANION_SENTINEL in r.stdout
    except Exception:
        return False


mc._is_companion_process = _is_companion_test


# -- fixture helpers ----------------------------------------------------------

def all_panes():
    rc, out = sub(["list-panes", "-a", "-F", "#{pane_id}"])
    return set(out.split()) if rc == 0 else set()


def pane_alive(pane):
    return pane in all_panes()


def pane_pid(pane):
    rc, out = sub(["display-message", "-p", "-t", pane, "#{pane_pid}"])
    return int(out.strip()) if rc == 0 and out.strip().isdigit() else 0


def pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def window_exists(name):
    rc, out = sub(["list-windows", "-t", f"={SESSION}", "-F", "#{window_name}"])
    return name in out.split()


def wait_for_text(pane, needle, timeout=10.0):
    """Readiness, not a sleep: block until `needle` is on the pane's screen."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        rc, out = sub(["capture-pane", "-p", "-J", "-t", pane])
        if rc == 0 and needle in out:
            return
        time.sleep(0.05)
    fail(f"{needle!r} never appeared in {pane} within {timeout}s")


def agent_window(name, task):
    """An agent window showing banner_<task>.txt, plus a companion stand-in.

    Returns (agent pane, agent pid, companion pane)."""
    banner = os.path.join(SCR, f"banner_{task}.txt")
    rc, out = sub(["new-window", "-d", "-P", "-F", "#{pane_id} #{pane_pid}",
                   "-t", f"={SESSION}:", "-n", name,
                   f"sh -c 'cat {banner}; exec tail -f /dev/null'"])
    if rc != 0:
        fail(f"could not create window {name!r} (rc={rc})")
    pane, _, pid = out.strip().partition(" ")
    rc, out = sub(["split-window", "-d", "-P", "-F", "#{pane_id}", "-t", pane,
                   f"sh -c 'exec -a {COMPANION_SENTINEL} sleep 86400'"])
    if rc != 0 or not out.strip():
        fail(f"could not create the companion stand-in in {name!r}")
    wait_for_text(pane, f"aitask workflow complete — t{task}")
    return pane, int(pid), out.strip()


def store_items(repo):
    """{kind: [ref, ...]} from the real writer's `list`, or {} without a store."""
    store = os.path.join(repo, ".aitask-sitrep")
    if not os.path.isdir(store):
        return {}
    r = subprocess.run([WRITER, "list"], capture_output=True, text=True,
                       env={**os.environ, "AITASK_SITREP_DIR": store}, timeout=30)
    if r.returncode != 0:
        fail(f"writer list failed for {store}: {r.stdout}{r.stderr}")
    found = {}
    for line in r.stdout.splitlines():
        if not line.startswith("ITEM:"):
            continue
        f = line[len("ITEM:"):].split("|")
        found.setdefault(f[2], []).append(f[6])
    return found


def store_contains(repo, needle):
    for d, _dirs, files in os.walk(os.path.join(repo, ".aitask-sitrep")):
        for name in files:
            try:
                with open(os.path.join(d, name), encoding="utf-8",
                          errors="replace") as fh:
                    if needle in fh.read():
                        return True
            except OSError:
                pass
    return False


# -- the real app host --------------------------------------------------------

def mk_app(monitor, pane, root):
    """A `__new__` MonitorApp around the REAL monitor. Only UI seams stubbed."""
    monitor.discover_panes()        # fills `_pane_cache` the way a tick would
    info = monitor.get_pane(pane)
    if info is None or info.category != PaneCategory.AGENT:
        fail(f"discovery did not list {pane} as an agent: {info!r}")
    snap = PaneSnapshot(pane=info, content="", timestamp=0.0,
                        idle_seconds=0.0, is_idle=True)
    app = MonitorApp.__new__(MonitorApp)
    app._monitor = monitor
    app._session = SESSION
    app._project_root = root
    app._snapshots = {pane: snap}
    app._focused_pane_id = pane
    app._session_root_map = {SESSION: root}
    app._task_cache = None
    app.notes, app.pushed, app.later, app.dispatched = [], [], [], []
    app.tmux_calls, app.harvest_calls = [], []
    app.notify = lambda msg, **kw: app.notes.append(
        (msg, kw.get("severity", "information")))
    app.push_screen = lambda screen, callback=None: app.pushed.append(
        (screen, callback))
    app.call_later = lambda *a, **k: app.later.append(a)
    app._current_agent_snapshot = lambda: app._snapshots.get(pane)
    app._dispatch_harvest_close = lambda s, state, r: app.dispatched.append(
        (s, state, r))

    real_tmux_async = monitor._tmux_async

    async def tmux_spy(args, timeout=5.0):
        result = await real_tmux_async(args, timeout=timeout)
        app.tmux_calls.append((list(args), result[0]))
        return result

    monitor._tmux_async = tmux_spy
    real_harvest = app._run_sitrep_harvest

    async def harvest_spy(args, *, stdin=None, timeout):
        app.harvest_calls.append((list(args), stdin))
        return await real_harvest(args, stdin=stdin, timeout=timeout)

    app._run_sitrep_harvest = harvest_spy
    real_for_close = app._harvest_for_close
    app.for_close = []

    async def for_close_spy(snap, state, root):
        result = await real_for_close(snap, state, root)
        app.for_close.append(result)
        return result

    app._harvest_for_close = for_close_spy
    return app


async def harvest(app, label):
    """`h` on the focused card, then the worker body. -> (dialog, callback)."""
    app.action_harvest_close()
    if len(app.dispatched) != 1:
        fail(f"{label}: expected one dispatch, got {app.dispatched!r}; "
             f"notes={app.notes!r}")
    await app._harvest_close(*app.dispatched[0])
    if app._harvest_close_inflight:
        fail(f"{label}: the in-flight flag was left set")
    if len(app.pushed) != 1:
        fail(f"{label}: expected one dialog, got {len(app.pushed)}")
    dialog, callback = app.pushed[0]
    if not isinstance(dialog, sc.HarvestResultDialog):
        fail(f"{label}: pushed {type(dialog).__name__}, not the result dialog")
    return dialog, callback


def capture_calls(app, pane):
    return [a for a, _rc in app.tmux_calls
            if a[:1] == ["capture-pane"] and pane in a]


def noted(app, needle, severity=None):
    return any(needle in m and (severity is None or s == severity)
               for m, s in app.notes)


# -- A: the happy path, on both tmux routes -----------------------------------

async def case_a(label, with_backend, repo, task):
    print(f"== A ({label}) ==")
    window = f"agent-pick-{task}"
    pane, pid, companion = agent_window(window, task)
    monitor = TmuxMonitor(session=SESSION)
    if with_backend and not await monitor.start_control_client():
        fail(f"A/{label}: control client failed to start")
    try:
        app = mk_app(monitor, pane, repo)
        dialog, callback = await harvest(app, f"A/{label}")
        _snap, state, root = app.dispatched[0]
        if state != "live" or root != os.path.realpath(repo):
            fail(f"A/{label}: dispatched state={state!r} root={root!r}")
        idents = [a for a, _ in app.tmux_calls
                  if a[:1] == ["display-message"] and mc.RUN_IDENTITY_FORMAT in a]
        if len(idents) != 2:
            fail(f"A/{label}: expected identity reads before and after, got "
                 f"{len(idents)}")
        caps = capture_calls(app, pane)
        want = ["capture-pane", "-p", "-J", "-t", pane, "-S",
                f"-{sc.HARVEST_CAPTURE_LINES}"]
        if caps != [want]:
            fail(f"A/{label}: gateway capture calls {caps!r}, want [{want!r}]")
        if len(app.harvest_calls) != 1:
            fail(f"A/{label}: harvest calls {app.harvest_calls!r}")
        argv, stdin = app.harvest_calls[0]
        want_argv = ["capture", "--root", os.path.realpath(repo), "--agent",
                     window, "--task", str(task), "--operation", "pick"]
        if argv != want_argv:
            fail(f"A/{label}: harvest argv {argv!r}, want {want_argv!r}")
        if not stdin or TOKEN.encode() not in stdin:
            fail(f"A/{label}: the harvest stdin is not the pane capture")
        rep = dialog._report
        kinds = sorted(i.kind for i in rep.items)
        refs = sorted(i.ref for i in rep.items if i.kind == "task")
        if not (rep.ok and rep.final_kind == "HARVESTED" and rep.added == 4
                and rep.existing == 0):
            fail(f"A/{label}: report {rep!r}")
        if kinds != ["question", "task", "task", "watch"] or refs != ["t154", "t155"]:
            fail(f"A/{label}: items kinds={kinds} refs={refs}")
        items = store_items(repo)
        if sorted(items.get("task", [])) != ["t154", "t155"] \
                or len(items.get("question", [])) != 1 \
                or len(items.get("watch", [])) != 1:
            fail(f"A/{label}: the store holds {items!r}")
        if not store_contains(repo, TOKEN):
            fail(f"A/{label}: the passage was not retained in the store")
        st = subprocess.run(["git", "-C", repo, "status", "--porcelain"],
                            capture_output=True, text=True)
        if st.returncode != 0 or st.stdout.strip():
            fail(f"A/{label}: the store is not git-ignored: {st.stdout!r}")
        if not noted(app, "Harvested: 4 added", "information"):
            fail(f"A/{label}: no success toast: {app.notes!r}")

        callback(True)
        if pane_alive(pane):
            fail(f"A/{label}: the harvested pane survived the confirm")
        if not window_exists(window) or not pane_alive(companion):
            fail(f"A/{label}: the close took the window or the companion")
        if not pane_alive(HOME_PANE):
            fail(f"A/{label}: the home pane was killed")
        if not noted(app, f"Closed {window}"):
            fail(f"A/{label}: no close toast: {app.notes!r}")
        if monitor.get_pane(pane) is not None:
            fail(f"A/{label}: the killed pane is still in the discovery cache")
    finally:
        if with_backend:
            await monitor.close_control_client()
    print(f"OK A ({label}): 4 items stored, pane closed, window + companion kept")


asyncio.run(case_a("ctrl", True, REPO_CTRL, 153))
asyncio.run(case_a("sub", False, REPO_SUB, 163))


# -- B: a failed harvest keeps the pane ---------------------------------------

async def case_b():
    print("== B (failed harvest) ==")
    pane, pid, companion = agent_window("agent-pick-170", 170)
    app = mk_app(TmuxMonitor(session=SESSION), pane, REPO_NEG)
    dialog, callback = await harvest(app, "B")
    rep = dialog._report
    if rep.ok or rep.final_kind != "HARVEST_FAILED" \
            or rep.reason != "store_not_ignorable":
        fail(f"B: report {rep!r}")
    if not rep.verdict().startswith("HARVEST FAILED"):
        fail(f"B: verdict {rep.verdict()!r}")
    if not noted(app, "HARVEST FAILED", "error"):
        fail(f"B: no error toast: {app.notes!r}")
    if not capture_calls(app, pane) or len(app.harvest_calls) != 1:
        fail("B: the failure must come from a real capture + harvest")
    # The refusal below must be the report check: the identity is valid.
    _rep, ident = app.for_close[0]
    if ident is None or ident.pane_id != pane or ident.pane_pid != str(pid):
        fail(f"B: the harvest bound no valid run identity ({ident!r})")
    callback(True)
    if not pane_alive(pane) or pane_pid(pane) != pid or not pid_alive(pid):
        fail("B: a failed harvest's confirm killed the agent")
    if not pane_alive(companion):
        fail("B: the companion was killed")
    if os.path.exists(os.path.join(REPO_NEG, ".aitask-sitrep")):
        fail("B: an un-ignorable store was created anyway")
    print("OK B: store_not_ignorable, nothing closed, nothing written")


asyncio.run(case_b())


# -- C: the sitrep window is never captured or harvested ----------------------

async def case_c():
    print("== C (agent-sitrep) ==")
    pane, pid, _companion = agent_window("agent-sitrep", 177)
    app = mk_app(TmuxMonitor(session=SESSION), pane, REPO_SITREP)
    dialog, callback = await harvest(app, "C")
    rep = dialog._report
    if rep.final_kind != "skipped" or not rep.ok:
        fail(f"C: report {rep!r}")
    if app.harvest_calls:
        fail(f"C: the sitrep window was harvested: {app.harvest_calls!r}")
    if capture_calls(app, pane):
        fail("C: the sitrep window was captured")
    if os.path.exists(os.path.join(REPO_SITREP, ".aitask-sitrep")):
        fail("C: a store was written for the sitrep window")
    print("OK C: no capture, no harvest, no store")


asyncio.run(case_c())


# -- D: a respawn after the harvest is refused --------------------------------

async def case_d():
    print("== D (respawn before confirm) ==")
    pane, pid, companion = agent_window("agent-pick-180", 180)
    monitor = TmuxMonitor(session=SESSION)
    app = mk_app(monitor, pane, REPO_RESP)
    dialog, callback = await harvest(app, "D")
    if not dialog._report.ok:
        fail(f"D: the harvest itself failed: {dialog._report!r}")
    rc, _ = sub(["respawn-pane", "-k", "-t", pane,
                 "sh -c 'echo HCL_NEWRUN; exec tail -f /dev/null'"])
    if rc != 0:
        fail("D: fixture respawn-pane failed")
    deadline = time.monotonic() + 10
    while pane_pid(pane) in (0, pid) and time.monotonic() < deadline:
        time.sleep(0.05)
    new_pid = pane_pid(pane)
    if new_pid in (0, pid):
        fail("D: the respawn kept the pid")
    wait_for_text(pane, "HCL_NEWRUN")

    callback(True)
    if not pane_alive(pane) or pane_pid(pane) != new_pid or not pid_alive(new_pid):
        fail("D: the confirm killed the respawned process")
    if not noted(app, "changed since the harvest", "warning"):
        fail(f"D: no 'changed' warning: {app.notes!r}")

    # Control: the guard, not a broken kill, refused. A fresh identity kills.
    rc, out = sub(["display-message", "-p", "-t", pane, mc.RUN_IDENTITY_FORMAT])
    fresh = mc.parse_run_identity(rc, out, pane)
    if fresh is None:
        fail(f"D: could not read a fresh identity: {rc} {out!r}")
    if monitor.kill_agent_run_guarded(fresh) != ("killed", False):
        fail("D: a fresh identity did not kill the pane (the control failed)")
    if pane_alive(pane) or not pane_alive(companion):
        fail("D: control kill: wrong panes afterwards")
    print("OK D: respawned run kept (changed); a fresh identity kills it")


asyncio.run(case_d())
print("OK harvest-and-close live")
PYEOF
)

# -- isolation: the real store and receipts are untouched ---------------------
MANIFEST_AFTER="$(manifest)"
if [[ "$MANIFEST_BEFORE" == "$MANIFEST_AFTER" ]]; then
    echo "ISOLATION:manifest_unchanged"
else
    changed="$(diff <(printf '%s\n' "$MANIFEST_BEFORE") <(printf '%s\n' "$MANIFEST_AFTER") \
        | sed -n 's/^[<>] [^ ]*  //p' | sort -u)"
    leaked=""
    while IFS= read -r path; do
        [[ -n "$path" && -f "$path" ]] || continue
        if grep -q -e "$TOKEN" -e "hclsmoke-$$" "$path" 2>/dev/null; then
            leaked+="$path"$'\n'
        fi
    done <<<"$changed"
    if [[ -n "$leaked" ]]; then
        echo "FAIL: the smoke run wrote real state:" >&2
        printf '  %s\n' "$leaked" >&2
        exit 1
    fi
    echo "ISOLATION:concurrent_writer (changed, but no trace of this run):"
    printf '  %s\n' "$changed"
fi

echo "PASS: tests/test_monitor_harvest_close_live.sh"
