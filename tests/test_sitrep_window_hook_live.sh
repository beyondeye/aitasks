#!/usr/bin/env bash
# tests/test_sitrep_window_hook_live.sh — the sitrep window under the REAL
# companion cleanup hook (t2211_2).
#
# `tests/test_sitrep_window_live.sh` stubs the hook. This runner keeps it real,
# because what it pins is the hook's verdict: the sitrep TUI is a real occupant,
# so when the agent exits the dead agent pane is removed and the TUI and the
# minimonitor companion stay — for the first agent and for a respawned one.
#
#   K1  cold spawn: the agent carries the cleanup hook; the agent exits -> its
#       pane is removed, the TUI + companion stay
#   K2  `ait sitrep` respawns the agent above the TUI; the new agent carries the
#       hook too; it exits -> removed again, the TUI + companion stay
#
# GUARDED. `aitask_companion_cleanup.sh` runs as a tmux `pane-died` job with raw,
# un-flagged `tmux` calls (aidocs/framework/tui_conventions.md), so this file
# REFUSES (exit 2) while the dedicated `-L ait` server is running:
# `require_clean_ait_server` FIRST (it reads the real `$TMUX` / socket), then
# `require_isolated_tmux`. Run it from a terminal that is NOT inside tmux, with
# that server stopped. Override on a dedicated box with
# AIT_LIVE_TMUX_TEST_FORCE=1.
#
# Seams, in the driver: the agent and TUI commands are `tail -f /dev/null`; the
# companion is a sleeper whose argv carries `minimonitor` (the test stamps the
# live marker a mounted minimonitor would). The hook, the lookup, the lock, the
# launches and the stamps are real.
#
# Run: bash tests/test_sitrep_window_hook_live.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=lib/scratch_cwd.sh
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

command -v tmux >/dev/null 2>&1 || { echo "SKIP: tmux not available"; exit 0; }

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
PASS=0
FAIL=0
TOTAL=0

# shellcheck source=lib/tmux_isolation.sh
. "$PROJECT_DIR/tests/lib/tmux_isolation.sh"
# ORDER IS LOAD-BEARING: the refusal guard reads what isolation then destroys.
require_clean_ait_server
require_isolated_tmux

FIX="$(mktemp -d "${TMPDIR:-/tmp}/ait_sitrep_hook_XXXXXX")"
FIX="$(cd "$FIX" && pwd -P)"
export TMUX_TMPDIR="$FIX"
SOCK="ait_sitrep_hook_$$"
export AITASKS_TMUX_SOCKET="$SOCK"
SESSION="sitrep_hook"
T() { tmux -L "$SOCK" "$@"; }
cleanup() {
    T kill-server 2>/dev/null
    rm -rf "$FIX"
}
trap cleanup EXIT

PYTHON_BIN="$(source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh" && require_ait_python)"

export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t
ROOT="$FIX/repo"
mkdir -p "$ROOT"
git -C "$ROOT" init -q
git -C "$ROOT" commit -q --allow-empty -m init

DRIVER="$FIX/driver.py"
cat > "$DRIVER" <<'PYEOF'
"""spawn_sitrep against the isolated server: prints status|pane|window|detail|tui."""
import sys
from pathlib import Path

import agent_launch_utils as alu
from monitor import monitor_core as mc
from tmux_exec import TmuxClient

STANDIN = (sys.executable, "-c", "import time; time.sleep(3600)", "minimonitor")
alu._COMPANION_ARGV = STANDIN
alu._COMPANION_START_COMMAND = " ".join(STANDIN)
mc.resolve_dry_run_command = lambda *a, **k: "tail -f /dev/null"
mc.sitrep_tui_command = lambda root: "tail -f /dev/null"


class Gateway:
    def __init__(self):
        self.client = TmuxClient()

    def tmux_run(self, args, timeout=5.0):
        return self.client.run(args, timeout=timeout)


res = mc.spawn_sitrep(Gateway(), target_root=Path(sys.argv[1]), session=sys.argv[2],
                      select_window=False)
print(f"{res.status}|{res.pane or ''}|{res.window}|{res.detail}|{res.tui or ''}")
PYEOF

spawn() {
    PYTHONPATH="$PROJECT_DIR/.aitask-scripts:$PROJECT_DIR/.aitask-scripts/lib" \
        "$PYTHON_BIN" "$DRIVER" "$1" "$SESSION" 2>>"$FIX/spawn.err"
}
field() { local IFS='|'; local -a f; read -ra f <<<"$1"; printf '%s' "${f[$2]:-}"; }
win_of() { T display-message -p -t "$1" '#{session_name}:#{window_index}'; }
mark_companions() {
    local p pid cmd
    while IFS=$'\t' read -r p pid cmd; do
        [[ "$cmd" == *minimonitor* ]] && T set-option -p -t "$p" @aitask_monitor_kind "minimonitor:$pid"
    done < <(T list-panes -a -F $'#{pane_id}\t#{pane_pid}\t#{pane_start_command}')
}
companion_in() {
    T list-panes -t "$1" -F $'#{pane_id}\t#{pane_start_command}' \
        | awk -F'\t' '$2 ~ /minimonitor/ {print $1; exit}'
}
# exit_agent <label> <agent> <window> <tui> <companion>: end the agent's process
# and let the real pane-died hook decide.
exit_agent() {
    local label="$1" agent="$2" win="$3" tui="$4" comp="$5" gone=no
    assert_contains "$label the agent carries the cleanup hook" "aitask_companion_cleanup.sh" \
        "$(T show-hooks -p -t "$agent" 2>/dev/null)"
    kill "$(T display-message -p -t "$agent" '#{pane_pid}')"
    for _ in $(seq 50); do
        T list-panes -t "$win" -F '#{pane_id}' | grep -qxF "$agent" || { gone=yes; break; }
        sleep 0.1
    done
    assert_eq "$label the dead agent pane is removed" "yes" "$gone"
    assert_eq "$label the TUI and the companion stay" "$(printf '%s\n' "$tui" "$comp" | sort)" \
        "$(T list-panes -t "$win" -F '#{pane_id}' | sort)"
}

T new-session -d -s "$SESSION" -x 200 -y 50 -n base -c "$ROOT" "tail -f /dev/null"

echo "--- K1: the first agent exits"
R="$(spawn "$ROOT")"
assert_eq "K1 spawned" "spawned" "$(field "$R" 0)"
AGENT="$(field "$R" 1)"
TUI="$(field "$R" 4)"
WIN="$(win_of "$AGENT")"
COMP="$(companion_in "$WIN")"
mark_companions
exit_agent "K1" "$AGENT" "$WIN" "$TUI" "$COMP"

echo "--- K2: the respawned agent exits"
R="$(spawn "$ROOT")"
assert_eq "K2 respawned beside the same TUI" "respawned_agent|$TUI" \
    "$(field "$R" 0)|$(field "$R" 4)"
exit_agent "K2" "$(field "$R" 1)" "$WIN" "$TUI" "$COMP"

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]]
