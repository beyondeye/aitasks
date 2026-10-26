#!/usr/bin/env bash
# test_tmux_spawn_path_live.sh - framework tmux spawns must not depend on the
# spawning process's PATH order (t1689).
#
# tmux hands a new pane the PATH of the client that issued new-window /
# split-window / new-session; an attached control client hands it the server's
# global PATH instead. On a mise host, a pane whose PATH puts ~/.local/bin ahead
# of mise's shims dir runs a `mise x <agent> -- <agent>` wrapper that resolves
# back to itself and loops forever. The gateways normalize the PATH every tmux
# client carries (lib/tmux_exec.py::normalize_spawn_path, lib/spawn_path.sh).
#
# Fixture, on a private tmux server whose global PATH is the hazardous order:
#   $HOME/.local/share/mise/shims/fakeagent  writes REAL  (the real binary)
#   $HOME/.local/bin/fakeagent               writes SHIM, exits 1 (a bounded
#                                            stand-in for the looping wrapper)
# Each case spawns `fakeagent <case>` and reads which one ran. The built-in
# control (raw tmux, no gateway) MUST read SHIM, proving the fixture reproduces
# the hazard; every gateway route must read REAL.
#
# The other direction (t2144): a mise-activated order, with a user tool dir
# ahead of mise on purpose and ~/.local/bin behind it, must reach the pane
# verbatim — $FIX/userbin/fakeagent (writes USER) must keep winning.
#
# Every lib is resolved from this file's own REPO_ROOT, so the same file can be
# copied into a scratch checkout of the pre-fix tree as a negative control.
#
# Run: bash tests/test_tmux_spawn_path_live.sh
# shellcheck disable=SC2016  # the single-quoted `bash -c` snippets and pane
# commands expand in the child shell / pane, never here.
set -uo pipefail

if ! command -v tmux >/dev/null 2>&1; then
    echo "SKIP: tmux not available"
    exit 0
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT_DIR="$REPO_ROOT/tests"
LIB_DIR="$REPO_ROOT/.aitask-scripts/lib"
# Start from an empty read-only dir, never the invoking one (t1826).
# shellcheck source=lib/scratch_cwd.sh
. "$REPO_ROOT/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

# The control-mode case imports monitor_core, which needs `yaml` — a bare system
# python3 may lack it — so resolve the framework interpreter the way
# tests/run_all_python_tests.sh does. Resolved now: it reads $HOME, which the
# fixture replaces below.
# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
. "$LIB_DIR/python_resolve.sh"
PYTHON_BIN="${PYTHON_BIN:-$(require_ait_python 2>/dev/null || echo python3)}"
PY="$(command -v "$PYTHON_BIN" || true)"
if [[ -z "$PY" ]]; then
    echo "SKIP: $PYTHON_BIN not available"
    exit 0
fi
BASH_BIN="$(command -v bash)"
TMUX_BIN="$(command -v tmux)"

# shellcheck source=lib/asserts.sh
. "$SCRIPT_DIR/lib/asserts.sh"
# shellcheck source=lib/tmux_isolation.sh
. "$SCRIPT_DIR/lib/tmux_isolation.sh"
require_isolated_tmux

PASS=0
FAIL=0
TOTAL=0

# Short base dir: macOS caps an AF_UNIX socket path at ~104 bytes and its
# $TMPDIR alone is ~53 (t1729).
FIX="$(mktemp -d /tmp/aitspXXXX)"
cleanup() {
    local d
    for d in sock sock_persist sock_launch; do
        [[ -d "$FIX/$d" ]] && TMUX_TMPDIR="$FIX/$d" "$TMUX_BIN" kill-server 2>/dev/null
    done
    rm -rf "$FIX"
}
trap cleanup EXIT

FHOME="$FIX/home"
MARKS="$FIX/marks"
SHIMS="$FHOME/.local/share/mise/shims"
LOCALBIN="$FHOME/.local/bin"
mkdir -p "$SHIMS" "$LOCALBIN" "$MARKS" "$FIX/sock" "$FIX/sock_persist" "$FIX/sock_launch"
# The marker dir is baked into the scripts: a pane's environment comes from the
# server, not from the spawning client, so an exported variable would not reach it.
cat >"$SHIMS/fakeagent" <<EOF
#!/bin/sh
echo REAL > "$MARKS/\$1"
EOF
cat >"$LOCALBIN/fakeagent" <<EOF
#!/bin/sh
echo SHIM > "$MARKS/\$1"
exit 1
EOF
chmod +x "$SHIMS/fakeagent" "$LOCALBIN/fakeagent"

export HOME="$FHOME"
unset MISE_DATA_DIR XDG_DATA_HOME AITASKS_HOME
# Linux: keep the persistent-session rung off systemd-run, whose unit would not
# inherit TMUX_TMPDIR and would start the server on the real socket dir.
export AIT_NO_SYSTEMD_RUN=1
export TMUX_TMPDIR="$FIX/sock"

TMUX_DIR="$(dirname "$TMUX_BIN")"
BAD_PATH="$LOCALBIN:$SHIMS:$TMUX_DIR:/usr/bin:/bin"
HEALTHY_PATH="$LOCALBIN:$TMUX_DIR:/usr/bin:/bin"

# wait_mark <case> -> the marker's content, or TIMEOUT. Polls on readiness (the
# file appearing), bounded at ~10s.
wait_mark() {
    local f="$MARKS/$1" i
    for ((i = 0; i < 200; i++)); do
        if [[ -s "$f" ]]; then
            cat "$f"
            return 0
        fi
        sleep 0.05
    done
    printf 'TIMEOUT'
}

# The server — and so its global PATH — starts from the hazardous order. That
# is what a control-mode spawn would hand the pane.
PATH="$BAD_PATH" "$TMUX_BIN" new-session -d -s base -x 120 -y 40 "sleep 600"

# --- built-in control: raw tmux reproduces the hazard ---------------------
PATH="$BAD_PATH" "$TMUX_BIN" new-window -d -t "=base:" "fakeagent raw"
assert_eq "control: a raw tmux client hands the pane its own (bad) PATH" \
    "SHIM" "$(wait_mark raw)"

# --- Python gateway: TmuxClient.run ---------------------------------------
PATH="$BAD_PATH" "$PY" - "$LIB_DIR" <<'PYEOF'
import sys
sys.path.insert(0, sys.argv[1])
from tmux_exec import TmuxClient
rc, _ = TmuxClient().run(["new-window", "-d", "-t", "=base:", "fakeagent py_run"])
sys.exit(0 if rc == 0 else 1)
PYEOF
assert_eq "python TmuxClient.run new-window resolves the real binary" \
    "REAL" "$(wait_mark py_run)"

# --- Shell gateway: ait_tmux ----------------------------------------------
PATH="$BAD_PATH" "$BASH_BIN" -c '
    source "$1/tmux_exec.sh"
    ait_tmux new-window -d -t "=base:" "fakeagent sh_run"
' _ "$LIB_DIR"
assert_eq "shell ait_tmux new-window resolves the real binary" \
    "REAL" "$(wait_mark sh_run)"

# --- Control mode: run_via_control with a live control client --------------
# The attached client's spawns get the server's global PATH (bad here), so the
# gateway must route pane-creating verbs around it.
ctl_out="$(PATH="$BAD_PATH" PYTHONPATH="$REPO_ROOT/.aitask-scripts:$LIB_DIR" \
    "$PY" - <<'PYEOF' 2>&1
import sys
from monitor.tmux_control import TmuxControlBackend
from tmux_exec import TmuxClient
backend = TmuxControlBackend(session="base", command_timeout=3.0, socket_args=[])
if not backend.start() or not backend.is_alive:
    print("CONTROL_NOT_ALIVE")
    sys.exit(1)
try:
    # Sanity: the backend really is the channel for ordinary commands.
    rc, out = backend.request_sync(["display-message", "-p", "ctl-ok"])
    print("CTL_ECHO:" + out.strip())
    rc, _ = TmuxClient(socket_args=[]).run_via_control(
        backend, ["new-window", "-d", "-t", "=base:", "fakeagent ctl"])
    print("RC:%d" % rc)
finally:
    backend.stop()
PYEOF
)"
assert_contains "control backend was alive and answering" "CTL_ECHO:ctl-ok" "$ctl_out"
assert_eq "run_via_control new-window resolves the real binary" \
    "REAL" "$(wait_mark ctl)"

# --- Persistent new-session (shell ladder; creates a new server) -----------
TMUX_TMPDIR="$FIX/sock_persist" PATH="$BAD_PATH" "$BASH_BIN" -c '
    source "$1/terminal_compat.sh"
    ait_tmux_new_session_persistent persist "$2" w "fakeagent persist"
' _ "$LIB_DIR" "$FIX"
assert_eq "ait_tmux_new_session_persistent first window resolves the real binary" \
    "REAL" "$(wait_mark persist)"

# --- launch_in_tmux new-session (Python ladder; creates a new server) ------
TMUX_TMPDIR="$FIX/sock_launch" PATH="$BAD_PATH" "$PY" - "$LIB_DIR" "$FIX" <<'PYEOF'
import sys
sys.path.insert(0, sys.argv[1])
from agent_launch_utils import TmuxLaunchConfig, launch_in_tmux
_, err = launch_in_tmux("fakeagent launch", TmuxLaunchConfig(
    session="launch", window="w", new_session=True, new_window=False,
    cwd=sys.argv[2]))
sys.exit(0 if err is None else 1)
PYEOF
assert_eq "launch_in_tmux new-session first window resolves the real binary" \
    "REAL" "$(wait_mark launch)"

# --- Decoy tmux: the reorder must not swap the launcher -----------------------
# The caller's PATH resolves the real tmux first, from ~/.local/bin; a failing
# `tmux` sits in mise's shims dir, which normalization moves ~/.local/bin behind.
# Every route must still run the caller's tmux, while the pane gets the
# reordered PATH (fakeagent -> REAL).
cat >"$SHIMS/tmux" <<'EOF'
#!/bin/sh
exit 23
EOF
chmod +x "$SHIMS/tmux"
ln -s "$TMUX_BIN" "$LOCALBIN/tmux"
DECOY_PATH="$LOCALBIN:$SHIMS:$TMUX_DIR:/usr/bin:/bin"
assert_eq "decoy control: the caller's PATH resolves the real tmux" \
    "$LOCALBIN/tmux" "$(PATH="$DECOY_PATH" command -v tmux)"

PATH="$DECOY_PATH" "$PY" - "$LIB_DIR" <<'PYEOF'
import sys
sys.path.insert(0, sys.argv[1])
from tmux_exec import TmuxClient
rc, _ = TmuxClient().run(["new-window", "-d", "-t", "=base:", "fakeagent decoy_py"])
sys.exit(0 if rc == 0 else 1)
PYEOF
assert_eq "decoy: python gateway runs the caller's tmux" "0" "$?"
assert_eq "decoy: python gateway pane still resolves the real binary" \
    "REAL" "$(wait_mark decoy_py)"

PATH="$DECOY_PATH" "$BASH_BIN" -c '
    source "$1/tmux_exec.sh"
    ait_tmux new-window -d -t "=base:" "fakeagent decoy_sh"
' _ "$LIB_DIR"
assert_eq "decoy: shell gateway runs the caller's tmux" "0" "$?"
assert_eq "decoy: shell gateway pane still resolves the real binary" \
    "REAL" "$(wait_mark decoy_sh)"

# The persistence helpers create a SERVER: clear the earlier cases' ones first.
TMUX_TMPDIR="$FIX/sock_persist" "$TMUX_BIN" kill-server 2>/dev/null
TMUX_TMPDIR="$FIX/sock_persist" PATH="$DECOY_PATH" "$BASH_BIN" -c '
    source "$1/terminal_compat.sh"
    ait_tmux_new_session_persistent persist2 "$2" w "fakeagent decoy_persist"
' _ "$LIB_DIR" "$FIX"
assert_eq "decoy: persistent new-session runs the caller's tmux" "0" "$?"
assert_eq "decoy: persistent new-session pane resolves the real binary" \
    "REAL" "$(wait_mark decoy_persist)"

TMUX_TMPDIR="$FIX/sock_launch" "$TMUX_BIN" kill-server 2>/dev/null
TMUX_TMPDIR="$FIX/sock_launch" PATH="$DECOY_PATH" "$PY" - "$LIB_DIR" "$FIX" <<'PYEOF'
import sys
sys.path.insert(0, sys.argv[1])
from agent_launch_utils import TmuxLaunchConfig, launch_in_tmux
_, err = launch_in_tmux("fakeagent decoy_launch", TmuxLaunchConfig(
    session="launch2", window="w", new_session=True, new_window=False,
    cwd=sys.argv[2]))
sys.exit(0 if err is None else 1)
PYEOF
assert_eq "decoy: launch_in_tmux new-session runs the caller's tmux" "0" "$?"
assert_eq "decoy: launch_in_tmux pane resolves the real binary" \
    "REAL" "$(wait_mark decoy_launch)"
rm -f "$SHIMS/tmux" "$LOCALBIN/tmux"

# --- Healthy order: no mise entry -> the pane PATH is the spawner's, verbatim
pane_cmd='printf %s "$PATH" > '"$MARKS"'/healthy_py'
PATH="$HEALTHY_PATH" "$PY" - "$LIB_DIR" "$pane_cmd" <<'PYEOF'
import sys
sys.path.insert(0, sys.argv[1])
from tmux_exec import TmuxClient
rc, _ = TmuxClient().run(["new-window", "-d", "-t", "=base:", sys.argv[2]])
sys.exit(0 if rc == 0 else 1)
PYEOF
assert_eq "healthy order: python gateway leaves the pane PATH untouched" \
    "$HEALTHY_PATH" "$(wait_mark healthy_py)"

pane_cmd='printf %s "$PATH" > '"$MARKS"'/healthy_sh'
PATH="$HEALTHY_PATH" "$BASH_BIN" -c '
    source "$1/tmux_exec.sh"
    ait_tmux new-window -d -t "=base:" "$2"
' _ "$LIB_DIR" "$pane_cmd"
assert_eq "healthy order: shell gateway leaves the pane PATH untouched" \
    "$HEALTHY_PATH" "$(wait_mark healthy_sh)"

# --- Activated order: a mise-activated shell reaches the pane verbatim (t2144)
# A user tool dir leads on purpose (the shell rc prepends it after mise
# activation), mise's entries follow, ~/.local/bin is already behind them.
USERBIN="$FIX/userbin"
mkdir -p "$USERBIN"
cat >"$USERBIN/fakeagent" <<EOF
#!/bin/sh
echo USER > "$MARKS/\$1"
EOF
chmod +x "$USERBIN/fakeagent"
ACTIVATED_PATH="$USERBIN:$TMUX_DIR:$FHOME/.local/share/mise/command-wrappers/bin:$SHIMS:/usr/bin:/bin:$LOCALBIN"

pane_cmd='printf %s "$PATH" > '"$MARKS"'/act_path_py; fakeagent act_py'
PATH="$ACTIVATED_PATH" "$PY" - "$LIB_DIR" "$pane_cmd" <<'PYEOF'
import sys
sys.path.insert(0, sys.argv[1])
from tmux_exec import TmuxClient
rc, _ = TmuxClient().run(["new-window", "-d", "-t", "=base:", sys.argv[2]])
sys.exit(0 if rc == 0 else 1)
PYEOF
assert_eq "activated order: python gateway leaves the pane PATH untouched" \
    "$ACTIVATED_PATH" "$(wait_mark act_path_py)"
assert_eq "activated order: python gateway pane keeps the user's tool" \
    "USER" "$(wait_mark act_py)"

pane_cmd='printf %s "$PATH" > '"$MARKS"'/act_path_sh; fakeagent act_sh'
PATH="$ACTIVATED_PATH" "$BASH_BIN" -c '
    source "$1/tmux_exec.sh"
    ait_tmux new-window -d -t "=base:" "$2"
' _ "$LIB_DIR" "$pane_cmd"
assert_eq "activated order: shell gateway leaves the pane PATH untouched" \
    "$ACTIVATED_PATH" "$(wait_mark act_path_sh)"
assert_eq "activated order: shell gateway pane keeps the user's tool" \
    "USER" "$(wait_mark act_sh)"

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
echo "ALL TESTS PASSED"
