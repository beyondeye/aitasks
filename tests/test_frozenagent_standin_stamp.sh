#!/usr/bin/env bash
# test_frozenagent_standin_stamp.sh — the stand-in self-stamp contract (t1705_6).
#
# THE ASSUMPTION THIS FILE EXISTS TO PROVE. The whole frozen-agent design rests
# on one unverified-until-now claim: that the freeze engine can respawn an
# agent's pane into `standin_command(<id>)` and get a viewer that marks itself
# ready. Three separate things have to hold for that, and none of them is
# provable off a live server:
#
#   a. the `ait frozenagent --record <id>` argv survives `respawn-pane`'s
#      single-string quoting (respawn-pane takes a COMMAND STRING, not an argv);
#   b. `ait` resolves on the respawned pane's PATH (the pane inherits the tmux
#      SERVER's environment, not the freezing process's);
#   c. the stamp lands on the viewer's OWN pane and on no other — the
#      `mark_monitor_pane` rule. `@aitask_standin_ready` is the only positive
#      evidence separating "stand-in up" from "agent still running", and
#      reconcile's §C table branches on it, so a stamp on the wrong pane is
#      worse than no stamp at all.
#
# It is deliberately the FIRST thing t1705_6 lands (the plan's `pre-phase`
# risk mitigation): if any of a/b/c fails, the fix belongs in `standin_command`
# or the launcher, not in an app that has already been written around it.
#
# It also carries the live half of the `cover_drop_destructive_path` mitigation
# (Tests 5-6): the fake-tmux unit tests in `tests/test_agent_freeze.py` pin the
# DECISIONS, but only a real server proves the kill lands, that a real agent
# sibling keeps the window (and the companion minimonitor with it), and that a
# refused drop leaves pane, record and capture untouched.
#
# Not a tmux-stress test — the viewer only reads and self-stamps — but it runs
# on an isolated server anyway, because it respawns and kills panes.
#
# Run: bash tests/test_frozenagent_standin_stamp.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

command -v tmux >/dev/null 2>&1 || { echo "SKIP: tmux not available"; exit 0; }

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
# Test bodies run inside ( … ) subshells, whose in-process PASS/FAIL increments
# die at subshell exit (CLAUDE.md, t1207).
assert_counters_init

# shellcheck source=lib/venv_python.sh
. "$SCRIPT_DIR/lib/venv_python.sh"

# ISOLATE, do not refuse — and that choice is deliberate, not a shortcut.
# `require_clean_ait_server` exists for tests that run framework code reaching
# tmux OUTSIDE the gateway, where isolation alone is not a sufficient guarantee:
# `aitask_companion_cleanup.sh` fires from a `pane-died` hook with raw,
# un-flagged `tmux`, so no environment override can sandbox it. This file arms
# no hooks. Every call it makes is gateway-routed (`ait_tmux`), and the one
# process it spawns into a pane — the viewer — reaches tmux only through
# `lib/tmux_exec.py` and only ever targets its own `$TMUX_PANE`, which inside
# the isolated server is an isolated pane. So `require_isolated_tmux` is the
# correct policy here, and it keeps the test runnable from inside tmux — which
# is where the freeze feature is actually developed.
# shellcheck source=lib/tmux_isolation.sh
. "$PROJECT_DIR/tests/lib/tmux_isolation.sh"
require_isolated_tmux

# shellcheck source=../.aitask-scripts/lib/tmux_exec.sh
. "$PROJECT_DIR/.aitask-scripts/lib/tmux_exec.sh"

FIXTURE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/ait_fa_stamp_XXXXXX")"
export TMUX_TMPDIR="$FIXTURE_DIR"
SESSION="ait_fa_stamp_$$"

cleanup() {
    tmux kill-server 2>/dev/null || true
    rm -rf "$FIXTURE_DIR" 2>/dev/null || true
}
trap cleanup EXIT

# The store and capture root the viewer will read. Exported BEFORE `new-session`
# so the tmux server — and therefore every pane it spawns — inherits them; a
# pane does not inherit the environment of whoever asks for the respawn.
export AITASKS_AGENT_SESSIONS_FILE="$FIXTURE_DIR/agent_sessions.json"
export AITASKS_FROZEN_DIR="$FIXTURE_DIR/frozen"
# `ait` must resolve on the respawned pane's PATH — assumption (b). Putting the
# repo root on PATH is exactly what a real installation does; if this line were
# what made the test pass in a way production does not, (b) would be untested,
# which is why the pane runs the bare `ait frozenagent` string and never an
# absolute path.
export PATH="$PROJECT_DIR:$PATH"

SESSIONS_SH="$PROJECT_DIR/.aitask-scripts/aitask_agent_sessions.sh"

pane_fmt() { ait_tmux display-message -p -t "$1" "$2" 2>/dev/null; }

# Poll for a pane option to take a value. Returns 0 as soon as it matches.
# A fixed sleep would either be flaky on a loaded box or slow on a fast one; the
# budget is what the assertion is really about ("within 5 s"), not the cadence.
wait_for_option() {
    local pane="$1" option="$2" want="$3" budget="${4:-5}"
    local waited=0
    while [ "$waited" -lt "$((budget * 10))" ]; do
        [ "$(pane_fmt "$pane" "#{$option}")" = "$want" ] && return 0
        sleep 0.1
        waited=$((waited + 1))
    done
    return 1
}

echo "=== Fixture: an isolated server with a two-pane agent window ==="

ait_tmux new-session -d -s "$SESSION" -n scratch "sleep 1000"
sleep 0.3

W="agent-pick-1705"
TARGET="$(ait_tmux new-window -P -F '#{pane_id}' \
    -t "$(ait_tmux_session_target "$SESSION")" -n "$W" "sleep 1000")"
SIBLING="$(ait_tmux split-window -P -F '#{pane_id}' -t "$TARGET" "sleep 1000")"
sleep 0.3

if [ -z "$TARGET" ] || [ -z "$SIBLING" ] || [ "$TARGET" = "$SIBLING" ]; then
    echo "FAIL: fixture did not produce two distinct panes (target='$TARGET' sibling='$SIBLING')"
    assert_record_fail
    assert_counters_load
    exit 1
fi

# One record for the target pane. `upsert` is the store's only creator, and it
# is what the freeze engine's fallback path calls too.
upsert_out="$("$SESSIONS_SH" upsert \
    --root "$PROJECT_DIR" --window "$W" \
    --pane "$TARGET" --pane-pid "$(pane_fmt "$TARGET" '#{pane_pid}')" \
    --operation pick --task-id 1705 --agent-string claudecode/opus5 2>&1)"
RECORD_ID="$(printf '%s\n' "$upsert_out" | sed -n 's/^UPSERTED:\([0-9a-f]*\)|.*/\1/p' | head -n1)"

if [ -z "$RECORD_ID" ]; then
    echo "FAIL: could not create a store record; upsert said: $upsert_out"
    assert_record_fail
    assert_counters_load
    exit 1
fi
echo "record id: $RECORD_ID"

echo "=== Test 1: standin_command() is the argv the engine will respawn ==="
STANDIN_CMD="$("$AITASK_PYTHON" -c '
import sys
sys.path.insert(0, sys.argv[1])
import agent_sessions
print(agent_sessions.standin_command(sys.argv[2]))
' "$PROJECT_DIR/.aitask-scripts/lib" "$RECORD_ID")"
assert_eq "standin_command is the ait verb with the record id" \
    "ait frozenagent --record $RECORD_ID" "$STANDIN_CMD"

echo "=== Test 2: the respawned stand-in stamps its OWN pane, within 5 s ==="
# The freeze engine's step 4/5 in miniature: stamp `@aitask_frozen`, clear any
# stale ready mark, then respawn the agent's own pane into the stand-in.
ait_tmux set-option  -p -t "$TARGET" '@aitask_frozen' "$RECORD_ID"
ait_tmux set-option  -pu -t "$TARGET" '@aitask_standin_ready'
ait_tmux respawn-pane -k -t "$TARGET" "$STANDIN_CMD"

if wait_for_option "$TARGET" '@aitask_standin_ready' "$RECORD_ID" 5; then
    assert_record_pass
else
    assert_record_fail
    echo "FAIL: the stand-in did not stamp @aitask_standin_ready=$RECORD_ID within 5s"
    echo "  observed: '$(pane_fmt "$TARGET" '#{@aitask_standin_ready}')'"
    echo "  pane cmd: '$(pane_fmt "$TARGET" '#{pane_current_command}')'"
    echo "  pane dead: '$(pane_fmt "$TARGET" '#{pane_dead}')'"
    echo "  --- pane output ---"
    ait_tmux capture-pane -p -t "$TARGET" 2>/dev/null | tail -20
fi

echo "=== Test 3: it stamps NO other pane ==="
# The `mark_monitor_pane` rule. A viewer that stamped by record lookup rather
# than by $TMUX_PANE would mark whatever pane the record names — which, after a
# tmux restart or a pane-id recycle, is somebody else's.
assert_eq "the sibling pane carries no ready stamp" \
    "" "$(pane_fmt "$SIBLING" '#{@aitask_standin_ready}')"
assert_eq "the scratch pane carries no ready stamp" \
    "" "$(ait_tmux list-panes -a -F '#{@aitask_standin_ready}' 2>/dev/null \
          | grep -v "^$RECORD_ID\$" | tr -d '\n')"

echo "=== Test 4: the window and the sibling survive the respawn ==="
# `respawn-pane -k` must replace the agent in place, not collapse the window —
# otherwise freezing would destroy the companion minimonitor beside it.
assert_eq "the target pane id is unchanged" \
    "$TARGET" "$(pane_fmt "$TARGET" '#{pane_id}')"
assert_eq "the sibling pane still exists" \
    "$SIBLING" "$(pane_fmt "$SIBLING" '#{pane_id}')"

echo '=== Test 5: a live drop kills the stand-in, sparing agent AND companion ==='
# The `cover_drop_destructive_path` mitigation's live half. The fake-tmux unit
# tests pin the decision; only a real server proves the kill actually lands and
# that a real agent sibling keeps the window (and with it the companion
# minimonitor) alive.
DW="agent-pick-9001"
DROP_PANE="$(ait_tmux new-window -P -F '#{pane_id}' \
    -t "$(ait_tmux_session_target "$SESSION")" -n "$DW" "sleep 1000")"
SIB_PANE="$(ait_tmux split-window -P -F '#{pane_id}' -t "$DROP_PANE" "sleep 1000")"
# A REAL companion pane, marked the way `maybe_spawn_minimonitor` marks one.
# Without it this case could not tell "the window survived" from "the companion
# survived" — the promised assertion is about the companion, and a fixture of
# two bare sleeps cannot make it. The pid is this shell's, so the marker reads
# as LIVE (`monitor_marker_alive`); a stale one would classify as an ordinary
# pane and quietly turn this into a two-real-agents row.
COMP_PANE="$(ait_tmux split-window -P -F '#{pane_id}' -t "$DROP_PANE" "sleep 1000")"
ait_tmux set-option -p -t "$COMP_PANE" '@aitask_monitor_kind' "minimonitor:$$"
sleep 0.3

drop_out="$("$SESSIONS_SH" upsert --root "$PROJECT_DIR" --window "$DW" \
    --pane "$DROP_PANE" --pane-pid "$(pane_fmt "$DROP_PANE" '#{pane_pid}')" 2>&1)"
DROP_ID="$(printf '%s\n' "$drop_out" | sed -n 's/^UPSERTED:\([0-9a-f]*\)|.*/\1/p' | head -n1)"
CAP_DIR="$FIXTURE_DIR/frozen/$DROP_ID"
mkdir -p "$CAP_DIR"
printf 'captured output\n' > "$CAP_DIR/capture.ansi"
printf 'captured output\n' > "$CAP_DIR/capture.txt"
fnonce="$("$SESSIONS_SH" freeze-begin "$DROP_ID" --owner-pid $$ \
    --capture-ansi "$CAP_DIR/capture.ansi" --capture-txt "$CAP_DIR/capture.txt" \
    --lines 1 | sed -n 's/^FREEZING:[0-9a-f]*|\(.*\)/\1/p')"
"$SESSIONS_SH" freeze-commit "$DROP_ID" --nonce "$fnonce" \
    --pane "$DROP_PANE" --pane-pid "$(pane_fmt "$DROP_PANE" '#{pane_pid}')" >/dev/null
ait_tmux set-option -p -t "$DROP_PANE" '@aitask_frozen' "$DROP_ID"

drop_line="$("$PROJECT_DIR/.aitask-scripts/aitask_frozen.sh" drop "$DROP_ID" 2>&1)"
assert_eq "the coordinator reports a clean drop" "DROPPED:$DROP_ID" "$drop_line"
assert_eq "the stand-in pane is gone" "" "$(pane_fmt "$DROP_PANE" '#{pane_id}')"
assert_eq "the real agent sibling SURVIVES (the window did not collapse)" \
    "$SIB_PANE" "$(pane_fmt "$SIB_PANE" '#{pane_id}')"
assert_eq "the COMPANION minimonitor survives too" \
    "$COMP_PANE" "$(pane_fmt "$COMP_PANE" '#{pane_id}')"
assert_eq "…and it is still marked as a live companion" \
    "minimonitor:$$" "$(pane_fmt "$COMP_PANE" '#{@aitask_monitor_kind}')"
assert_eq "the record is gone from the store" \
    "" "$("$SESSIONS_SH" show "$DROP_ID" 2>/dev/null | sed -n 's/^id:\(.*\)/\1/p')"
if [ -d "$CAP_DIR" ]; then
    assert_record_fail; echo "FAIL: the capture directory survived the drop"
else
    assert_record_pass
fi

echo "=== Test 6: a drop refused mid-flight destroys NOTHING ==="
# The fail-closed half: a record whose lease is held by a live coordinator must
# come back untouched — pane, record and capture.
KW="agent-pick-9002"
KEEP_PANE="$(ait_tmux new-window -P -F '#{pane_id}' \
    -t "$(ait_tmux_session_target "$SESSION")" -n "$KW" "sleep 1000")"
sleep 0.3
keep_out="$("$SESSIONS_SH" upsert --root "$PROJECT_DIR" --window "$KW" \
    --pane "$KEEP_PANE" --pane-pid "$(pane_fmt "$KEEP_PANE" '#{pane_pid}')" 2>&1)"
KEEP_ID="$(printf '%s\n' "$keep_out" | sed -n 's/^UPSERTED:\([0-9a-f]*\)|.*/\1/p' | head -n1)"
KEEP_CAP="$FIXTURE_DIR/frozen/$KEEP_ID"
mkdir -p "$KEEP_CAP"; printf 'keep me\n' > "$KEEP_CAP/capture.ansi"; cp "$KEEP_CAP/capture.ansi" "$KEEP_CAP/capture.txt"
knonce="$("$SESSIONS_SH" freeze-begin "$KEEP_ID" --owner-pid $$ \
    --capture-ansi "$KEEP_CAP/capture.ansi" --capture-txt "$KEEP_CAP/capture.txt" \
    --lines 1 | sed -n 's/^FREEZING:[0-9a-f]*|\(.*\)/\1/p')"
"$SESSIONS_SH" freeze-commit "$KEEP_ID" --nonce "$knonce" \
    --pane "$KEEP_PANE" --pane-pid "$(pane_fmt "$KEEP_PANE" '#{pane_pid}')" >/dev/null
ait_tmux set-option -p -t "$KEEP_PANE" '@aitask_frozen' "$KEEP_ID"
# A live restore holds the record ($$ is this shell, demonstrably alive).
"$SESSIONS_SH" restore-begin "$KEEP_ID" --owner-pid $$ --mode resume >/dev/null

refused="$("$PROJECT_DIR/.aitask-scripts/aitask_frozen.sh" drop "$KEEP_ID" 2>&1 || true)"
assert_eq "an in-flight record is refused" "DROP_REFUSED:$KEEP_ID|in_flight" "$refused"
assert_eq "…and its pane is untouched" "$KEEP_PANE" "$(pane_fmt "$KEEP_PANE" '#{pane_id}')"
assert_eq "…and its record survives" "$KEEP_ID" \
    "$("$SESSIONS_SH" show "$KEEP_ID" | sed -n 's/^id:\(.*\)/\1/p')"
if [ -f "$KEEP_CAP/capture.ansi" ]; then
    assert_record_pass
else
    assert_record_fail; echo "FAIL: a refused drop deleted the capture"
fi

echo "=== Test 7: coordinator <-> monitor parity on a REAL window ==="
# WHY THIS LIVES HERE. `tests/test_cleanup_rule_parity.sh` compares all three
# users of the "does this window still hold a real agent?" rule — but it arms
# real `pane-died` hooks, and `aitask_companion_cleanup.sh` reaches tmux with
# raw, un-flagged calls, so it refuses to run while the dedicated `-L ait`
# server is alive. That refusal is correct and must not be forced.
#
# Only the BASH producer needs those hooks. The monitor's
# `kill_agent_pane_smart` (with its kills stubbed) and the coordinator's
# `_other_real_agents` are both hook-free, so the half that this task actually
# introduced — a NEW call site enumerating panes differently (from the pane,
# not from a stored window name) — can be checked here, on an isolated server,
# every run. The bash<->monitor half is unchanged by this task and stays with
# the parity script.
parity_pair() {
    local label="$1" target="$2" windex="$3" expect="$4"
    local py coord
    py="$(PYTHONPATH="$PROJECT_DIR/.aitask-scripts:$PROJECT_DIR/.aitask-scripts/lib" \
        AIT_P_SESSION="$SESSION" AIT_P_TARGET="$target" AIT_P_WINDEX="$windex" \
        "$AITASK_PYTHON" - <<'PYEOF'
import os
from monitor.monitor_core import PaneCategory, TmuxMonitor, TmuxPaneInfo

target = os.environ["AIT_P_TARGET"]
mon = TmuxMonitor(session=os.environ["AIT_P_SESSION"], multi_session=False,
                  exclude_pane="")
rc, out = mon.tmux_run(["display-message", "-p", "-t", target,
                        "#{pane_pid}\t#{@aitask_frozen}"])
pid, frozen = 0, ""
if rc == 0 and out.strip():
    parts = out.splitlines()[0].split("\t")
    try:
        pid = int(parts[0])
    except (ValueError, IndexError):
        pid = 0
    frozen = parts[1].strip() if len(parts) > 1 else ""
mon._pane_cache[target] = TmuxPaneInfo(
    window_index=os.environ["AIT_P_WINDEX"], window_name="parity",
    pane_index="0", pane_id=target, pane_pid=pid, current_command="sleep",
    width=80, height=24, category=PaneCategory.AGENT,
    session_name=os.environ["AIT_P_SESSION"], frozen_record=frozen)
verdict = []
mon.kill_window = lambda p: (verdict.append("window"), True)[1]
mon.kill_pane = lambda p: (verdict.append("pane"), True)[1]
mon._drop_session_record = lambda rid: True
mon.kill_agent_pane_smart(target)
print(verdict[0] if verdict else "none")
PYEOF
)"
    coord="$(PYTHONPATH="$PROJECT_DIR/.aitask-scripts:$PROJECT_DIR/.aitask-scripts/lib" \
        AIT_P_TARGET="$target" "$AITASK_PYTHON" - <<'PYEOF'
import os
import agent_freeze
others = agent_freeze._other_real_agents(os.environ["AIT_P_TARGET"])
print("pane" if others is None else ("window" if others == 0 else "pane"))
PYEOF
)"
    assert_eq "$label [monitor]" "$expect" "$py"
    assert_eq "$label [coordinator]" "$expect" "$coord"
    assert_eq "$label [PARITY]" "$py" "$coord"
}

# One lone agent beside a companion: the window goes.
PW1="parity-1"
P1="$(ait_tmux new-window -P -F '#{pane_id}' \
    -t "$(ait_tmux_session_target "$SESSION")" -n "$PW1" "sleep 1000")"
P1C="$(ait_tmux split-window -P -F '#{pane_id}' -t "$P1" "sleep 1000")"
ait_tmux set-option -p -t "$P1C" '@aitask_monitor_kind' "minimonitor:$$"
sleep 0.3
parity_pair "lone agent + companion" "$P1" \
    "$(ait_tmux display-message -p -t "$P1" '#{window_index}')" window

# A real agent sibling keeps it.
PW2="parity-2"
P2="$(ait_tmux new-window -P -F '#{pane_id}' \
    -t "$(ait_tmux_session_target "$SESSION")" -n "$PW2" "sleep 1000")"
# A second real agent, needed only for its PRESENCE in the window.
ait_tmux split-window -d -t "$P2" "sleep 1000"
P2C="$(ait_tmux split-window -P -F '#{pane_id}' -t "$P2" "sleep 1000")"
ait_tmux set-option -p -t "$P2C" '@aitask_monitor_kind' "minimonitor:$$"
sleep 0.3
parity_pair "agent + agent + companion" "$P2" \
    "$(ait_tmux display-message -p -t "$P2" '#{window_index}')" pane

# A frozen stand-in IS a real sibling (the t1705_4 rule).
PW3="parity-3"
P3="$(ait_tmux new-window -P -F '#{pane_id}' \
    -t "$(ait_tmux_session_target "$SESSION")" -n "$PW3" "sleep 1000")"
P3F="$(ait_tmux split-window -P -F '#{pane_id}' -t "$P3" "sleep 1000")"
P3C="$(ait_tmux split-window -P -F '#{pane_id}' -t "$P3" "sleep 1000")"
ait_tmux set-option -p -t "$P3F" '@aitask_frozen' 'aabbccdd'
ait_tmux set-option -p -t "$P3C" '@aitask_monitor_kind' "minimonitor:$$"
sleep 0.3
parity_pair "agent + frozen stand-in + companion" "$P3" \
    "$(ait_tmux display-message -p -t "$P3" '#{window_index}')" pane

echo "=== Test 8: list mode stamps nothing ==="
# The switcher launches the BARE `ait frozenagent`, which is a list of every
# frozen record — not a stand-in for any one of them. Stamping from there would
# mark whatever pane the user happened to open the list in as record X's
# viewer, which is exactly the wrong-pane failure the self-stamp rule exists to
# prevent. Asserted live because the switcher really does launch it in a pane.
LIST_PANE="$(ait_tmux new-window -P -F '#{pane_id}' \
    -t "$(ait_tmux_session_target "$SESSION")" -n listmode "sleep 1000")"
ait_tmux respawn-pane -k -t "$LIST_PANE" "ait frozenagent"
sleep 2
assert_eq "a list-mode pane carries no ready stamp" \
    "" "$(pane_fmt "$LIST_PANE" '#{@aitask_standin_ready}')"
assert_eq "and the viewer pane's stamp is untouched" \
    "$RECORD_ID" "$(pane_fmt "$TARGET" '#{@aitask_standin_ready}')"

echo
echo "=== Results: $PASS passed, $FAIL failed (of $TOTAL) ==="
assert_counters_load
if [ "$FAIL" -eq 0 ]; then
    echo "PASS: all $TOTAL assertions"
    exit 0
fi
echo "FAIL: $FAIL of $TOTAL assertions"
exit 1
