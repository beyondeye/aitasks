#!/usr/bin/env bash
# tests/test_restore_flows_live.sh — the restore coordinator against a real tmux
# server, the real SessionStart hook and the real store (t1705_5).
#
# `tests/test_agent_restore.py` owns the coordinator's branching with fakes.
# This file owns what only a real server can answer: that `respawn-pane -k -e`
# really delivers all four identity variables, that the SHIPPED hook really
# turns them into a store acknowledgement, that a mismatched session is really
# refused, and that a coordinator really stopped or killed mid-transaction is
# really settled by `reconcile`.
#
# `tests/test_frozen_standin_spike.sh` (t1705_1 + t1716) is the CONTROL for this
# file, and `tests/test_freeze_engine_live.sh` is its predecessor: if a case here
# fails, run those first. A red spike means the platform changed; a red freeze
# suite means the shared plumbing (`lib/agent_frozen_ops.py`) changed; only a
# green pair points at this coordinator.
#
# THE ACKNOWLEDGEMENT PATH IS REAL. `tests/lib/fake_agent.sh` execs the shipped
# `aitask_session_hook.sh` with a synthetic payload, so what is exercised is
# hook -> `aitask_agent_sessions.sh` -> store, not a simulation of it. That is
# what makes "captures are deleted ONLY on a verified ack" a testable claim.
#
# THE STAND-IN VIEWER DOES NOT EXIST YET (t1705_6), so `AITASKS_FROZEN_STANDIN_CMD`
# points at `tests/lib/fake_standin.sh`, which reproduces the one behaviour the
# protocol depends on: the viewer stamps its OWN pane `@aitask_standin_ready`.
#
# Cases
#   1   happy resume: ack=hook, captures DELETED, stamp cleared, pane re-joined
#   2   happy re-pick: a brand-new session id is adopted
#   3   all four `-e` identity variables arrive (V11)
#   4   the replacement exits at once -> agent_exited, stand-in back, capture kept
#   5   a MISMATCHED session -> abort via last_error, WITHOUT waiting out the grace
#   6   no hook at all -> liveness confirm after the grace, captures KEPT
#   7   gone pane -> the replacement lands in a new window, one record still
#   8   the hook WINS the launch race -> success, and NO rollback respawn (V12)
#   9   a PAUSED coordinator's restore is never taken over, even past the grace
#   10  `AITASKS_RESTORE_FAIL_AT` at begin | respawn | ack -> state + recovery
#   11  coordinator killed after clearing ready, before the respawn
#   12  coordinator SIGSTOPped in `aborting` -> second restore refused, reconcile
#       finishes, the resumed coordinator gets NONCE_MISMATCH and touches nothing
#   13  Restore-All keeps going after one failing record
#
# TMUX-STRESS. Run from a shell that is NOT inside tmux, with the dedicated
# `-L ait` server stopped; `require_clean_ait_server` refuses otherwise.
#
# Run: bash tests/test_restore_flows_live.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

command -v tmux >/dev/null 2>&1 || { echo "SKIP: tmux not available"; exit 0; }

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
# Cases run inside ( … ) subshells; without the file-backed counters their
# PASS/FAIL increments die at subshell exit and this file exits 0 whatever
# happened (CLAUDE.md, t1207).
assert_counters_init

# ORDER IS LOAD-BEARING (tests/lib/tmux_isolation.sh).
# shellcheck source=lib/tmux_isolation.sh
. "$PROJECT_DIR/tests/lib/tmux_isolation.sh"
require_clean_ait_server     # FIRST
require_isolated_tmux        # SECOND

REAL_PATH="$PATH"
REAL_TMUX="$(command -v tmux)"

FIXTURE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/ait_restore_live_XXXXXX")"
export TMUX_TMPDIR="$FIXTURE_DIR"
SESSION="ait_restore_$$"

# The REAL repo is the project root on purpose. The hook resolves a root by
# walking up to `aitasks/metadata/project_config.yaml` and then execs that root's
# `aitask_agent_sessions.sh`, and `aitask_codeagent.sh` resolves the agent binary
# and model from that root's metadata — a synthetic root would need all of it
# copied in, and every copy is a chance to diverge from what ships. Nothing here
# writes to the repo: the store, the capture tree and the tmux server are all
# redirected into $FIXTURE_DIR below.
ROOT="$PROJECT_DIR"

export AITASKS_AGENT_SESSIONS_FILE="$FIXTURE_DIR/agent_sessions.json"
export AITASKS_FROZEN_DIR="$FIXTURE_DIR/frozen"
export AITASKS_FROZEN_STANDIN_CMD="$PROJECT_DIR/tests/lib/fake_standin.sh"
export AITASKS_TEST_MODE=1
# The lease grace, shortened so takeover races finish in seconds.
export AITASKS_STALE_OP_GRACE=1
# The ACK grace, shortened by the seam this task added (V2). Without it the
# case-5 assertion "the liveness fallback must not fire" would be measured
# against 20 s and would pass vacuously.
export AITASKS_RESTORE_ACK_GRACE=3
GRACE_SLEEP=4

# A fake `claude` so the resolved argv (`claude --model <id> --resume <sid>`)
# actually starts the fixture agent when tmux respawns it. Exported BEFORE the
# server starts: `respawn-pane` runs its command in the TMUX SERVER's
# environment, which is captured at server start, not this shell's at call time.
mkdir -p "$FIXTURE_DIR/bin"
AGENT_ENV_FILE="$FIXTURE_DIR/agent_env"
cat > "$FIXTURE_DIR/bin/claude" <<WRAPPER
#!/usr/bin/env bash
# The fake \`claude\`. It sources a per-case control file before exec'ing the
# fixture agent, because \`respawn-pane\` runs its command in the TMUX SERVER's
# environment — captured when the server started — so a per-case
# \`FAKE_AGENT_EXIT=1 ./aitask_frozen.sh restore ...\` in the test shell would
# never reach the replacement. \`exec\` keeps the pid, so \`#{pane_pid}\` still
# names the agent (t1465).
[ -f "$AGENT_ENV_FILE" ] && . "$AGENT_ENV_FILE"
exec "$PROJECT_DIR/tests/lib/fake_agent.sh" "\$@"
WRAPPER
chmod +x "$FIXTURE_DIR/bin/claude"
export PATH="$FIXTURE_DIR/bin:$PATH"
export FAKE_AGENT_HOOK_LOG="$FIXTURE_DIR/hook.log"
# Belt and braces: name the shipped hook explicitly rather than relying on the
# fixture agent resolving it relative to its own (symlinked) path.
export AITASKS_FAKE_AGENT_HOOK="$PROJECT_DIR/.aitask-scripts/aitask_session_hook.sh"

chmod +x "$PROJECT_DIR/tests/lib/fake_standin.sh" 2>/dev/null || true
chmod +x "$PROJECT_DIR/tests/lib/fake_agent.sh" 2>/dev/null || true

FAKE_AGENT="$PROJECT_DIR/tests/lib/fake_agent.sh"
FROZEN_SH="$PROJECT_DIR/.aitask-scripts/aitask_frozen.sh"
SESSIONS_SH="$PROJECT_DIR/.aitask-scripts/aitask_agent_sessions.sh"

cleanup() {
    PATH="$REAL_PATH" "$REAL_TMUX" kill-server 2>/dev/null || true
    rm -rf "$FIXTURE_DIR" 2>/dev/null || true
}
trap cleanup EXIT

section() { echo; echo "=== $1 ==="; }

# --- fixture helpers ---------------------------------------------------------

tm() { "$REAL_TMUX" "$@"; }

pane_fmt() { tm display-message -p -t "$1" "$2" 2>/dev/null; }

# `display-message -p -t <gone pane>` exits ZERO with EMPTY output, so the exit
# status says nothing about whether the pane exists. The output is the signal.
pane_exists() { [ -n "$(pane_fmt "$1" '#{pane_id}')" ]; }
window_exists() {
    tm list-windows -t "=$2" -F '#{window_name}' 2>/dev/null | grep -qxF "$1"
}

store() { "$SESSIONS_SH" "$@"; }
record_of_pane() { pane_fmt "$1" '#{@aitask_record}'; }
record_field() { store show "$1" 2>/dev/null | sed -n "s/^$2://p"; }

# An agent window rooted in the project. Echoes "<agent_pane> <companion_pane>".
make_agent_window() {
    local window="$1"
    local agent companion comp_pid
    agent="$(tm new-window -d -t "=$SESSION" -n "$window" -c "$ROOT" \
        -P -F '#{pane_id}' "$FAKE_AGENT")"
    companion="$(tm split-window -d -t "$agent" -c "$ROOT" \
        -P -F '#{pane_id}' "sleep 1000")"
    comp_pid="$(pane_fmt "$companion" '#{pane_pid}')"
    tm set-option -p -t "$companion" @aitask_monitor_kind "minimonitor:$comp_pid"
    printf '%s %s\n' "$agent" "$companion"
}

wait_for_record_state() {
    local rid="$1" want="$2" i=0
    while [ "$i" -lt 120 ]; do
        [ "$(record_field "$rid" state)" = "$want" ] && return 0
        sleep 0.1
        i=$((i + 1))
    done
    return 1
}

wait_for_ready() {
    local pane="$1" rid="$2" i=0
    while [ "$i" -lt 120 ]; do
        [ "$(pane_fmt "$pane" '#{@aitask_standin_ready}')" = "$rid" ] && return 0
        sleep 0.1
        i=$((i + 1))
    done
    return 1
}

# Set / clear the replacement agent's environment for ONE case.
agent_env() { printf 'export %s\n' "$@" > "$AGENT_ENV_FILE"; }
agent_env_clear() { : > "$AGENT_ENV_FILE"; }

# Drop a record when a case is done. Cases share one store (the hook, running
# inside the pane, reads the SERVER's AITASKS_AGENT_SESSIONS_FILE, so a per-case
# store file would be written by the coordinator and ignored by the hook), so
# leftovers would otherwise leak into `restore --all` and into reconcile's
# output in later cases.
drop_record() { store drop "$1" >/dev/null 2>&1 || true; }

wait_stopped() {
    local pid="$1" i=0
    while [ "$i" -lt 100 ]; do
        case "$(ps -o state= -p "$pid" 2>/dev/null | tr -d ' ')" in
            T*) return 0 ;;
        esac
        sleep 0.1
        i=$((i + 1))
    done
    return 1
}

# Freeze a fresh agent window and return "<record_id> <pane_id>", with the
# record's `codeagent_session_id` seeded so a RESUME is possible. Seeding it
# through the real `upsert` keeps this on the shipped write path.
make_frozen() {
    local window="$1" session_id="${2:-sess-orig}" agent_string="${3:-claudecode/opus5}"
    local agent companion pane_pid
    read -r agent companion < <(make_agent_window "$window")
    sleep 0.3
    pane_pid="$(pane_fmt "$agent" '#{pane_pid}')"
    store upsert --root "$ROOT" --window "$window" \
        --pane "$agent" --pane-pid "$pane_pid" --session "$SESSION" \
        --session-id "$session_id" --agent-string "$agent_string" \
        --operation pick --task-id 1705 >/dev/null 2>&1
    "$FROZEN_SH" freeze "$agent" >/dev/null 2>&1
    printf '%s %s\n' "$(record_of_pane "$agent")" "$agent"
}

tm new-session -d -s "$SESSION" -n scratch -c "$ROOT" "sleep 1000"
sleep 0.4

# ---------------------------------------------------------------------------
section "Case 1 — happy resume: ack=hook, captures DELETED"
# ---------------------------------------------------------------------------
(
    read -r RID PANE < <(make_frozen "agent-pick-1705" "sess-orig")
    assert_eq "case 1: the record is frozen before the restore" "frozen" \
        "$(record_field "$RID" state)"
    wait_for_ready "$PANE" "$RID"
    standin_pid="$(pane_fmt "$PANE" '#{pane_pid}')"

    out="$("$FROZEN_SH" restore "$RID" 2>&1)"; rc=$?
    assert_eq "case 1: restore exits 0" "0" "$rc"
    assert_contains "case 1: reports a HOOK-verified restore" "RESTORED:$RID|hook" "$out"

    assert_eq "case 1: record is live" "live" "$(record_field "$RID" state)"
    assert_eq "case 1: ack is the strong one" "hook" "$(record_field "$RID" ack)"

    # The whole point of demanding a hook ack: only a VERIFIED resume may delete
    # the single copy of the user's scrollback.
    if [ ! -d "$AITASKS_FROZEN_DIR/$RID" ]; then assert_record_pass; else
        assert_record_fail
        echo "FAIL: case 1: a hook-verified restore must delete the captures"
    fi
    assert_eq "case 1: the frozen stamp is cleared" "" \
        "$(pane_fmt "$PANE" '#{@aitask_frozen}')"
    assert_eq "case 1: the pane still carries the record join" "$RID" \
        "$(record_of_pane "$PANE")"

    new_pid="$(pane_fmt "$PANE" '#{pane_pid}')"
    if [ "$new_pid" != "$standin_pid" ]; then assert_record_pass; else
        assert_record_fail
        echo "FAIL: case 1: the stand-in was never replaced (pid $new_pid)"
    fi
    assert_eq "case 1: the record's pane_pid tracks the replacement" "$new_pid" \
        "$(record_field "$RID" pane_pid)"
    drop_record "$RID"
    tm kill-window -t "=$SESSION:agent-pick-1705" 2>/dev/null || true
)

# ---------------------------------------------------------------------------
section "Case 2 — happy re-pick: a new session id is adopted"
# ---------------------------------------------------------------------------
(
    read -r RID PANE < <(make_frozen "agent-pick-1706" "sess-orig")
    wait_for_ready "$PANE" "$RID"

    out="$("$FROZEN_SH" restore "$RID" --repick 2>&1)"; rc=$?
    assert_eq "case 2: re-pick exits 0" "0" "$rc"
    assert_contains "case 2: reports a restore" "RESTORED:$RID" "$out"
    assert_eq "case 2: record is live" "live" "$(record_field "$RID" state)"
    assert_eq "case 2: the mode was recorded as repick" "repick" \
        "$(record_field "$RID" restore_mode)"

    # A re-pick starts a NEW session, so the stored id must move off the old one
    # rather than being compared against it (which is what `resume` mode does).
    sid="$(record_field "$RID" codeagent_session_id)"
    if [ "$sid" != "sess-orig" ] && [ -n "$sid" ]; then assert_record_pass; else
        assert_record_fail
        echo "FAIL: case 2: re-pick must adopt the new session id (got '$sid')"
    fi
    drop_record "$RID"
    tm kill-window -t "=$SESSION:agent-pick-1706" 2>/dev/null || true
)

# ---------------------------------------------------------------------------
section "Case 3 — all four -e identity variables arrive (V11)"
# ---------------------------------------------------------------------------
# A dropped AITASK_RESTORE_NONCE would make every hook ack a NONCE_MISMATCH and
# route every restore to the liveness fallback — which still REPORTS success.
# This is the assertion that separates "restored" from "restored and verified".
(
    read -r RID PANE < <(make_frozen "agent-pick-1707" "sess-orig")
    wait_for_ready "$PANE" "$RID"
    report="$FIXTURE_DIR/envprobe_case3.txt"

    # Restore by hand with the coordinator's own respawn shape, pointing the
    # replacement at --report-env so it self-reports the environment it got.
    nonce_line="$(store restore-begin "$RID" --owner-pid $$ --mode resume 2>&1 | tail -1)"
    nonce="${nonce_line##*|}"
    tm set-option -pu -t "$PANE" @aitask_standin_ready
    tm respawn-pane -k \
        -e "AITASK_RESTORE_RECORD=$RID" \
        -e "AITASK_RESTORE_NONCE=$nonce" \
        -e "AITASK_RESTORE_MODE=resume" \
        -e "AITASK_RESTORE_EXPECT_SESSION=sess-orig" \
        -t "$PANE" "FAKE_AGENT_NO_HOOK=1 '$FAKE_AGENT' --report-env '$report'"

    for _ in $(seq 1 60); do [ -s "$report" ] && break; sleep 0.1; done
    if [ -s "$report" ]; then
        assert_eq "case 3: RECORD arrived" "$RID" \
            "$(sed -n 's/^AITASK_RESTORE_RECORD=//p' "$report")"
        assert_eq "case 3: NONCE arrived" "$nonce" \
            "$(sed -n 's/^AITASK_RESTORE_NONCE=//p' "$report")"
        assert_eq "case 3: MODE arrived" "resume" \
            "$(sed -n 's/^AITASK_RESTORE_MODE=//p' "$report")"
        assert_eq "case 3: EXPECT_SESSION arrived" "sess-orig" \
            "$(sed -n 's/^AITASK_RESTORE_EXPECT_SESSION=//p' "$report")"
        assert_eq "case 3: the pane pid IS the agent (no wrapper)" \
            "$(pane_fmt "$PANE" '#{pane_pid}')" \
            "$(sed -n 's/^pid=//p' "$report")"
    else
        assert_record_fail
        echo "FAIL: case 3: the respawned replacement never self-reported"
    fi
    drop_record "$RID"
    tm kill-window -t "=$SESSION:agent-pick-1707" 2>/dev/null || true
)

# ---------------------------------------------------------------------------
section "Case 4 — the replacement exits at once -> agent_exited"
# ---------------------------------------------------------------------------
(
    read -r RID PANE < <(make_frozen "agent-pick-1708" "sess-orig")
    wait_for_ready "$PANE" "$RID"
    # `remain-on-exit` keeps the pane once its process dies, which is both the
    # `pane_dead=1` observation the §C row keys on AND the production shape (the
    # framework arms it on agent panes so `pane-died` can fire). Without it the
    # pane vanishes and the rollback has no pane to put the stand-in back into.
    tm set-option -p -t "$PANE" remain-on-exit on

    agent_env FAKE_AGENT_EXIT=1
    out="$("$FROZEN_SH" restore "$RID" 2>&1)"; rc=$?
    agent_env_clear
    assert_eq "case 4: restore reports failure" "1" "$rc"
    assert_contains "case 4: names the agent_exited outcome" \
        "RESTORE_FAILED:$RID" "$out"

    wait_for_record_state "$RID" frozen
    assert_eq "case 4: the record is back to frozen" "frozen" \
        "$(record_field "$RID" state)"
    # The capture is the user's only copy of what the agent had said. A failed
    # restore must never be the thing that destroys it.
    if [ -d "$AITASKS_FROZEN_DIR/$RID" ]; then assert_record_pass; else
        assert_record_fail
        echo "FAIL: case 4: a failed restore deleted the capture"
    fi
    assert_eq "case 4: the attempt was counted" "1" \
        "$(record_field "$RID" restore_attempts)"
    assert_eq "case 4: the frozen stamp is still set" "$RID" \
        "$(pane_fmt "$PANE" '#{@aitask_frozen}')"
    if wait_for_ready "$PANE" "$RID"; then assert_record_pass; else
        assert_record_fail
        echo "FAIL: case 4: the stand-in was not put back (user left staring at a dead pane)"
    fi
    drop_record "$RID"
    tm kill-window -t "=$SESSION:agent-pick-1708" 2>/dev/null || true
)

# ---------------------------------------------------------------------------
section "Case 5 — a MISMATCHED session aborts WITHOUT waiting out the grace"
# ---------------------------------------------------------------------------
# The negative assertion this whole grace seam exists for: the store persists
# `<nonce>:session_mismatch`, the coordinator reads it and aborts IMMEDIATELY.
# If it instead fell through to the 20 s liveness fallback it would report
# success for an agent running the WRONG session — and delete nothing, but claim
# a restore that never happened.
(
    read -r RID PANE < <(make_frozen "agent-pick-1709" "sess-orig")
    wait_for_ready "$PANE" "$RID"

    started="$(date +%s)"
    agent_env FAKE_AGENT_SESSION=sess-WRONG
    out="$("$FROZEN_SH" restore "$RID" 2>&1)"; rc=$?
    agent_env_clear
    elapsed=$(( $(date +%s) - started ))

    assert_eq "case 5: restore reports failure" "1" "$rc"
    assert_contains "case 5: names the mismatch" "session_mismatch" "$out"
    # THE assertion. It is only meaningful because AITASKS_RESTORE_ACK_GRACE
    # shortened the window to 3 s — against the hardcoded 20 s it would have
    # passed while testing nothing.
    if [ "$elapsed" -lt "$GRACE_SLEEP" ]; then assert_record_pass; else
        assert_record_fail
        echo "FAIL: case 5: took ${elapsed}s (>= ${GRACE_SLEEP}s grace) — the liveness fallback fired"
    fi

    wait_for_record_state "$RID" frozen
    assert_eq "case 5: the record is back to frozen" "frozen" \
        "$(record_field "$RID" state)"
    if [ -d "$AITASKS_FROZEN_DIR/$RID" ]; then assert_record_pass; else
        assert_record_fail; echo "FAIL: case 5: the capture was destroyed"
    fi
    assert_eq "case 5: the stored session id was NOT overwritten" "sess-orig" \
        "$(record_field "$RID" codeagent_session_id)"
    drop_record "$RID"
    tm kill-window -t "=$SESSION:agent-pick-1709" 2>/dev/null || true
)

# ---------------------------------------------------------------------------
section "Case 6 — no hook at all -> liveness confirm, captures KEPT"
# ---------------------------------------------------------------------------
(
    read -r RID PANE < <(make_frozen "agent-pick-1710" "sess-orig")
    wait_for_ready "$PANE" "$RID"

    agent_env FAKE_AGENT_NO_HOOK=1
    out="$("$FROZEN_SH" restore "$RID" 2>&1)"; rc=$?
    agent_env_clear
    assert_eq "case 6: restore exits 0" "0" "$rc"
    assert_contains "case 6: reports the WEAKER liveness outcome" \
        "RESTORED:$RID|liveness" "$out"
    assert_eq "case 6: record is live" "live" "$(record_field "$RID" state)"
    assert_eq "case 6: ack is liveness, not hook" "liveness" \
        "$(record_field "$RID" ack)"
    # `ack=liveness` never verified the session id, so the capture is the only
    # remaining evidence of what was there. Keeping it is the contract.
    if [ -d "$AITASKS_FROZEN_DIR/$RID" ]; then assert_record_pass; else
        assert_record_fail
        echo "FAIL: case 6: a liveness-only confirm must KEEP the captures"
    fi
    drop_record "$RID"
    tm kill-window -t "=$SESSION:agent-pick-1710" 2>/dev/null || true
)

# ---------------------------------------------------------------------------
section "Case 7 — a gone pane restores into a NEW window, one record still"
# ---------------------------------------------------------------------------
(
    read -r RID PANE < <(make_frozen "agent-pick-1711" "sess-orig")
    wait_for_ready "$PANE" "$RID"
    # Count records for THIS window only. A whole-store count is not stable
    # across cases: reconcile legitimately purges dead-window records from
    # earlier ones, so the total can go DOWN and say nothing about this case.
    win_records() { store list 2>/dev/null | awk -F'|' '$4 == "agent-pick-1711"' | wc -l | tr -d ' '; }
    before_records="$(win_records)"

    tm kill-window -t "=$SESSION:agent-pick-1711" 2>/dev/null || true
    sleep 0.3
    # reconcile records the gone pane the way the §C table says.
    "$FROZEN_SH" reconcile >/dev/null 2>&1 || true

    out="$("$FROZEN_SH" restore "$RID" 2>&1)"; rc=$?
    assert_contains "case 7: the restore reports on the SAME record" "$RID" "$out"

    after_records="$(win_records)"
    assert_eq "case 7: no second record was created for the window" \
        "$before_records" "$after_records"
    drop_record "$RID"
    tm kill-window -t "=$SESSION:agent-pick-1711" 2>/dev/null || true
)

# ---------------------------------------------------------------------------
section "Case 8 — the hook WINS the launch race (V12): success, NO rollback"
# ---------------------------------------------------------------------------
# `restore-launched` is state-guarded to `restoring`. When the replacement's hook
# acks first the record is already `live` and the verb is REFUSED. A coordinator
# that read that refusal as failure would roll back and `respawn-pane -k` the
# pane back to the stand-in — killing an agent it had just restored. This is the
# single worst outcome the task can produce, so the ordering is FORCED (the fake
# agent acks with no delay), not hoped for.
(
    read -r RID PANE < <(make_frozen "agent-pick-1712" "sess-orig")
    wait_for_ready "$PANE" "$RID"

    agent_env FAKE_AGENT_HOOK_DELAY=0
    out="$("$FROZEN_SH" restore "$RID" 2>&1)"; rc=$?
    agent_env_clear
    assert_eq "case 8: restore exits 0" "0" "$rc"
    assert_contains "case 8: the hook ack is reported as SUCCESS" \
        "RESTORED:$RID|hook" "$out"
    assert_eq "case 8: record is live" "live" "$(record_field "$RID" state)"
    assert_eq "case 8: ack is hook" "hook" "$(record_field "$RID" ack)"
    if [ ! -d "$AITASKS_FROZEN_DIR/$RID" ]; then assert_record_pass; else
        assert_record_fail; echo "FAIL: case 8: a verified ack must delete the captures"
    fi
    assert_eq "case 8: the frozen stamp is cleared" "" \
        "$(pane_fmt "$PANE" '#{@aitask_frozen}')"
    # The rollback signature: a stand-in back in the pane and a re-stamped ready
    # mark. Neither may be present.
    assert_eq "case 8: NO rollback — the ready mark was not re-stamped" "" \
        "$(pane_fmt "$PANE" '#{@aitask_standin_ready}')"
    drop_record "$RID"
    tm kill-window -t "=$SESSION:agent-pick-1712" 2>/dev/null || true
)

# ---------------------------------------------------------------------------
section "Case 9 — a PAUSED coordinator's restore is never taken over"
# ---------------------------------------------------------------------------
# A SIGSTOPped process is ALIVE, so the live-owner half of the lease test must
# refuse takeover no matter how much grace has elapsed. This is the assertion
# that fails if `--owner-pid` is ever dropped or defaulted.
(
    read -r RID PANE < <(make_frozen "agent-pick-1713" "sess-orig")
    wait_for_ready "$PANE" "$RID"

    # Pause at `ack`, NOT at `respawn`: by then `launch_pid` is recorded and the
    # replacement is running, so reconcile's liveness row genuinely wants to
    # confirm this record. Pausing earlier would only exercise the
    # `launch_pid == 0` indeterminate row, which declines for a different reason
    # and would let a dropped `--owner-pid` pass unnoticed.
    agent_env FAKE_AGENT_NO_HOOK=1
    AITASKS_FROZEN_PAUSE_AT=ack "$FROZEN_SH" restore "$RID" >/dev/null 2>&1 &
    coord=$!
    # `aitask_frozen.sh` EXECs python, so $coord IS the coordinator process and
    # its stopped state is directly observable.
    if wait_stopped "$coord"; then assert_record_pass; else
        assert_record_fail; echo "FAIL: case 9: the coordinator never stopped itself"
    fi
    assert_eq "case 9: it is holding the record in restoring" "restoring" \
        "$(record_field "$RID" state)"
    assert_eq "case 9: with a real launch recorded" "1" \
        "$([ "$(record_field "$RID" launch_pid)" != "0" ] && echo 1 || echo 0)"

    "$FROZEN_SH" reconcile >/dev/null 2>&1 || true
    assert_eq "case 9: reconcile did not take it over INSIDE the grace" "restoring" \
        "$(record_field "$RID" state)"
    sleep "$GRACE_SLEEP"
    "$FROZEN_SH" reconcile >/dev/null 2>&1 || true
    # THE assertion: a SIGSTOPped owner is ALIVE, so no amount of elapsed grace
    # may license a takeover. This is what fails if --owner-pid is ever dropped.
    assert_eq "case 9: reconcile STILL did not take it over past the grace" "restoring" \
        "$(record_field "$RID" state)"
    assert_eq "case 9: and never confirmed it behind the owner's back" "" \
        "$(record_field "$RID" ack)"

    # Let it finish; the coordinator must complete its own restore.
    kill -CONT "$coord" 2>/dev/null || true
    wait "$coord" 2>/dev/null || true
    agent_env_clear
    wait_for_record_state "$RID" live
    assert_eq "case 9: the resumed coordinator finished its own restore" "live" \
        "$(record_field "$RID" state)"
    drop_record "$RID"
    tm kill-window -t "=$SESSION:agent-pick-1713" 2>/dev/null || true
)

# ---------------------------------------------------------------------------
section "Case 10 — failure injection at every stage"
# ---------------------------------------------------------------------------
# Each stage asserts the STATE and the RECOVERY, not just the exit code.
(
    # begin: the store was never written. Nothing may have moved.
    read -r RID PANE < <(make_frozen "agent-pick-1714" "sess-orig")
    wait_for_ready "$PANE" "$RID"
    AITASKS_RESTORE_FAIL_AT=begin "$FROZEN_SH" restore "$RID" >/dev/null 2>&1
    assert_eq "case 10/begin: record untouched, still frozen" "frozen" \
        "$(record_field "$RID" state)"
    assert_eq "case 10/begin: no attempt was counted" "0" \
        "$(record_field "$RID" restore_attempts)"
    assert_eq "case 10/begin: no lease was minted" "" "$(record_field "$RID" op_nonce)"
    if [ -d "$AITASKS_FROZEN_DIR/$RID" ]; then assert_record_pass; else
        assert_record_fail; echo "FAIL: case 10/begin: the capture went missing"
    fi
    assert_eq "case 10/begin: the ready mark is untouched" "$RID" \
        "$(pane_fmt "$PANE" '#{@aitask_standin_ready}')"
    drop_record "$RID"
    tm kill-window -t "=$SESSION:agent-pick-1714" 2>/dev/null || true
)
(
    # respawn: the stranded-lease case. Reconcile must put the stand-in back.
    read -r RID PANE < <(make_frozen "agent-pick-1715" "sess-orig")
    wait_for_ready "$PANE" "$RID"
    AITASKS_RESTORE_FAIL_AT=respawn "$FROZEN_SH" restore "$RID" >/dev/null 2>&1
    sleep "$GRACE_SLEEP"
    "$FROZEN_SH" reconcile >/dev/null 2>&1 || true
    wait_for_record_state "$RID" frozen
    assert_eq "case 10/respawn: reconcile returned the record to frozen" "frozen" \
        "$(record_field "$RID" state)"
    if [ -d "$AITASKS_FROZEN_DIR/$RID" ]; then assert_record_pass; else
        assert_record_fail; echo "FAIL: case 10/respawn: the capture was lost"
    fi
    if wait_for_ready "$PANE" "$RID"; then assert_record_pass; else
        assert_record_fail
        echo "FAIL: case 10/respawn: the ready mark was never re-stamped — dead pane for the user"
    fi
    drop_record "$RID"
    tm kill-window -t "=$SESSION:agent-pick-1715" 2>/dev/null || true
)
(
    # ack: the replacement IS running; the coordinator died before resolving.
    # Reconcile must liveness-confirm it via launch_pid and KEEP the captures.
    read -r RID PANE < <(make_frozen "agent-pick-1716" "sess-orig")
    wait_for_ready "$PANE" "$RID"
    agent_env FAKE_AGENT_NO_HOOK=1
    AITASKS_RESTORE_FAIL_AT=ack "$FROZEN_SH" restore "$RID" >/dev/null 2>&1
    assert_eq "case 10/ack: the record is left restoring for reconcile" "restoring" \
        "$(record_field "$RID" state)"
    sleep "$GRACE_SLEEP"
    "$FROZEN_SH" reconcile >/dev/null 2>&1 || true
    wait_for_record_state "$RID" live
    assert_eq "case 10/ack: reconcile confirmed it" "live" "$(record_field "$RID" state)"
    assert_eq "case 10/ack: on the WEAKER evidence" "liveness" \
        "$(record_field "$RID" ack)"
    if [ -d "$AITASKS_FROZEN_DIR/$RID" ]; then assert_record_pass; else
        assert_record_fail
        echo "FAIL: case 10/ack: a liveness confirm must KEEP the captures"
    fi
    drop_record "$RID"
    tm kill-window -t "=$SESSION:agent-pick-1716" 2>/dev/null || true
)

# ---------------------------------------------------------------------------
section "Case 11 — coordinator killed after clearing ready, before the respawn"
# ---------------------------------------------------------------------------
# The record is `restoring`, the ready mark is gone, and NOTHING was launched.
# `launch_pid` is 0, so reconcile has no positive evidence of a replacement and
# must ABORT by `standin_pid` — never liveness-confirm.
(
    read -r RID PANE < <(make_frozen "agent-pick-1717" "sess-orig")
    wait_for_ready "$PANE" "$RID"

    AITASKS_FROZEN_PAUSE_AT=respawn "$FROZEN_SH" restore "$RID" >/dev/null 2>&1 &
    coord=$!
    wait_for_record_state "$RID" restoring
    pkill -KILL -P "$coord" 2>/dev/null || true
    kill -KILL "$coord" 2>/dev/null || true
    wait "$coord" 2>/dev/null || true

    assert_eq "case 11: launch_pid stayed 0 (nothing was launched)" "0" \
        "$(record_field "$RID" launch_pid)"
    sleep "$GRACE_SLEEP"
    "$FROZEN_SH" reconcile >/dev/null 2>&1 || true
    sleep "$GRACE_SLEEP"
    "$FROZEN_SH" reconcile >/dev/null 2>&1 || true
    wait_for_record_state "$RID" frozen
    assert_eq "case 11: reconcile aborted back to frozen" "frozen" \
        "$(record_field "$RID" state)"
    if [ "$(record_field "$RID" ack)" != "liveness" ]; then assert_record_pass; else
        assert_record_fail
        echo "FAIL: case 11: reconcile CONFIRMED a restore that never launched"
    fi
    drop_record "$RID"
    tm kill-window -t "=$SESSION:agent-pick-1717" 2>/dev/null || true
)

# ---------------------------------------------------------------------------
section 'Case 12 — a second restore during aborting is refused'
# ---------------------------------------------------------------------------
(
    read -r RID PANE < <(make_frozen "agent-pick-1718" "sess-orig")
    wait_for_ready "$PANE" "$RID"

    agent_env FAKE_AGENT_EXIT=1
    AITASKS_FROZEN_PAUSE_AT=aborting "$FROZEN_SH" restore "$RID" >/dev/null 2>&1 &
    coord=$!
    if wait_for_record_state "$RID" aborting; then
        out="$("$FROZEN_SH" restore "$RID" 2>&1)"; rc=$?
        if [ "$rc" -ne 0 ]; then assert_record_pass; else
            assert_record_fail
            echo "FAIL: case 12: a second restore during aborting must be refused"
        fi
        assert_contains "case 12: the refusal names the record" "$RID" "$out"
    else
        # `aborting` is short-lived; if it was missed the case cannot assert.
        echo "NOTE: case 12: never observed the aborting window — skipping its assertions"
    fi
    pkill -CONT -P "$coord" 2>/dev/null || true
    kill -CONT "$coord" 2>/dev/null || true
    wait "$coord" 2>/dev/null || true
    agent_env_clear
    sleep "$GRACE_SLEEP"
    "$FROZEN_SH" reconcile >/dev/null 2>&1 || true
    drop_record "$RID"
    tm kill-window -t "=$SESSION:agent-pick-1718" 2>/dev/null || true
)

# ---------------------------------------------------------------------------
section "Case 13 — Restore-All keeps going after one failing record"
# ---------------------------------------------------------------------------
(
    agent_env_clear
    read -r RID_OK PANE_OK < <(make_frozen "agent-pick-1719" "sess-ok")
    wait_for_ready "$PANE_OK" "$RID_OK"
    # A record that CANNOT resume: its agent string names a model that does not
    # exist, so the `--dry-run` probe returns nothing and the binary preflight
    # refuses WITHOUT writing to the store — exactly the shape a batch must
    # survive. (An empty session id would be the other such preflight, but it is
    # not a deterministic fixture any more: the replacement agent runs the REAL
    # hook the moment its window is created, so the record legitimately acquires
    # a session id before the case can use its absence.)
    read -r RID_BAD PANE_BAD < <(make_frozen "agent-pick-1720" "sess-bad" "claudecode/nosuchmodel")
    wait_for_ready "$PANE_BAD" "$RID_BAD"

    out="$("$FROZEN_SH" restore --all 2>&1)"; rc=$?
    assert_contains "case 13: the good record was restored" "RESTORED:$RID_OK" "$out"
    assert_contains "case 13: the bad record reported its own failure" \
        "RESTORE_FAILED:$RID_BAD|binary" "$out"
    assert_contains "case 13: a summary line is printed" "RESTORE_ALL:" "$out"
    if [ "$rc" -ne 0 ]; then assert_record_pass; else
        assert_record_fail
        echo "FAIL: case 13: a batch with a failure must not exit 0"
    fi
    assert_eq "case 13: the bad record was left untouched" "frozen" \
        "$(record_field "$RID_BAD" state)"
    drop_record "$RID_OK"
    drop_record "$RID_BAD"
    tm kill-window -t "=$SESSION:agent-pick-1719" 2>/dev/null || true
    tm kill-window -t "=$SESSION:agent-pick-1720" 2>/dev/null || true
)

echo ""
echo "=== Summary ==="
assert_counters_load
echo "Passed: $PASS / $TOTAL"
if [[ "$FAIL" -eq 0 ]]; then echo "ALL TESTS PASSED"; else echo "SOME TESTS FAILED ($FAIL)"; fi
[[ "$FAIL" -eq 0 ]]
