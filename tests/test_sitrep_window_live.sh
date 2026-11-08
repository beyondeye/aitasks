#!/usr/bin/env bash
# tests/test_sitrep_window_live.sh — the sitrep window spawn against a real tmux
# server (t2175_4; the agent + TUI roles since t2211_2).
#
# `tests/test_sitrep_window.py` pins the spawn's decisions through mocks. This
# file answers what only a live server can:
#
#   A  a spawn creates the `agent-sitrep` window: the agent pane is stamped with
#      the canonical root, starts in it, the TUI is stamped under it, and the
#      companion is beside them
#   I  ... in the agreed layout (coordinates, not counts), the agent active, and
#      discovery lists only the agent
#   B  a second call focuses that pane and creates no window
#   C  two concurrent cold calls leave exactly one agent and one TUI; the
#      companion is spawned even under a config that turns auto-spawn off and
#      excludes `agent-` from the companion window prefixes
#   D  a call from a linked worktree reaches the main root's pane
#   E  with the companion moved before the agent (`swap-pane`), a call still
#      returns the agent pane
#   F  an unstamped pane in an `agent-sitrep` window with cwd = root is found
#      (the name fallback a restore into a new window relies on)
#   G  an unstamped candidate window listed BEFORE the stamped window: the
#      stamped pane wins
#   J  agent only (TUI gone) -> `added_tui`: layout restored, focus untouched
#   K  the agent pane gone, TUI + companion left (the state the cleanup hook
#      leaves — the hook ITSELF runs in tests/test_sitrep_window_hook_live.sh)
#   L  TUI + companion only -> `respawned_agent` above the TUI: layout, focus
#      untouched, the cleanup hook is armed on the new agent, discovery lists it
#      alone
#   M  the TUI alone -> `respawned_agent`, the companion column restored, the TUI
#      still active although the companion spawn refocused the agent
#   N  both alive -> `focused`
#   H  a frozen agent beside its live TUI -> a new window with the agent, the
#      SAME TUI moved under it; the frozen session untouched; one TUI per root;
#      each window lists exactly one agent
#   H2 a frozen agent with no TUI anywhere -> a cold spawn; the frozen window
#      untouched
#   R  races from the agent-only and the TUI-only states: one agent, one TUI
#   X  negative control: a driver whose companion split loses `-f` turns the
#      full-height assertion red
#
# Seams, all in the driver: the agent command (`resolve_dry_run_command`) and the
# TUI command (`sitrep_tui_command`) are `tail -f /dev/null`; the companion
# command (`_COMPANION_ARGV`) is a sleeper whose argv carries `minimonitor`, so
# the shared helper rule recognises it the way it recognises a booting
# minimonitor, and the test stamps the live marker a mounted minimonitor would.
# The companion cleanup hook is stubbed on BOTH import paths
# (`agent_launch_utils` and `monitor_core`'s respawn path) and its calls are
# logged to $AIT_LIVE_HOOK_LOG: the real hook runs raw, un-flagged tmux, so it
# only ever fires under `tests/test_sitrep_window_hook_live.sh`, which refuses
# to run beside a live `-L ait` server. The driver always passes
# `select_window=False`, so every repair here is a no-select repair. Everything
# else is real: the lookup, the lock, the launches, the stamps, the move and
# `maybe_spawn_minimonitor`'s split.
#
# Every tmux call goes to a private server (`require_isolated_tmux` + its own
# socket); the driver reaches it through the gateway via AITASKS_TMUX_SOCKET.
#
# Run: bash tests/test_sitrep_window_live.sh
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
require_isolated_tmux

FIX="$(mktemp -d "${TMPDIR:-/tmp}/ait_sitrep_live_XXXXXX")"
FIX="$(cd "$FIX" && pwd -P)"
export TMUX_TMPDIR="$FIX"
SOCK="ait_sitrep_live_$$"
export AITASKS_TMUX_SOCKET="$SOCK"
SESSION="sitrep_live"
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
git -C "$ROOT" worktree add -q "$ROOT/aiwork/t1_x" -b aitask/t1_x 2>/dev/null
ROOT2="$FIX/repo2"        # the negative control's own repository
mkdir -p "$ROOT2"
git -C "$ROOT2" init -q
git -C "$ROOT2" commit -q --allow-empty -m init

DRIVER="$FIX/driver.py"
cat > "$DRIVER" <<'PYEOF'
"""spawn_sitrep against the isolated server: prints status|pane|window|detail|tui."""
import os
import sys
from pathlib import Path

import agent_launch_utils as alu
from monitor import monitor_core as mc
from tmux_exec import TmuxClient

STANDIN = (sys.executable, "-c", "import time; time.sleep(3600)", "minimonitor")
alu._COMPANION_ARGV = STANDIN
alu._COMPANION_START_COMMAND = " ".join(STANDIN)
def _logged_hook(agent, companion):
    with open(os.environ["AIT_LIVE_HOOK_LOG"], "a", encoding="utf-8") as fh:
        fh.write(f"{agent} {companion}\n")
    return "installed"


alu.attach_companion_cleanup_hook = _logged_hook
mc.attach_companion_cleanup_hook = _logged_hook
mc.resolve_dry_run_command = lambda *a, **k: "tail -f /dev/null"
mc.sitrep_tui_command = lambda root: "tail -f /dev/null"
if os.environ.get("AIT_LIVE_MUTANT_NO_F") == "1":
    _real = alu._companion_check_and_split

    def _no_full_height(*a, **k):
        k["full_height"] = False
        return _real(*a, **k)
    alu._companion_check_and_split = _no_full_height


class Gateway:
    def __init__(self):
        self.client = TmuxClient()

    def tmux_run(self, args, timeout=5.0):
        return self.client.run(args, timeout=timeout)


res = mc.spawn_sitrep(Gateway(), target_root=Path(sys.argv[1]), session=sys.argv[2],
                      select_window=False)
print(f"{res.status}|{res.pane or ''}|{res.window}|{res.detail}|{res.tui or ''}")
PYEOF

VIEW="$FIX/view.py"
cat > "$VIEW" <<'PYEOF'
"""Discovery's agent-listed panes per window: `<window_index> <pane,...>` lines."""
import sys

from monitor.monitor_core import TmuxMonitor

mon = TmuxMonitor(session=sys.argv[1], all_sessions=False, agent_prefixes=["agent-"])
by_window = {}
for p in mon.discover_panes():
    by_window.setdefault(p.window_index, []).append(p.pane_id)
for w in sorted(by_window):
    print(w, ",".join(by_window[w]))
PYEOF

PYPATH="$PROJECT_DIR/.aitask-scripts:$PROJECT_DIR/.aitask-scripts/lib"
export AIT_LIVE_HOOK_LOG="$FIX/hooks.log"
: > "$AIT_LIVE_HOOK_LOG"
spawn() {   # spawn <target root> -> "<status>|<pane>|<window>|<detail>|<tui>"
    PYTHONPATH="$PYPATH" "$PYTHON_BIN" "$DRIVER" "$1" "$SESSION" 2>>"$FIX/spawn.err"
}
listed_in() {   # listed_in <pane> -> the agent-listed panes of that pane's window
    local w
    w="$(T display-message -p -t "$1" '#{window_index}')"
    PYTHONPATH="$PYPATH" "$PYTHON_BIN" "$VIEW" "$SESSION" 2>>"$FIX/spawn.err" \
        | awk -v w="$w" '$1 == w {print $2}'
}
field() { local IFS='|'; local -a f; read -ra f <<<"$1"; printf '%s' "${f[$2]:-}"; }
status_of() { field "$1" 0; }
pane_of() { field "$1" 1; }
detail_of() { field "$1" 3; }
tui_of() { field "$1" 4; }
win_of() { T display-message -p -t "$1" '#{session_name}:#{window_index}'; }
stamped_count() { T list-panes -a -F '#{@aitask_sitrep_root}' | grep -cxF "$ROOT"; }
live_tui_count() {
    T list-panes -a -F $'#{@aitask_sitrep_tui_root}\t#{@aitask_frozen}\t#{pane_dead}' \
        | awk -F'\t' -v r="$ROOT" '$1 == r && $2 == "" && $3 != "1"' | wc -l | tr -d ' '
}
live_agent_count() {
    T list-panes -a -F $'#{@aitask_sitrep_root}\t#{@aitask_frozen}\t#{pane_dead}' \
        | awk -F'\t' -v r="$ROOT" '$1 == r && $2 == "" && $3 != "1"' | wc -l | tr -d ' '
}
window_count() { T list-windows -t "=$SESSION:" -F x | wc -l | tr -d ' '; }
panes_in() { T list-panes -t "$1" -F x | wc -l | tr -d ' '; }
active_in() { T list-panes -t "$1" -F $'#{pane_active}\t#{pane_id}' | awk -F'\t' '$1 == 1 {print $2}'; }
mark_companions() {   # stamp a live minimonitor marker on every companion stand-in
    local p pid cmd
    while IFS=$'\t' read -r p pid cmd; do
        [[ "$cmd" == *minimonitor* ]] && T set-option -p -t "$p" @aitask_monitor_kind "minimonitor:$pid"
    done < <(T list-panes -a -F $'#{pane_id}\t#{pane_pid}\t#{pane_start_command}')
}
companion_in() {   # companion_in <window target> -> its pane id
    T list-panes -t "$1" -F $'#{pane_id}\t#{pane_start_command}' \
        | awk -F'\t' '$2 ~ /minimonitor/ {print $1; exit}'
}
tui_pane() {   # the live TUI pane for ROOT
    T list-panes -a -F $'#{pane_id}\t#{@aitask_sitrep_tui_root}\t#{@aitask_frozen}' \
        | awk -F'\t' -v r="$ROOT" '$2 == r && $3 == "" {print $1; exit}'
}
agent_pane() {   # the live stamped agent for ROOT
    T list-panes -a -F $'#{pane_id}\t#{@aitask_sitrep_root}\t#{@aitask_frozen}' \
        | awk -F'\t' -v r="$ROOT" '$2 == r && $3 == "" {print $1; exit}'
}
# geometry <agent> <tui> <companion> -> "ok" or the first broken invariant
geometry() {
    local out
    out="$(T list-panes -t "$1" -F '#{pane_id} #{pane_left} #{pane_top} #{pane_width} #{pane_height} #{window_width} #{window_height}')"
    awk -v a="$1" -v t="$2" -v m="$3" '
        { L[$1]=$2; Tp[$1]=$3; W[$1]=$4; H[$1]=$5; ww=$6; wh=$7 }
        END {
            if (!(a in L) || !(t in L) || !(m in L)) { print "missing pane"; exit }
            if (L[a] != 0 || Tp[a] != 0)             { print "agent not at 0,0"; exit }
            if (L[t] != 0)                            { print "tui not at left 0"; exit }
            if (Tp[t] != Tp[a] + H[a] + 1)            { print "tui not under the agent"; exit }
            if (W[t] != W[a])                         { print "tui width != agent width"; exit }
            if (L[m] != W[a] + 1)                     { print "companion not right of the agent"; exit }
            if (Tp[m] != 0)                           { print "companion not at top 0"; exit }
            if (H[m] != wh)                           { print "companion not full height"; exit }
            if (H[a] + H[t] + 1 != wh)                { print "agent + tui != window height"; exit }
            print "ok"
        }' <<<"$out"
}
# race <label>: two concurrent spawns, the first held after its lookup.
race() {
    local label="$1" p1 p2 second_passed=no
    rm -f "$FIX/p1" "$FIX/p2" "$FIX/p1.reached" "$FIX/p2.reached"
    mkfifo "$FIX/p1" "$FIX/p2"
    AITASK_SITREP_SPAWN_PAUSE_FIFO="$FIX/p1" spawn "$ROOT" > "$FIX/c1" & p1=$!
    for _ in $(seq 100); do [[ -f "$FIX/p1.reached" ]] && break; sleep 0.1; done
    assert_eq "$label the first spawn is held after its lookup" "spawn:after_lookup" \
        "$(cat "$FIX/p1.reached" 2>/dev/null)"
    AITASK_SITREP_SPAWN_PAUSE_FIFO="$FIX/p2" spawn "$ROOT" > "$FIX/c2" & p2=$!
    for _ in $(seq 30); do [[ -f "$FIX/p2.reached" ]] && { second_passed=yes; break; }; sleep 0.1; done
    assert_eq "$label the second spawn waits on the lock" "no" "$second_passed"
    echo go > "$FIX/p1"
    wait "$p1"
    # The second one then finds both roles and returns before its pause point;
    # release it anyway if it got there, so a regression cannot hang the run.
    for _ in $(seq 100); do
        kill -0 "$p2" 2>/dev/null || break
        if [[ -f "$FIX/p2.reached" ]]; then echo go > "$FIX/p2"; break; fi
        sleep 0.1
    done
    wait "$p2"
    assert_eq "$label exactly one live agent" "1" "$(live_agent_count)"
    assert_eq "$label exactly one live TUI" "1" "$(live_tui_count)"
    assert_eq "$label one repaired, one focused" "focused" \
        "$(cut -d'|' -f1 "$FIX/c2")"
    mark_companions
}

T new-session -d -s "$SESSION" -x 200 -y 50 -n base -c "$ROOT" "tail -f /dev/null"

# --- A -----------------------------------------------------------------------
echo "--- A: spawn"
R="$(spawn "$ROOT")"
assert_eq "A spawned" "spawned" "$(status_of "$R")"
AGENT="$(pane_of "$R")"
TUI="$(tui_of "$R")"
assert_contains "A window" "$SESSION:agent-sitrep|" "$R"
assert_eq "A no warnings" "" "$(detail_of "$R")"
assert_eq "A stamp = canonical root" "$ROOT" "$(T show-options -p -v -t "$AGENT" @aitask_sitrep_root)"
assert_eq "A agent starts in the root" "$ROOT" "$(T display-message -p -t "$AGENT" '#{pane_current_path}')"
assert_eq "A TUI stamp = canonical root" "$ROOT" "$(T show-options -p -v -t "$TUI" @aitask_sitrep_tui_root)"
assert_eq "A TUI starts in the root" "$ROOT" "$(T display-message -p -t "$TUI" '#{pane_current_path}')"
COMP="$(companion_in "=$SESSION:agent-sitrep")"
assert_contains "A a companion pane beside them" "%" "$COMP"
assert_eq "A the window holds agent + TUI + companion" "3" "$(panes_in "=$SESSION:agent-sitrep")"
mark_companions

# --- I -----------------------------------------------------------------------
echo "--- I: layout"
assert_eq "I geometry" "ok" "$(geometry "$AGENT" "$TUI" "$COMP")"
assert_eq "I the agent is the active pane" "$AGENT" "$(active_in "$AGENT")"
assert_eq "I discovery lists only the agent" "$AGENT" "$(listed_in "$AGENT")"

# --- B -----------------------------------------------------------------------
echo "--- B: second call focuses"
W0="$(window_count)"
R="$(spawn "$ROOT")"
assert_eq "B focused the same pane" "focused|$AGENT" "$(status_of "$R")|$(pane_of "$R")"
assert_eq "B no new window" "$W0" "$(window_count)"

# --- C -----------------------------------------------------------------------
echo "--- C: two concurrent calls on a fresh server state"
# From here on the project's config excludes `agent-` from automatic companions
# and turns auto-spawn off: the sitrep window must still get its companion.
mkdir -p "$ROOT/aitasks/metadata"
printf 'tmux:\n  minimonitor:\n    auto_spawn: false\n    companion_window_prefixes: [create-]\n' \
    > "$ROOT/aitasks/metadata/project_config.yaml"
T kill-window -t "=$SESSION:agent-sitrep"
race "C"
assert_eq "C exactly one stamped agent pane" "1" "$(stamped_count)"
assert_eq "C the first one spawned" "spawned" "$(cut -d'|' -f1 "$FIX/c1")"
AGENT="$(agent_pane)"
TUI="$(tui_pane)"
COMP="$(companion_in "$(win_of "$AGENT")")"
assert_contains "C the companion is spawned despite a config excluding agent-" "%" "$COMP"
assert_eq "C geometry" "ok" "$(geometry "$AGENT" "$TUI" "$COMP")"

# --- D -----------------------------------------------------------------------
echo "--- D: linked worktree"
R="$(spawn "$ROOT/aiwork/t1_x")"
assert_eq "D a worktree reaches the main root's pane" "focused|$AGENT" "$(status_of "$R")|$(pane_of "$R")"

# --- E -----------------------------------------------------------------------
echo "--- E: companion moved before the agent"
WIN="$(win_of "$AGENT")"
T swap-pane -s "$COMP" -t "$AGENT"
assert_eq "E the companion now lists first" "$COMP" "$(T list-panes -t "$WIN" -F '#{pane_id}' | head -1)"
R="$(spawn "$ROOT")"
assert_eq "E still the agent pane" "focused|$AGENT" "$(status_of "$R")|$(pane_of "$R")"
T swap-pane -s "$COMP" -t "$AGENT"     # back, for the layout checks below

# --- F -----------------------------------------------------------------------
echo "--- F: name+cwd fallback for an unstamped agent"
T set-option -p -u -t "$AGENT" @aitask_sitrep_root
R="$(spawn "$ROOT")"
assert_eq "F the unstamped agent is found, not its companion or TUI" "focused|$AGENT" \
    "$(status_of "$R")|$(pane_of "$R")"
T set-option -p -t "$AGENT" @aitask_sitrep_root "$ROOT"

# --- G -----------------------------------------------------------------------
echo "--- G: an unstamped candidate listed before the stamped window"
CAND="$(T new-window -d -b -P -F '#{pane_id}' -t "$WIN" -n agent-sitrep-9 -c "$ROOT" "tail -f /dev/null")"
first="$(T list-panes -a -F $'#{pane_id}\t#{window_name}' | awk -F'\t' '$2 ~ /^agent-sitrep/ {print $1; exit}')"
assert_eq "G the candidate lists first" "$CAND" "$first"
R="$(spawn "$ROOT")"
assert_eq "G the stamped pane wins" "focused|$AGENT" "$(status_of "$R")|$(pane_of "$R")"
T kill-pane -t "$CAND"
WIN="$(win_of "$AGENT")"

# --- J -----------------------------------------------------------------------
echo "--- J: agent only -> the TUI is added"
T kill-pane -t "$TUI"
T select-pane -t "$COMP"
R="$(spawn "$ROOT")"
assert_eq "J added_tui for the same agent" "added_tui|$AGENT" "$(status_of "$R")|$(pane_of "$R")"
TUI="$(tui_of "$R")"
assert_eq "J the new TUI is stamped" "$ROOT" "$(T show-options -p -v -t "$TUI" @aitask_sitrep_tui_root)"
assert_eq "J geometry" "ok" "$(geometry "$AGENT" "$TUI" "$COMP")"
assert_eq "J the companion is still the active pane" "$COMP" "$(active_in "$AGENT")"

# --- K -----------------------------------------------------------------------
echo "--- K: the agent pane gone, TUI + companion left"
T kill-window -t "$WIN"
R="$(spawn "$ROOT")"
assert_eq "K a fresh window" "spawned" "$(status_of "$R")"
AGENT="$(pane_of "$R")"
TUI="$(tui_of "$R")"
WIN="$(win_of "$AGENT")"
COMP="$(companion_in "$WIN")"
mark_companions
assert_contains "K the companion spawn armed the hook on the agent" "$AGENT $COMP" \
    "$(cat "$AIT_LIVE_HOOK_LOG")"
# kill-pane fires no pane-died: this is the state the hook leaves, not the hook.
T kill-pane -t "$AGENT"
assert_eq "K the TUI and the companion stay" "$(printf '%s\n' "$TUI" "$COMP" | sort)" \
    "$(T list-panes -t "$WIN" -F '#{pane_id}' | sort)"

# --- L -----------------------------------------------------------------------
echo "--- L: TUI + companion -> the agent is respawned above the TUI"
T select-pane -t "$COMP"
R="$(spawn "$ROOT")"
assert_eq "L respawned_agent beside the same TUI" "respawned_agent|$TUI" \
    "$(status_of "$R")|$(tui_of "$R")"
assert_eq "L no warnings" "" "$(detail_of "$R")"
AGENT="$(pane_of "$R")"
assert_eq "L the new agent is stamped" "$ROOT" "$(T show-options -p -v -t "$AGENT" @aitask_sitrep_root)"
assert_eq "L geometry" "ok" "$(geometry "$AGENT" "$TUI" "$COMP")"
assert_eq "L the companion is still the active pane" "$COMP" "$(active_in "$AGENT")"
assert_contains "L the hook is armed on the new agent with the surviving companion" \
    "$AGENT $COMP" "$(cat "$AIT_LIVE_HOOK_LOG")"
assert_eq "L discovery lists only the new agent" "$AGENT" "$(listed_in "$AGENT")"

# --- M -----------------------------------------------------------------------
echo "--- M: the TUI alone -> agent respawned, companion column restored"
T kill-pane -t "$AGENT"
T kill-pane -t "$COMP"
assert_eq "M precondition: the TUI is alone and active" "1|$TUI" "$(panes_in "$TUI")|$(active_in "$TUI")"
R="$(spawn "$ROOT")"
assert_eq "M respawned_agent" "respawned_agent" "$(status_of "$R")"
AGENT="$(pane_of "$R")"
COMP="$(companion_in "$(win_of "$TUI")")"
mark_companions
assert_contains "M a companion is back" "%" "$COMP"
assert_eq "M geometry" "ok" "$(geometry "$AGENT" "$TUI" "$COMP")"
assert_eq "M the TUI is still the active pane" "$TUI" "$(active_in "$TUI")"

# --- N -----------------------------------------------------------------------
echo "--- N: both alive -> focused"
R="$(spawn "$ROOT")"
assert_eq "N focused" "focused|$AGENT" "$(status_of "$R")|$(pane_of "$R")"

# --- R -----------------------------------------------------------------------
echo "--- R: races from the agent-only and the TUI-only states"
T kill-pane -t "$TUI"
race "R/agent-only"
assert_eq "R/agent-only the first one added the TUI" "added_tui" "$(cut -d'|' -f1 "$FIX/c1")"
T kill-pane -t "$AGENT"
race "R/tui-only"
assert_eq "R/tui-only the first one respawned the agent" "respawned_agent" \
    "$(cut -d'|' -f1 "$FIX/c1")"
AGENT="$(agent_pane)"
TUI="$(tui_pane)"
COMP="$(companion_in "$(win_of "$AGENT")")"
assert_eq "R geometry" "ok" "$(geometry "$AGENT" "$TUI" "$COMP")"

# --- H -----------------------------------------------------------------------
echo "--- H: a frozen agent beside its live TUI"
OLDWIN="$(win_of "$AGENT")"
FROZEN="$AGENT"
OLDCOMP="$COMP"
T set-option -p -t "$FROZEN" @aitask_frozen rec00001
R="$(spawn "$ROOT")"
assert_eq "H spawned, the TUI moved" "spawned|tui_moved|$TUI" \
    "$(status_of "$R")|$(detail_of "$R")|$(tui_of "$R")"
NEW="$(pane_of "$R")"
NEWWIN="$(win_of "$NEW")"
assert_eq "H ... into a new window" "new" "$([[ "$NEWWIN" != "$OLDWIN" ]] && echo new || echo same)"
assert_contains "H ... named agent-sitrep-<n>" "|$SESSION:agent-sitrep-" "$R"
assert_eq "H the frozen pane is untouched" "rec00001|$ROOT" \
    "$(T show-options -p -v -t "$FROZEN" @aitask_frozen)|$(T show-options -p -v -t "$FROZEN" @aitask_sitrep_root)"
assert_eq "H the old window holds the frozen pane + its companion only" \
    "$(printf '%s\n' "$FROZEN" "$OLDCOMP" | sort)" "$(T list-panes -t "$OLDWIN" -F '#{pane_id}' | sort)"
COMP="$(companion_in "$NEWWIN")"
mark_companions
assert_eq "H the new window holds new agent + the same TUI + companion" \
    "$(printf '%s\n' "$NEW" "$TUI" "$COMP" | sort)" "$(T list-panes -t "$NEWWIN" -F '#{pane_id}' | sort)"
assert_eq "H geometry of the new window" "ok" "$(geometry "$NEW" "$TUI" "$COMP")"
assert_eq "H exactly one live TUI for the root" "1" "$(live_tui_count)"
assert_eq "H the old window lists only the frozen agent" "$FROZEN" "$(listed_in "$FROZEN")"
assert_eq "H the new window lists only the new agent" "$NEW" "$(listed_in "$NEW")"

# --- H2 ----------------------------------------------------------------------
echo "--- H2: a frozen agent and no TUI anywhere -> cold spawn"
T kill-window -t "$NEWWIN"
assert_eq "H2 precondition: no live TUI, no live agent" "0|0" "$(live_tui_count)|$(live_agent_count)"
R="$(spawn "$ROOT")"
assert_eq "H2 spawned with no warnings" "spawned|" "$(status_of "$R")|$(detail_of "$R")"
assert_eq "H2 a new TUI" "1" "$(live_tui_count)"
assert_eq "H2 the frozen window is untouched" \
    "$(printf '%s\n' "$FROZEN" "$OLDCOMP" | sort)" "$(T list-panes -t "$OLDWIN" -F '#{pane_id}' | sort)"

# --- X -----------------------------------------------------------------------
echo "--- X: negative control — a companion split without -f"
R="$(AIT_LIVE_MUTANT_NO_F=1 spawn "$ROOT2")"
assert_eq "X the mutant spawns" "spawned" "$(status_of "$R")"
XA="$(pane_of "$R")"
XT="$(tui_of "$R")"
XC="$(companion_in "$(win_of "$XA")")"
assert_eq "X the geometry check turns red without -f" "red" \
    "$([[ "$(geometry "$XA" "$XT" "$XC")" != ok ]] && echo red || echo green)"
assert_eq "X ... because the companion is no longer full height" "short" \
    "$(T list-panes -t "$XA" -F '#{pane_id} #{pane_height} #{window_height}' \
        | awk -v m="$XC" '$1 == m {print ($2 == $3 ? "full" : "short")}')"

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]]
