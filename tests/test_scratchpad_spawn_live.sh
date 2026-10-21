#!/usr/bin/env bash
# tests/test_scratchpad_spawn_live.sh — minimonitor `o` scratchpad spawn against
# a real tmux server (t2073_4).
#
# `tests/test_minimonitor_scratchpad_spawn.py` pins the spawn's decisions
# through mocks. This file answers what only a live server can:
#
#   A  the pad is stamped (target + store), absent from `discover_panes`, and the
#      agent's `pane-died` hook names the cleanup script
#   F  `launch_split_pane` returns the id of the pane tmux really created (the
#      pad's own start command and window, read back from tmux)
#   B  the agent's PROCESS exits -> `pane-died` -> the pad and the minimonitor
#      companion are gone; a control pad bound to another agent survives
#   C  freeze and restore keep the agent's pane id, and the pad stays bound to it
#   D  dropping a frozen record kills the stand-in with `kill-pane`, which fires
#      no `pane-died`: the pad is LEFT BEHIND. Asserted as the known gap that the
#      `kill_bound_helpers_on_direct_kill` follow-up closes — flip this case
#      when that lands.
#   E  the REAL editor command (no seam) opens its store at the stamped key even
#      though the tmux server's environment names a different store root —
#      E1 with an override in the driver, E2 with none. Control E0: the same
#      command WITHOUT the pinned root opens under the server's root, proving
#      the two environments really differ and the pin is what makes E1/E2 pass.
#
# Cases A-D replace exactly one seam, `monitor_core.scratchpad_command`, with a
# harmless `tail -f /dev/null`; everything below it is real — the store helper,
# the duplicate lookup, `launch_split_pane`, the stamps, the cleanup hook.
# Freeze/restore reuse the `test_restore_flows_live.sh` fixture (fake `claude`,
# the shipped SessionStart hook, the real store), with the REAL repo as the
# project root for the same reasons given there; nothing writes into the repo.
#
# TMUX-STRESS. It arms real `pane-died` hooks, so it calls
# `require_clean_ait_server` (REFUSES inside tmux or with `-L ait` alive) before
# `require_isolated_tmux`. Run it from a terminal that is NOT inside tmux.
#
# Run: bash tests/test_scratchpad_spawn_live.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

command -v tmux >/dev/null 2>&1 || { echo "SKIP: tmux not available"; exit 0; }

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
# Cases run inside ( … ) subshells; without the file-backed counters their
# PASS/FAIL increments die at subshell exit (CLAUDE.md, t1207).
assert_counters_init

# ORDER IS LOAD-BEARING (tests/lib/tmux_isolation.sh).
# shellcheck source=lib/tmux_isolation.sh
. "$PROJECT_DIR/tests/lib/tmux_isolation.sh"
require_clean_ait_server     # FIRST
require_isolated_tmux        # SECOND

# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
. "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"
PYTHON_BIN="$(require_ait_python)"

REAL_PATH="$PATH"
REAL_TMUX="$(command -v tmux)"

FIXTURE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/ait_scratch_spawn_XXXXXX")"
FIXTURE_PHYS="$(cd -P "$FIXTURE_DIR" && pwd)"
export TMUX_TMPDIR="$FIXTURE_DIR"
SESSION="ait_scratch_$$"
ROOT="$PROJECT_DIR"

export AITASKS_AGENT_SESSIONS_FILE="$FIXTURE_DIR/agent_sessions.json"
export AITASKS_FROZEN_DIR="$FIXTURE_DIR/frozen"
export AITASKS_FROZEN_STANDIN_CMD="$PROJECT_DIR/tests/lib/fake_standin.sh"
export AITASKS_TEST_MODE=1
export AITASKS_STALE_OP_GRACE=1
export AITASKS_RESTORE_ACK_GRACE=3
# Cases A-D: the driver's store root. It only feeds the `path` verb (which
# creates nothing); the seam keeps the editor itself out of these cases.
export AITASK_SCRATCHPAD_DIR="$FIXTURE_DIR/pad"

# The fake `claude` (restore) and the `ait` shim (case E), exported on PATH
# BEFORE the server starts: panes run in the SERVER's environment.
mkdir -p "$FIXTURE_DIR/bin"
AGENT_ENV_FILE="$FIXTURE_DIR/agent_env"
cat > "$FIXTURE_DIR/bin/claude" <<WRAPPER
#!/usr/bin/env bash
[ -f "$AGENT_ENV_FILE" ] && . "$AGENT_ENV_FILE"
exec "$PROJECT_DIR/tests/lib/fake_agent.sh" "\$@"
WRAPPER
# Case E's pads run `ait scratchpad` from their project root; resolve `ait` the
# way the global shim does, without depending on one being installed.
cat > "$FIXTURE_DIR/bin/ait" <<'SHIM'
#!/usr/bin/env bash
exec "$PWD/ait" "$@"
SHIM
chmod +x "$FIXTURE_DIR/bin/claude" "$FIXTURE_DIR/bin/ait"
export PATH="$FIXTURE_DIR/bin:$PATH"
export FAKE_AGENT_HOOK_LOG="$FIXTURE_DIR/hook.log"
export AITASKS_FAKE_AGENT_HOOK="$PROJECT_DIR/.aitask-scripts/aitask_session_hook.sh"
chmod +x "$PROJECT_DIR/tests/lib/fake_standin.sh" "$PROJECT_DIR/tests/lib/fake_agent.sh" 2>/dev/null || true

FAKE_AGENT="$PROJECT_DIR/tests/lib/fake_agent.sh"
FROZEN_SH="$PROJECT_DIR/.aitask-scripts/aitask_frozen.sh"
SESSIONS_SH="$PROJECT_DIR/.aitask-scripts/aitask_agent_sessions.sh"
STORE_SH="$PROJECT_DIR/.aitask-scripts/aitask_scratchpad_store.sh"

# shellcheck source=lib/frozen_fixtures.sh
. "$PROJECT_DIR/tests/lib/frozen_fixtures.sh"
trap cleanup EXIT

drop_record() { store drop "$1" >/dev/null 2>&1 || true; }

# wait_until <tries of 0.1 s> <command...> — a bounded poll, never an assertion.
wait_until() {
    local tries="$1" i=0
    shift
    until "$@"; do
        [ "$i" -ge "$tries" ] && return 1
        sleep 0.1
        i=$((i + 1))
    done
}
pane_gone() { ! pane_exists "$1"; }

DRIVER="$FIXTURE_DIR/driver.py"
cat > "$DRIVER" <<'PYEOF'
"""spawn | discover, against the isolated server. Env-driven; see the callers."""
import os
import sys
from pathlib import Path

from monitor import monitor_core as mc
from monitor.monitor_core import TmuxMonitor

mon = TmuxMonitor(session=os.environ["AIT_SESSION"], multi_session=False,
                  exclude_pane="")
if sys.argv[1] == "discover":
    print(" ".join(p.pane_id for p in mon.discover_panes()))
    sys.exit(0)
if os.environ.get("AIT_SEAM") == "1":
    mc.scratchpad_command = lambda *a, **k: "tail -f /dev/null"
notes = []
pad = mc.spawn_scratchpad(
    mon,
    followed_pane=os.environ["AIT_AGENT"],
    followed_window=os.environ["AIT_WINDOW"],
    session=os.environ["AIT_SESSION"],
    task_id=os.environ.get("AIT_TASK") or None,
    target_root=Path(os.environ["AIT_ROOT"]),
    companion_pane=os.environ.get("AIT_COMPANION") or None,
    select_window=False,
    notify=lambda msg, **kw: notes.append(msg),
    schedule_refresh=lambda: None,
)
for note in notes:
    print(f"NOTE:{note}", file=sys.stderr)
print(f"PAD:{pad or ''}")
PYEOF

# PAD_DIR_UNSET=1 runs the driver with AITASK_SCRATCHPAD_DIR removed (case E2).
py() {
    local unset_args=()
    [ "${PAD_DIR_UNSET:-0}" = 1 ] && unset_args=(-u AITASK_SCRATCHPAD_DIR)
    env "${unset_args[@]}" \
        PYTHONPATH="$PROJECT_DIR/.aitask-scripts:$PROJECT_DIR/.aitask-scripts/lib" \
        AITASKS_TMUX_SOCKET="" TMUX_TMPDIR="$FIXTURE_DIR" "$PYTHON_BIN" "$DRIVER" "$@"
}

# spawn <agent> <window> <task|""> <root> <companion|""> <seam 0|1> -> pad id
spawn() {
    local out
    out="$(AIT_SESSION="$SESSION" AIT_AGENT="$1" AIT_WINDOW="$2" AIT_TASK="$3" \
        AIT_ROOT="$4" AIT_COMPANION="$5" AIT_SEAM="$6" py spawn 2>"$FIXTURE_DIR/spawn.err")"
    out="$(sed -n 's/^PAD://p' <<<"$out")"
    [ -n "$out" ] || sed 's/^/    spawn: /' "$FIXTURE_DIR/spawn.err" >&2
    printf '%s\n' "$out"
}

# A live agent window with its record seeded for a RESUME (restore needs the
# session id), WITHOUT freezing it — the pad must be bound to the live agent
# first. Echoes "<record_id> <agent_pane> <companion_pane>".
make_live_agent() {
    local window="$1" agent companion rid pane_pid seeded
    read -r agent companion < <(make_agent_window "$SESSION" "$window" "$ROOT")
    rid="$(wait_for_record_stamp "$agent")" || {
        echo "FAIL: no @aitask_record stamp on $agent" >&2; return 1; }
    pane_pid="$(pane_fmt "$agent" '#{pane_pid}')"
    seeded="$(store upsert --root "$ROOT" --window "$window" \
        --pane "$agent" --pane-pid "$pane_pid" --session "$SESSION" \
        --session-id "sess-$window" --agent-string "claudecode/opus5" \
        --operation pick --task-id 1705 2>/dev/null)"
    [ "${seeded##*$'\n'}" = "UPSERTED:$rid|updated" ] || {
        echo "FAIL: seed did not update $rid (got '$seeded')" >&2; return 1; }
    printf '%s %s %s\n' "$rid" "$agent" "$companion"
}

key_for() {  # key_for <root> <task> [<AITASK_SCRATCHPAD_DIR>|""]
    (cd "$1" && if [ -n "${3:-}" ]; then AITASK_SCRATCHPAD_DIR="$3" "$STORE_SH" path "$2"
              else env -u AITASK_SCRATCHPAD_DIR "$STORE_SH" path "$2"; fi)
}

tm new-session -d -s "$SESSION" -n scratch -c "$ROOT" "sleep 1000"
sleep 0.4

# ---------------------------------------------------------------------------
section "Case A + F — stamped, out of discovery, hook armed, real pane id"
# ---------------------------------------------------------------------------
(
    read -r AGENT COMPANION < <(make_agent_window "$SESSION" "agent-pick-2101" "$ROOT")
    sleep 0.3
    PAD="$(spawn "$AGENT" "agent-pick-2101" 2101 "$ROOT" "$COMPANION" 1)"
    if [ -n "$PAD" ]; then assert_record_pass; else
        assert_record_fail; echo "FAIL: A: no pad was opened"; exit 1
    fi
    assert_eq "A: target stamped" "$AGENT" "$(pane_fmt "$PAD" '#{@aitask_scratchpad_target}')"
    assert_eq "A: store stamped with the helper's key" "$(key_for "$ROOT" 2101 "$AITASK_SCRATCHPAD_DIR")" \
        "$(pane_fmt "$PAD" '#{@aitask_scratchpad_store}')"
    seen="$(AIT_SESSION="$SESSION" py discover)"
    assert_contains "A: the agent is discovered" "$AGENT" "$seen"
    case " $seen " in
        *" $PAD "*) assert_record_fail; echo "FAIL: A: the pad was discovered as an agent" ;;
        *) assert_record_pass ;;
    esac
    assert_contains "A: the agent's pane-died hook runs the cleanup script" \
        "aitask_companion_cleanup.sh" "$(tm show-hooks -p -t "$AGENT" pane-died 2>/dev/null)"
    # F: the returned id IS the pane tmux created for this launch.
    assert_contains "F: the pad's start command is the launched one" "tail -f /dev/null" \
        "$(pane_fmt "$PAD" '#{pane_start_command}')"
    assert_eq "F: the pad sits in the agent's window" "$(pane_fmt "$AGENT" '#{window_id}')" \
        "$(pane_fmt "$PAD" '#{window_id}')"
    # A second press is refused while the pad lives.
    assert_eq "A: a second press opens nothing" "" \
        "$(spawn "$AGENT" "agent-pick-2101" 2101 "$ROOT" "$COMPANION" 1 2>/dev/null)"
)

# ---------------------------------------------------------------------------
section "Case B — the agent exits: pad and companion go, a control pad stays"
# ---------------------------------------------------------------------------
(
    read -r AGENT COMPANION < <(make_agent_window "$SESSION" "agent-pick-2102" "$ROOT")
    read -r CTRL_AGENT CTRL_COMP < <(make_agent_window "$SESSION" "agent-pick-2103" "$ROOT")
    sleep 0.3
    PAD="$(spawn "$AGENT" "agent-pick-2102" 2102 "$ROOT" "$COMPANION" 1)"
    CTRL_PAD="$(spawn "$CTRL_AGENT" "agent-pick-2103" 2103 "$ROOT" "$CTRL_COMP" 1)"
    [ -n "$PAD" ] && [ -n "$CTRL_PAD" ] || { assert_record_fail; echo "FAIL: B: setup"; exit 1; }

    kill "$(pane_fmt "$AGENT" '#{pane_pid}')"
    if wait_until 80 pane_gone "$PAD"; then assert_record_pass; else
        assert_record_fail; echo "FAIL: B: the pad outlived its agent"
    fi
    if wait_until 80 pane_gone "$COMPANION"; then assert_record_pass; else
        assert_record_fail; echo "FAIL: B: the minimonitor companion was not despawned"
    fi
    if pane_exists "$CTRL_PAD"; then assert_record_pass; else
        assert_record_fail; echo "FAIL: B: a pad bound to ANOTHER agent was killed"
    fi
    assert_eq "B: the control pad is still bound" "$CTRL_AGENT" \
        "$(pane_fmt "$CTRL_PAD" '#{@aitask_scratchpad_target}')"
)

# ---------------------------------------------------------------------------
section "Case C — freeze and restore keep the pad bound to the same pane id"
# ---------------------------------------------------------------------------
(
    read -r RID AGENT COMPANION < <(make_live_agent "agent-pick-2104") || { assert_record_fail; exit 1; }
    PAD="$(spawn "$AGENT" "agent-pick-2104" 2104 "$ROOT" "$COMPANION" 1)"
    [ -n "$PAD" ] || { assert_record_fail; echo "FAIL: C: no pad"; drop_record "$RID"; exit 1; }

    out="$("$FROZEN_SH" freeze "$AGENT" 2>&1)"
    assert_contains "C: freeze reports FROZEN" "FROZEN:$RID" "$out"
    assert_eq "C: the agent pane id survives the freeze" "$AGENT" "$(pane_fmt "$AGENT" '#{pane_id}')"
    if pane_exists "$PAD"; then assert_record_pass; else
        assert_record_fail; echo "FAIL: C: the pad died with the freeze"
    fi
    assert_eq "C: the pad is still bound after the freeze" "$AGENT" \
        "$(pane_fmt "$PAD" '#{@aitask_scratchpad_target}')"

    wait_for_ready "$AGENT" "$RID"
    out="$("$FROZEN_SH" restore "$RID" 2>&1)"
    assert_contains "C: restore reports RESTORED" "RESTORED:$RID" "$out"
    assert_eq "C: the agent pane id survives the restore" "$AGENT" "$(pane_fmt "$AGENT" '#{pane_id}')"
    if pane_exists "$PAD"; then assert_record_pass; else
        assert_record_fail; echo "FAIL: C: the pad died with the restore"
    fi
    assert_eq "C: the pad is still bound after the restore" "$AGENT" \
        "$(pane_fmt "$PAD" '#{@aitask_scratchpad_target}')"
    drop_record "$RID"
)

# ---------------------------------------------------------------------------
section "Case D — KNOWN GAP: a frozen-record drop leaves the pad behind"
# ---------------------------------------------------------------------------
(
    read -r RID AGENT COMPANION < <(make_live_agent "agent-pick-2105") || { assert_record_fail; exit 1; }
    # A real sibling agent keeps the window, so the drop takes the `kill-pane`
    # branch — the direct kill that fires no `pane-died`.
    SIBLING="$(tm split-window -d -t "$AGENT" -c "$ROOT" -P -F '#{pane_id}' "sleep 1000")"
    PAD="$(spawn "$AGENT" "agent-pick-2105" 2105 "$ROOT" "$COMPANION" 1)"
    [ -n "$PAD" ] || { assert_record_fail; echo "FAIL: D: no pad"; drop_record "$RID"; exit 1; }
    out="$("$FROZEN_SH" freeze "$AGENT" 2>&1)"
    assert_contains "D: freeze reports FROZEN" "FROZEN:$RID" "$out"

    out="$("$FROZEN_SH" drop "$RID" 2>&1)"
    assert_contains "D: drop reports DROPPED" "DROPPED:$RID" "$out"
    if wait_until 20 pane_gone "$AGENT"; then assert_record_pass; else
        assert_record_fail; echo "FAIL: D: the stand-in was not killed"
    fi
    if pane_exists "$SIBLING"; then assert_record_pass; else
        assert_record_fail; echo "FAIL: D: the sibling agent was killed"
    fi
    # THE GAP: no pane-died fired, so nothing killed the bound pad. When
    # kill_bound_helpers_on_direct_kill lands, this assertion flips.
    sleep 0.5
    if pane_exists "$PAD"; then assert_record_pass; else
        assert_record_fail
        echo "FAIL: D: the pad is gone — if the direct-kill follow-up landed, flip this case"
    fi
)

# ---------------------------------------------------------------------------
section "Case E — the real editor opens the stamped store whatever the server env"
# ---------------------------------------------------------------------------
ROOT_E="$FIXTURE_DIR/proj_e"
mkdir -p "$ROOT_E/aitasks/metadata"
: > "$ROOT_E/aitasks/metadata/project_config.yaml"
printf -- '---\nstatus: Implementing\n---\n' > "$ROOT_E/aitasks/t9001_fixture.md"
ln -s "$PROJECT_DIR/ait" "$ROOT_E/ait"
ln -s "$PROJECT_DIR/.aitask-scripts" "$ROOT_E/.aitask-scripts"
ROOT_E_PHYS="$(cd -P "$ROOT_E" && pwd)"
SERVER_PAD="$FIXTURE_DIR/server_pad"
# The pads' environment: the server's GLOBAL env, which differs from the driver's.
tm set-environment -g AITASK_SCRATCHPAD_DIR "$SERVER_PAD"

holder_at() { [ -e "$1/.holder.lock" ]; }

(
    AGENT_E="$(tm new-window -d -t "=$SESSION" -n agent-pick-9001 -c "$ROOT_E" \
        -P -F '#{pane_id}' "sleep 1000")"
    sleep 0.3

    # E0 — CONTROL: the same command without the pinned root follows the server.
    CTRL="$(tm split-window -d -t "$AGENT_E" -c "$ROOT_E" -P -F '#{pane_id}' \
        "ait scratchpad --task 9001 --target $AGENT_E")"
    if wait_until 150 holder_at "$SERVER_PAD/9001"; then assert_record_pass; else
        assert_record_fail
        echo "FAIL: E0: the unpinned editor did not open under the server's root —"
        echo "      the environments may not differ, or the editor did not start:"
        tm capture-pane -p -t "$CTRL" 2>/dev/null | sed 's/^/      /' | tail -15
    fi
    tm kill-pane -t "$CTRL" 2>/dev/null
    wait_until 30 pane_gone "$CTRL"
    rm -rf "$SERVER_PAD"

    # E1 — an override in the driver only.
    PAD="$(AITASK_SCRATCHPAD_DIR="$FIXTURE_DIR/driver_pad" \
        spawn "$AGENT_E" agent-pick-9001 9001 "$ROOT_E" "" 0)"
    stamped="$(pane_fmt "$PAD" '#{@aitask_scratchpad_store}')"
    assert_eq "E1: the stamp is the driver's root" "$FIXTURE_PHYS/driver_pad/9001" "$stamped"
    if [ -n "$stamped" ] && wait_until 150 holder_at "$stamped"; then assert_record_pass; else
        assert_record_fail; echo "FAIL: E1: the editor did not open the stamped store"
        tm capture-pane -p -t "$PAD" 2>/dev/null | sed 's/^/      /' | tail -15
    fi
    if [ ! -e "$SERVER_PAD/9001" ]; then assert_record_pass; else
        assert_record_fail; echo "FAIL: E1: the editor opened the SERVER's store"
    fi
    tm kill-pane -t "$PAD" 2>/dev/null
    wait_until 30 pane_gone "$PAD"

    # E2 — no override anywhere but the server: the default root is pinned.
    PAD="$(PAD_DIR_UNSET=1 spawn "$AGENT_E" agent-pick-9001 9001 "$ROOT_E" "" 0)"
    stamped="$(pane_fmt "$PAD" '#{@aitask_scratchpad_store}')"
    assert_eq "E2: the stamp is the project's default root" \
        "$ROOT_E_PHYS/.aitask-scratchpad/9001" "$stamped"
    if [ -n "$stamped" ] && wait_until 150 holder_at "$stamped"; then assert_record_pass; else
        assert_record_fail; echo "FAIL: E2: the editor did not open the stamped store"
        tm capture-pane -p -t "$PAD" 2>/dev/null | sed 's/^/      /' | tail -15
    fi
    if [ ! -e "$SERVER_PAD/9001" ]; then assert_record_pass; else
        assert_record_fail; echo "FAIL: E2: the editor opened the SERVER's store"
    fi
    tm kill-pane -t "$PAD" 2>/dev/null
)

echo ""
echo "=== Summary ==="
assert_counters_load
echo "Passed: $PASS / $TOTAL"
if [[ "$FAIL" -eq 0 ]]; then echo "ALL TESTS PASSED"; else echo "SOME TESTS FAILED ($FAIL)"; fi
[[ "$FAIL" -eq 0 ]]
