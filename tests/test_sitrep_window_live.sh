#!/usr/bin/env bash
# tests/test_sitrep_window_live.sh — the sitrep window spawn against a real tmux
# server (t2175_4).
#
# `tests/test_sitrep_window.py` pins the spawn's decisions through mocks. This
# file answers what only a live server can:
#
#   A  a spawn creates the `agent-sitrep` window: the agent pane is stamped with
#      the canonical root, starts in it, and has a companion beside it
#   B  a second call focuses that pane and creates no window
#   C  two concurrent calls leave exactly one stamped pane; the companion is
#      spawned even under a config that turns auto-spawn off and excludes
#      `agent-` from the companion window prefixes
#   D  a call from a linked worktree reaches the main root's pane
#   E  with the companion moved before the agent (`swap-pane`), a call still
#      returns the agent pane
#   F  an unstamped pane in an `agent-sitrep` window with cwd = root is found
#      (the name fallback a restore into a new window relies on)
#   G  an unstamped candidate window listed BEFORE the stamped window: the
#      stamped pane wins
#   H  a frozen stamped pane beside its live companion does not block: a new
#      window is spawned, and the companion is never returned
#
# Seams, all in the driver: the agent command (`resolve_dry_run_command`) is
# `tail -f /dev/null`; the companion command (`_COMPANION_ARGV`) is a sleeper
# whose argv carries `minimonitor`, so the shared helper rule recognises it the
# way it recognises a booting minimonitor, and the test stamps the live marker a
# mounted minimonitor would; the companion's pane-died cleanup hook is not armed
# (no agent exits here, and the hook script is the one tmux caller outside the
# gateway). Everything else is real: the lookup, the lock, the launch, the stamp
# and `maybe_spawn_minimonitor`'s split.
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

DRIVER="$FIX/driver.py"
cat > "$DRIVER" <<'PYEOF'
"""spawn_sitrep against the isolated server: prints status|pane|window|detail."""
import sys
from pathlib import Path

import agent_launch_utils as alu
from monitor import monitor_core as mc
from tmux_exec import TmuxClient

STANDIN = (sys.executable, "-c", "import time; time.sleep(3600)", "minimonitor")
alu._COMPANION_ARGV = STANDIN
alu._COMPANION_START_COMMAND = " ".join(STANDIN)
alu.attach_companion_cleanup_hook = lambda *a, **k: "installed"
mc.resolve_dry_run_command = lambda *a, **k: "tail -f /dev/null"


class Gateway:
    def __init__(self):
        self.client = TmuxClient()

    def tmux_run(self, args, timeout=5.0):
        return self.client.run(args, timeout=timeout)


res = mc.spawn_sitrep(Gateway(), target_root=Path(sys.argv[1]), session=sys.argv[2],
                      select_window=False)
print(f"{res.status}|{res.pane or ''}|{res.window}|{res.detail}")
PYEOF

spawn() {   # spawn <target root> -> "<status>|<pane>|<window>|<detail>"
    PYTHONPATH="$PROJECT_DIR/.aitask-scripts:$PROJECT_DIR/.aitask-scripts/lib" \
        "$PYTHON_BIN" "$DRIVER" "$1" "$SESSION" 2>"$FIX/spawn.err"
}
status_of() { printf '%s' "${1%%|*}"; }
pane_of() { local r="${1#*|}"; printf '%s' "${r%%|*}"; }
stamped_count() { T list-panes -a -F '#{@aitask_sitrep_root}' | grep -cxF "$ROOT"; }
window_count() { T list-windows -t "=$SESSION:" -F x | wc -l | tr -d ' '; }
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

T new-session -d -s "$SESSION" -n base -c "$ROOT" "tail -f /dev/null"

# --- A -----------------------------------------------------------------------
echo "--- A: spawn"
R="$(spawn "$ROOT")"
assert_eq "A spawned" "spawned" "$(status_of "$R")"
AGENT="$(pane_of "$R")"
assert_contains "A window" "$SESSION:agent-sitrep|" "$R"
assert_eq "A stamp = canonical root" "$ROOT" "$(T show-options -p -v -t "$AGENT" @aitask_sitrep_root)"
assert_eq "A agent starts in the root" "$ROOT" "$(T display-message -p -t "$AGENT" '#{pane_current_path}')"
COMP="$(companion_in "=$SESSION:agent-sitrep")"
assert_contains "A a companion pane beside the agent" "%" "$COMP"
assert_eq "A the window holds agent + companion" "2" \
    "$(T list-panes -t "=$SESSION:agent-sitrep" -F x | wc -l | tr -d ' ')"
mark_companions

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
# Deterministic, not a timing race: the first spawn is held INSIDE its lock just
# after its lookup (the AITASK_SITREP_SPAWN_PAUSE_FIFO seam); the second, given
# its own pause point, must not get past ITS lookup while the first is held.
# Without the lock it would, and both would spawn.
T kill-window -t "=$SESSION:agent-sitrep"
mkfifo "$FIX/p1" "$FIX/p2"
AITASK_SITREP_SPAWN_PAUSE_FIFO="$FIX/p1" spawn "$ROOT" > "$FIX/c1" & p1=$!
for _ in $(seq 100); do [[ -f "$FIX/p1.reached" ]] && break; sleep 0.1; done
assert_eq "C the first spawn is held after its lookup" "spawn:after_lookup" \
    "$(cat "$FIX/p1.reached" 2>/dev/null)"
AITASK_SITREP_SPAWN_PAUSE_FIFO="$FIX/p2" spawn "$ROOT" > "$FIX/c2" & p2=$!
second_passed=no
for _ in $(seq 30); do [[ -f "$FIX/p2.reached" ]] && { second_passed=yes; break; }; sleep 0.1; done
assert_eq "C the second spawn waits on the lock while the first is held" "no" "$second_passed"
echo go > "$FIX/p1"
wait "$p1"
# The second one then finds the first's stamp and returns before its pause
# point; release it anyway if it got there, so a regression cannot hang the run.
for _ in $(seq 100); do
    kill -0 "$p2" 2>/dev/null || break
    if [[ -f "$FIX/p2.reached" ]]; then echo go > "$FIX/p2"; break; fi
    sleep 0.1
done
wait "$p2"
assert_eq "C exactly one stamped pane" "1" "$(stamped_count)"
assert_eq "C one spawned, one focused" "focused spawned" \
    "$(cut -d'|' -f1 "$FIX/c1" "$FIX/c2" | sort | tr '\n' ' ' | sed 's/ $//')"
AGENT="$(T list-panes -a -F $'#{pane_id}\t#{@aitask_sitrep_root}' | awk -F'\t' -v r="$ROOT" '$2==r {print $1}')"
assert_contains "C the companion is spawned despite a config excluding agent-" "%" \
    "$(companion_in "$(T display-message -p -t "$AGENT" '#{session_name}:#{window_index}')")"
mark_companions

# --- D -----------------------------------------------------------------------
echo "--- D: linked worktree"
R="$(spawn "$ROOT/aiwork/t1_x")"
assert_eq "D a worktree reaches the main root's pane" "focused|$AGENT" "$(status_of "$R")|$(pane_of "$R")"

# --- E -----------------------------------------------------------------------
echo "--- E: companion moved before the agent"
WIN="$(T display-message -p -t "$AGENT" '#{session_name}:#{window_index}')"
COMP="$(companion_in "$WIN")"
T swap-pane -s "$COMP" -t "$AGENT"
assert_eq "E the companion now lists first" "$COMP" "$(T list-panes -t "$WIN" -F '#{pane_id}' | head -1)"
R="$(spawn "$ROOT")"
assert_eq "E still the agent pane" "focused|$AGENT" "$(status_of "$R")|$(pane_of "$R")"

# --- F -----------------------------------------------------------------------
echo "--- F: name+cwd fallback for an unstamped agent"
T set-option -p -u -t "$AGENT" @aitask_sitrep_root
R="$(spawn "$ROOT")"
assert_eq "F the unstamped agent is found, not its companion" "focused|$AGENT" \
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

# --- H -----------------------------------------------------------------------
echo "--- H: a frozen sitrep beside its live companion does not block"
T set-option -p -t "$AGENT" @aitask_frozen rec00001
R="$(spawn "$ROOT")"
assert_eq "H a new sitrep is spawned" "spawned" "$(status_of "$R")"
NEW="$(pane_of "$R")"
assert_eq "H ... it is neither the frozen agent nor its companion" "new" \
    "$([[ "$NEW" != "$AGENT" && "$NEW" != "$COMP" ]] && echo new || echo reused)"
assert_contains "H ... in its own window" "$SESSION:agent-sitrep-2|" "$R"

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]]
