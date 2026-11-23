#!/usr/bin/env bash
# tests/test_sitrep_window_select_live.sh — a sitrep open WITH selection moves
# the attached client, also from another session (t2338).
#
# `tests/test_sitrep_window_live.sh` drives every spawn with select_window=False.
# This file covers the selecting call the TUIs make (`ait sitrep open` without
# `--no-select`: the switcher's Sitrep row and `S`, the monitor's `S`), against a
# real tmux server with a real terminal client attached:
#
#   1  a cold spawn for session B, made from a pane in session A: the attached
#      terminal client ends in session B, on the returned agent pane; a control
#      client (`-C`, the shape a monitor keeps on its helper session since t2051)
#      attached to a third session is not moved
#   2  the client back in A, a second call: `focused`, the client in B on the
#      same pane, and no new window
#   3  a cold spawn from a pane in B, the client in B, the user moving to another
#      window while the companion spawns (and the companion warns): the client
#      stays where the user went — `new-window` already gave it the window, and
#      nothing pulls it back; a mutant that focuses unconditionally turns it red
#   4  the same launch, but the user switches the client to ANOTHER SESSION
#      during startup: it stays there (the jump is decided by the session read
#      before the window is created, not after); the same mutant turns it red
#   X  mutant control: the first `switch_to_pane_anywhere` a no-op -> the client
#      stays in A, so case 1's assertion can fail
#   5  two terminal clients: the initiator (in A) detaches during the companion
#      spawn, a second terminal sits in D: the second terminal is not moved —
#      the jump names the initiating client; a mutant that lets tmux pick the
#      client moves the second terminal instead
#   6  the initiator CLOSES during startup and a new terminal attaches to D,
#      usually on the same freed /dev/pts name: the replacement is not moved —
#      the jump re-checks name AND pid; a mutant without the pid check moves it.
#      Pty reuse is the kernel's choice: when the name is not reused the run
#      says so, and the reuse logic is pinned by the unit tests instead.
#   7  the launch read sent THROUGH a control client (the route a control-routed
#      `monitor.tmux_run` takes, t2051): with `-t <caller pane>` it names the
#      terminal client viewing that pane's session (7a); with nobody viewing it,
#      tmux falls back to the control client itself, which
#      `_sitrep_launch_client` refuses, so nothing is moved (7b)
#
# The driver runs with TMUX / TMUX_PANE of a pane in session A, the way the
# switcher's worker runs inside its host TUI pane, so `switch-client`'s
# current-client resolution follows the real call path. Seams, as in the other
# live file: the agent and TUI commands are `tail -f /dev/null`, the companion
# is a sleeper whose argv carries `minimonitor`, and the companion cleanup hook
# is stubbed. Every tmux call goes to a private server (`require_isolated_tmux`
# + its own socket).
#
# Needs `script` (util-linux) for the terminal client; skips without it.
#
# Run: bash tests/test_sitrep_window_select_live.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=lib/scratch_cwd.sh
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

command -v tmux >/dev/null 2>&1 || { echo "SKIP: tmux not available"; exit 0; }
if ! script -qfc true /dev/null >/dev/null 2>&1; then
    echo "SKIP: util-linux script not available (needed for a terminal client)"
    exit 0
fi

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
PASS=0
FAIL=0
TOTAL=0

# shellcheck source=lib/tmux_isolation.sh
. "$PROJECT_DIR/tests/lib/tmux_isolation.sh"
require_isolated_tmux

FIX="$(mktemp -d "${TMPDIR:-/tmp}/ait_sitrep_sel_XXXXXX")"
FIX="$(cd "$FIX" && pwd -P)"
export TMUX_TMPDIR="$FIX"
SOCK="ait_sitrep_sel_$$"
export AITASKS_TMUX_SOCKET="$SOCK"
T() { tmux -L "$SOCK" "$@"; }
BG_PIDS=()
cleanup() {
    exec 9>&- 8>&- 2>/dev/null
    T kill-server 2>/dev/null
    local p _
    for p in "${BG_PIDS[@]}"; do kill "$p" 2>/dev/null; done
    for p in "${BG_PIDS[@]}"; do   # bounded: never hang the run on a client
        for _ in $(seq 1 40); do kill -0 "$p" 2>/dev/null || break; sleep 0.05; done
        kill -9 "$p" 2>/dev/null
    done
    rm -rf "$FIX"
}
trap cleanup EXIT

PYTHON_BIN="$(source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh" && require_ait_python)"

export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t
mkrepo() { mkdir -p "$1" && git -C "$1" init -q && git -C "$1" commit -q --allow-empty -m init; }
ROOT="$FIX/repo"
ROOT_MUTANT="$FIX/repo_mutant"      # the mutant control's own repository
ROOT_SAME="$FIX/repo_same"          # case 3
ROOT_SAME_MUTANT="$FIX/repo_same_mutant"
ROOT_SWITCH="$FIX/repo_switch"      # case 4
ROOT_SWITCH_MUTANT="$FIX/repo_switch_mutant"
ROOT_DETACH="$FIX/repo_detach"      # case 5
ROOT_DETACH_MUTANT="$FIX/repo_detach_mutant"
ROOT_REUSE="$FIX/repo_reuse"        # case 6
ROOT_REUSE_MUTANT="$FIX/repo_reuse_mutant"
mkrepo "$ROOT_REUSE"
mkrepo "$ROOT_REUSE_MUTANT"
mkrepo "$ROOT_DETACH"
mkrepo "$ROOT_DETACH_MUTANT"
mkrepo "$ROOT_SWITCH"
mkrepo "$ROOT_SWITCH_MUTANT"
mkrepo "$ROOT"
mkrepo "$ROOT_MUTANT"
mkrepo "$ROOT_SAME"
mkrepo "$ROOT_SAME_MUTANT"

DRIVER="$FIX/driver.py"
cat > "$DRIVER" <<'PYEOF'
"""spawn_sitrep WITH selection: prints status|pane|window|detail|tui."""
import os
import sys
from pathlib import Path

import agent_launch_utils as alu
from monitor import monitor_core as mc
from tmux_exec import TmuxClient

STANDIN = (sys.executable, "-c", "import time; time.sleep(3600)", "minimonitor")
alu._COMPANION_ARGV = STANDIN
alu._COMPANION_START_COMMAND = " ".join(STANDIN)
alu.attach_companion_cleanup_hook = lambda agent, companion: "installed"
mc.attach_companion_cleanup_hook = lambda agent, companion: "installed"
mc.resolve_dry_run_command = lambda *a, **k: "tail -f /dev/null"
mc.sitrep_tui_command = lambda root: "tail -f /dev/null"
if os.environ.get("AIT_LIVE_MUTANT_NO_FIRST_FOCUS") == "1":
    _real = mc.switch_to_pane_anywhere
    _calls = []

    def _first_is_a_noop(pane, client=None):
        _calls.append(pane)
        return True if len(_calls) == 1 else _real(pane, client=client)
    mc.switch_to_pane_anywhere = _first_is_a_noop
if os.environ.get("AIT_LIVE_MUTANT_ALWAYS_FOCUS") == "1":
    # The pre-gate behaviour: focus as if the client were always elsewhere.
    _real_client = mc._sitrep_launch_client

    def _always_elsewhere(monitor, caller_pane):
        found = _real_client(monitor, caller_pane)
        return found._replace(session="__elsewhere__") if found else None
    mc._sitrep_launch_client = _always_elsewhere
if os.environ.get("AIT_LIVE_MUTANT_NO_PID_CHECK") == "1":
    # The name-only identity: any client holding the name counts.
    mc._sitrep_client_still_attached = lambda monitor, client: True
if os.environ.get("AIT_LIVE_MUTANT_IMPLICIT_CLIENT") == "1":
    # The jump before the client was named: tmux picks the client itself, and
    # nothing re-checks the initiator.
    mc._sitrep_client_still_attached = lambda monitor, client: True
    _real_switch = mc.switch_to_pane_anywhere
    mc.switch_to_pane_anywhere = lambda pane, client=None: _real_switch(pane)
_navigate_to = os.environ.get("AIT_LIVE_NAVIGATE_TO", "")
_switch_client = os.environ.get("AIT_LIVE_SWITCH_CLIENT", "")   # "<tty>|<session>"
_detach_client = os.environ.get("AIT_LIVE_DETACH_CLIENT", "")   # "<tty>"
# "<tty>|<session>|<stdin fifo>|<out file>": close that terminal, then attach a
# new one to <session>; its tty and the script pid go to <out file>.
_replace_client = os.environ.get("AIT_LIVE_REPLACE_CLIENT", "")


def _replace(spec):
    import subprocess
    import time
    tty, target, fifo, out_file = spec.split("|", 3)
    TmuxClient().run(["detach-client", "-t", tty])
    for _ in range(100):                      # the pty is freed with its node
        if not os.path.exists(tty):
            break
        time.sleep(0.03)
    sock = os.environ["AITASKS_TMUX_SOCKET"]
    _, before = TmuxClient().run(["list-clients", "-F", "#{client_tty}"])
    proc = subprocess.Popen(
        ["script", "-qfc", f"tmux -L {sock} attach -t ={target}", "/dev/null"],
        stdin=open(fifo), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        env={**os.environ, "TERM": "xterm-256color"}, start_new_session=True)
    new = ""
    for _ in range(100):
        _, now = TmuxClient().run(["list-clients", "-F", "#{client_tty}"])
        added = sorted(set(now.split()) - set(before.split()))
        if added:
            new = added[0]
            break
        time.sleep(0.05)
    with open(out_file, "w", encoding="utf-8") as fh:
        fh.write(f"{new}|{proc.pid}\n")


if _navigate_to or _switch_client or _detach_client or _replace_client:
    # The user moves on while the companion spawns — to another window, or
    # the client to another session — and the companion spawn warns.
    _real_companion = mc.maybe_spawn_minimonitor

    def _companion_then_move(*a, **k):
        _real_companion(*a, **k)
        if _navigate_to:
            TmuxClient().run(["select-window", "-t", _navigate_to])
        if _switch_client:
            tty, target = _switch_client.split("|", 1)
            TmuxClient().run(["switch-client", "-c", tty, "-t", f"={target}"])
        if _detach_client:
            TmuxClient().run(["detach-client", "-t", _detach_client])
        if _replace_client:
            _replace(_replace_client)
        return None
    mc.maybe_spawn_minimonitor = _companion_then_move


class Gateway:
    def __init__(self):
        self.client = TmuxClient()

    def tmux_run(self, args, timeout=5.0):
        return self.client.run(args, timeout=timeout)


# The caller pane, named the way `sitrep_open` names it (TMUX_PANE).
res = mc.spawn_sitrep(Gateway(), target_root=Path(sys.argv[1]), session=sys.argv[2],
                      select_window=True,
                      caller_pane=os.environ.get("TMUX_PANE") or None)
print(f"{res.status}|{res.pane or ''}|{res.window}|{res.detail}|{res.tui or ''}")
PYEOF

PYPATH="$PROJECT_DIR/.aitask-scripts:$PROJECT_DIR/.aitask-scripts/lib"
field() { local IFS='|'; local -a f; read -ra f <<<"$1"; printf '%s' "${f[$2]:-}"; }

# --- server: A (the caller's session), B (the target), C (the control client's)
T -f /dev/null new-session -d -s sel_a -x 160 -y 48 -n base -c "$ROOT" "tail -f /dev/null"
T new-session -d -s sel_b -x 160 -y 48 -n base -c "$ROOT" "tail -f /dev/null"
T new-session -d -s sel_c -x 160 -y 48 -n base -c "$ROOT" "tail -f /dev/null"
T new-session -d -s sel_d -x 160 -y 48 -n base -c "$ROOT" "tail -f /dev/null"
CALLER_PANE="$(T display-message -p -t '=sel_a:base' '#{pane_id}')"
SOCKET_PATH="$(T display-message -p '#{socket_path}')"
SERVER_PID="$(T display-message -p '#{pid}')"
SESSION_A_ID="$(T display-message -p -t '=sel_a' '#{session_id}')"
CALLER_TMUX="$SOCKET_PATH,$SERVER_PID,${SESSION_A_ID#\$}"
B_PANE="$(T display-message -p -t '=sel_b:base' '#{pane_id}')"
B_WINDOW="$(T display-message -p -t '=sel_b:base' '#{window_id}')"
SESSION_B_ID="$(T display-message -p -t '=sel_b' '#{session_id}')"
B_TMUX="$SOCKET_PATH,$SERVER_PID,${SESSION_B_ID#\$}"

# A real terminal client in A, and a control client in C. Each client's stdin
# is a FIFO this shell holds open on fd 9 (closed by cleanup), so neither sees
# EOF while the test runs and nothing outlives it.
mkfifo "$FIX/clients.in"
TERM=xterm-256color script -qfc "tmux -L $SOCK attach -t =sel_a" /dev/null \
    >/dev/null 2>&1 <"$FIX/clients.in" &
BG_PIDS+=($!)
exec 9>"$FIX/clients.in"
mkfifo "$FIX/control.in"
tmux -L "$SOCK" -C attach -t =sel_c >/dev/null 2>&1 <"$FIX/control.in" &
BG_PIDS+=($!)
exec 8>"$FIX/control.in"

tty_session() {   # tty_session <tty> -> that terminal client's session
    T list-clients -F '#{client_tty}|#{client_session}' 2>/dev/null \
        | awk -F'|' -v t="$1" '$1 == t {print $2; exit}'
}
attach_terminal() {   # attach_terminal <session>: sets NEW_TTY to the new client's tty
    local before
    before="$(T list-clients -F '#{client_tty}' 2>/dev/null | sort)"
    TERM=xterm-256color script -qfc "tmux -L $SOCK attach -t =$1" /dev/null \
        >/dev/null 2>&1 <"$FIX/clients.in" &
    BG_PIDS+=($!)
    NEW_TTY=""
    for _ in $(seq 1 100); do
        NEW_TTY="$(comm -13 <(printf '%s\n' "$before") \
            <(T list-clients -F '#{client_tty}' 2>/dev/null | sort) | head -n1)"
        [[ -n "$NEW_TTY" ]] && return 0
        sleep 0.05
    done
    return 1
}
client_row() {   # client_row <control 0|1> -> "<tty>|<session>"
    T list-clients -F '#{client_control_mode}|#{client_tty}|#{client_session}' 2>/dev/null \
        | awk -F'|' -v c="$1" '$1 == c {print $2 "|" $3; exit}'
}
for _ in $(seq 1 100); do
    [[ -n "$(client_row 0)" && -n "$(client_row 1)" ]] && break
    sleep 0.05
done
TTY="$(field "$(client_row 0)" 0)"
if [[ -z "$TTY" || -z "$(client_row 1)" ]]; then
    echo "FAIL: setup — clients did not attach: $(T list-clients 2>&1)"
    exit 1
fi
echo "SETUP:ok (terminal client $TTY in sel_a, control client in sel_c)"

spawn() {   # spawn <root> [env...] -> "<status>|<pane>|<window>|<detail>|<tui>"
    # The caller is a pane in A unless CALLER_IN_B=1 is among the env words.
    local root="$1"; shift
    local tmux_env="$CALLER_TMUX" pane="$CALLER_PANE" w
    for w in "$@"; do
        [[ "$w" == CALLER_IN_B=1 ]] && { tmux_env="$B_TMUX"; pane="$B_PANE"; }
    done
    env "$@" TMUX="$tmux_env" TMUX_PANE="$pane" PYTHONPATH="$PYPATH" \
        "$PYTHON_BIN" "$DRIVER" "$root" sel_b 2>>"$FIX/spawn.err"
}
client_session() { tty_session "$TTY"; }
client_pane() { T display-message -p -c "$TTY" '#{pane_id}' 2>/dev/null; }
client_window() { T display-message -p -c "$TTY" '#{window_id}' 2>/dev/null; }
windows_in_b() { T list-windows -t '=sel_b' -F '#{window_id}' | wc -l | tr -d ' '; }

# --- 1: cold spawn for B, from a pane in A -------------------------------------
out="$(spawn "$ROOT")"
agent="$(field "$out" 1)"
assert_eq "1: cold spawn status" "spawned" "$(field "$out" 0)"
assert_eq "1: no warning" "" "$(field "$out" 3)"
assert_eq "1: terminal client moved to the target session" "sel_b" "$(client_session)"
assert_eq "1: terminal client on the agent pane" "$agent" "$(client_pane)"
assert_eq "1: control client not moved" "sel_c" "$(field "$(client_row 1)" 1)"
wins_after_cold="$(windows_in_b)"

# --- 2: back in A, a second call focuses the same pane ------------------------
T switch-client -c "$TTY" -t '=sel_a'
assert_eq "2: setup — client back in A" "sel_a" "$(client_session)"
out="$(spawn "$ROOT")"
assert_eq "2: repeat status" "focused" "$(field "$out" 0)"
assert_eq "2: same agent pane" "$agent" "$(field "$out" 1)"
assert_eq "2: terminal client in the target session" "sel_b" "$(client_session)"
assert_eq "2: terminal client on the agent pane" "$agent" "$(client_pane)"
assert_eq "2: no new window" "$wins_after_cold" "$(windows_in_b)"

# --- 3: same-session caller who moved on during the companion spawn ------------
assert_eq "3: setup — client in B" "sel_b" "$(client_session)"
out="$(spawn "$ROOT_SAME" CALLER_IN_B=1 AIT_LIVE_NAVIGATE_TO="$B_WINDOW")"
assert_eq "3: cold spawn status" "spawned" "$(field "$out" 0)"
assert_contains "3: the companion warned" "companion_not_spawned" "$(field "$out" 3)"
assert_eq "3: the client stays in B" "sel_b" "$(client_session)"
assert_eq "3: the client stays on the window the user chose" "$B_WINDOW" "$(client_window)"
out="$(spawn "$ROOT_SAME_MUTANT" CALLER_IN_B=1 AIT_LIVE_NAVIGATE_TO="$B_WINDOW" \
    AIT_LIVE_MUTANT_ALWAYS_FOCUS=1)"
assert_eq "3X: an unconditional focus pulls the client back (control)" \
    "$(field "$out" 1)" "$(client_pane)"

# --- 4: same-session caller who switched SESSIONS during the companion spawn ---
T switch-client -c "$TTY" -t '=sel_b'
assert_eq "4: setup — client in B" "sel_b" "$(client_session)"
out="$(spawn "$ROOT_SWITCH" CALLER_IN_B=1 AIT_LIVE_SWITCH_CLIENT="$TTY|sel_a")"
assert_eq "4: cold spawn status" "spawned" "$(field "$out" 0)"
assert_eq "4: the client stays in the session the user chose" "sel_a" "$(client_session)"
T switch-client -c "$TTY" -t '=sel_b'
out="$(spawn "$ROOT_SWITCH_MUTANT" CALLER_IN_B=1 AIT_LIVE_SWITCH_CLIENT="$TTY|sel_a" \
    AIT_LIVE_MUTANT_ALWAYS_FOCUS=1)"
assert_eq "4X: a jump decided after startup pulls the client back (control)" \
    "sel_b" "$(client_session)"

# --- X: mutant control — the cold-spawn assertion can fail --------------------
T switch-client -c "$TTY" -t '=sel_a'
out="$(spawn "$ROOT_MUTANT" AIT_LIVE_MUTANT_NO_FIRST_FOCUS=1)"
assert_eq "X: mutant cold spawn status" "spawned" "$(field "$out" 0)"
assert_eq "X: without the focus the client stays in A (control)" "sel_a" "$(client_session)"

# --- 7: the launch read through a control client --------------------------------
# (Before 5/6, while the initiating terminal client still views A; nobody views
# B at this point.) Control-mode command syntax: single-quoted arguments. The
# first %begin/%end block answers the attach itself and is empty, so take the
# first non-empty line of any block.
T switch-client -c "$TTY" -t '=sel_a'
ctl_fmt="$(printf '#{client_name}\t#{client_pid}\t#{client_control_mode}\t#{client_session}')"
via_control() {   # via_control <pane> -> the launch read sent through a control client
    printf "display-message -p -t '%s' '%s'\n" "$1" "$ctl_fmt" \
        | timeout 10 tmux -L "$SOCK" -C attach -t =sel_c 2>/dev/null \
        | awk '/^%begin/ {g=1; next} /^%end/ {g=0; next} g && NF {print; exit}'
}
launch_client_of() {   # launch_client_of <canned answer> -> parsed | None
    CTL_OUT="$1" PYTHONPATH="$PYPATH" "$PYTHON_BIN" - <<'PYEOF'
import os
from monitor import monitor_core as mc

class Canned:
    def tmux_run(self, args, timeout=5.0):
        return 0, os.environ["CTL_OUT"] + "\n"

found = mc._sitrep_launch_client(Canned(), "%0")
print(f"parsed:{found.name}" if found else "None")
PYEOF
}
viewed="$(via_control "$CALLER_PANE")"
assert_eq "7a: via a control client, -t <pane in A> names A's terminal client" \
    "$TTY|0|sel_a" "$(printf '%s' "$viewed" | awk -F'\t' '{print $1 "|" $3 "|" $4; exit}')"
assert_eq "7a: ... and it is accepted" "parsed:$TTY" "$(launch_client_of "$viewed")"
unviewed="$(via_control "$B_PANE")"
assert_eq "7b: with nobody viewing B, the read falls back to the control client" "1" \
    "$(printf '%s' "$unviewed" | awk -F'\t' '{print $3; exit}')"
assert_eq "7b: ... and it is refused (moves nothing)" "None" "$(launch_client_of "$unviewed")"
as_terminal="$(printf '%s' "$unviewed" | awk -F'\t' -v OFS='\t' '{$3 = "0"; print; exit}')"
assert_contains "7b: control — the same answer as a terminal client parses" "parsed:" \
    "$(launch_client_of "$as_terminal")"

# --- 5: the initiator detaches; a second terminal must not be moved -----------
# (Last: it detaches the initiating clients.)
attach_terminal sel_d || { echo "FAIL: setup — second terminal did not attach"; exit 1; }
OTHER_TTY="$NEW_TTY"
T switch-client -c "$TTY" -t '=sel_a'
assert_eq "5: setup — initiator in A" "sel_a" "$(tty_session "$TTY")"
assert_eq "5: setup — second terminal in D" "sel_d" "$(tty_session "$OTHER_TTY")"
out="$(spawn "$ROOT_DETACH" AIT_LIVE_DETACH_CLIENT="$TTY")"
assert_eq "5: cold spawn status" "spawned" "$(field "$out" 0)"
assert_eq "5: the initiator is gone" "" "$(tty_session "$TTY")"
assert_eq "5: the second terminal is not moved" "sel_d" "$(tty_session "$OTHER_TTY")"
attach_terminal sel_a || { echo "FAIL: setup — replacement initiator did not attach"; exit 1; }
INIT2="$NEW_TTY"
out="$(spawn "$ROOT_DETACH_MUTANT" AIT_LIVE_DETACH_CLIENT="$INIT2" \
    AIT_LIVE_MUTANT_IMPLICIT_CLIENT=1)"
assert_eq "5X: an implicit client moves the second terminal (control)" \
    "sel_b" "$(tty_session "$OTHER_TTY")"

# --- 6: the initiator closes; a replacement may get its pty name ---------------
reuse_case() {   # reuse_case <root> <label> [env...] -> sets REPL_TTY, REUSED
    local root="$1" label="$2"; shift 2
    attach_terminal sel_a || { echo "FAIL: setup — $label initiator did not attach"; exit 1; }
    local init="$NEW_TTY" out_file="$FIX/replace_$label.out"
    out="$(spawn "$root" AIT_LIVE_REPLACE_CLIENT="$init|sel_d|$FIX/clients.in|$out_file" "$@")"
    assert_eq "$label: cold spawn status" "spawned" "$(field "$out" 0)"
    local repl
    repl="$(cat "$out_file" 2>/dev/null)"
    REPL_TTY="$(field "$repl" 0)"
    [[ -n "$(field "$repl" 1)" ]] && BG_PIDS+=("$(field "$repl" 1)")
    REUSED=0
    [[ -n "$REPL_TTY" && "$REPL_TTY" == "$init" ]] && REUSED=1
    if [[ -z "$REPL_TTY" ]]; then
        echo "FAIL: setup — $label replacement terminal did not attach"; exit 1
    fi
    echo "NOTE: $label: initiator $init, replacement $REPL_TTY (pty reused: $REUSED)"
}
reuse_case "$ROOT_REUSE" 6
assert_eq "6: the replacement terminal is not moved" "sel_d" "$(tty_session "$REPL_TTY")"
reuse_case "$ROOT_REUSE_MUTANT" 6X AIT_LIVE_MUTANT_NO_PID_CHECK=1
if [[ "$REUSED" == 1 ]]; then
    assert_eq "6X: a name-only identity moves the replacement (control)" \
        "sel_b" "$(tty_session "$REPL_TTY")"
else
    echo "NOTE: 6X: pty not reused this run — the control needs a reused name;" \
        "the reuse logic is pinned by tests/test_sitrep_window.py"
fi

if [[ -s "$FIX/spawn.err" ]]; then
    echo "--- driver stderr ---"
    cat "$FIX/spawn.err"
fi

echo ""
echo "Results: $PASS passed, $FAIL failed (of $TOTAL)"
[[ "$FAIL" -eq 0 ]]
