#!/usr/bin/env bash
# tests/test_freeze_engine_live.sh — the freeze engine against a real tmux
# server (t1705_4).
#
# `tests/test_agent_freeze.py` owns the transaction's internals with fakes; this
# file owns everything only a real server can answer: that `respawn-pane -k`
# really keeps the window and the companion, that pane options really survive
# it, that `#{pane_pid}` really changes, that a real `pane_dead` pane is really
# respawned, and that a coordinator really stopped or killed mid-transaction is
# really handled by `reconcile`.
#
# `tests/test_frozen_standin_spike.sh` (t1705_1) is the CONTROL for this file:
# it proves the tmux facts in isolation, without any framework code. If a case
# here fails, run the spike first — a red spike means the platform changed, a
# green spike means this engine did.
#
# THE STAND-IN VIEWER DOES NOT EXIST YET (it lands in t1705_6), so every case
# points `AITASKS_FROZEN_STANDIN_CMD` at `tests/lib/fake_standin.sh`, which
# reproduces the one behaviour reconcile depends on: the viewer stamps its OWN
# pane with `@aitask_standin_ready`. `FAKE_STANDIN_NO_STAMP=1` models a viewer
# that is booting, or broken, and is the fixture for the indeterminate rows.
#
# Cases
#   1   happy freeze: record `frozen`, captures 0600, companion untouched,
#       `standin_pid == #{pane_pid}` of the respawned pane
#   2   `AITASKS_FREEZE_FAIL_AT` at every stage -> the §C rollback
#   3a  a PAUSED coordinator keeps its lease, even past the grace
#   3b  a DEAD coordinator's lease is taken over past the grace
#   3c  a coordinator killed after the respawn -> reconcile commits
#   4   stand-in that never stamps -> INDETERMINATE, no transition (two passes)
#   5   a dead stand-in pane is respawned
#   6   the window disappears while `freezing` -> the gone-pane commit
#   7   Freeze-All never touches a companion or a shadow (+ negative control)
#   8   two sessions: distinct `-t` targets, per-session outcomes, and the
#       fail-closed purge rule
#   9   `kill_agent_pane_smart` on a frozen pane drops its record
#
# TMUX-STRESS. Run from a shell that is NOT inside tmux, with the dedicated
# `-L ait` server stopped; `require_clean_ait_server` refuses otherwise.
#
# Run: bash tests/test_freeze_engine_live.sh
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

# ORDER IS LOAD-BEARING (tests/lib/tmux_isolation.sh): the clean-server guard
# reads $TMUX and resolves `-L ait` against the user's real socket dir;
# require_isolated_tmux then unsets $TMUX and repoints TMUX_TMPDIR.
# shellcheck source=lib/tmux_isolation.sh
. "$PROJECT_DIR/tests/lib/tmux_isolation.sh"
require_clean_ait_server     # FIRST
require_isolated_tmux        # SECOND

# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
. "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"
PYTHON_BIN="$(require_ait_python)"

REAL_PATH="$PATH"
REAL_TMUX="$(command -v tmux)"

FIXTURE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/ait_freeze_live_XXXXXX")"
export TMUX_TMPDIR="$FIXTURE_DIR"
SESSION="ait_freeze_$$"
SESSION_B="ait_freeze_b_$$"

# Two synthetic project roots. `discover_aitasks_sessions` walks a pane's cwd up
# to `aitasks/metadata/project_config.yaml`, so each root needs that marker and
# each session's panes must START in it.
ROOT_A="$FIXTURE_DIR/proj_a"
ROOT_B="$FIXTURE_DIR/proj_b"
for root in "$ROOT_A" "$ROOT_B"; do
    mkdir -p "$root/aitasks/metadata"
    : > "$root/aitasks/metadata/project_config.yaml"
done

# Everything the engine touches is redirected into the fixture: the store, the
# capture tree, and the stand-in command.
export AITASKS_AGENT_SESSIONS_FILE="$FIXTURE_DIR/agent_sessions.json"
export AITASKS_FROZEN_DIR="$FIXTURE_DIR/frozen"
export AITASKS_FROZEN_STANDIN_CMD="$PROJECT_DIR/tests/lib/fake_standin.sh"
# `respawn-pane` runs its command in the TMUX SERVER's environment, not this
# shell's, so a plain `FAKE_STANDIN_NO_STAMP=1` export would never reach the
# stand-in. It rides on the command string instead — the same `env VAR=... cmd`
# prefix the restore coordinator uses for its identity variables (spike case 3).
STANDIN_NO_STAMP="env FAKE_STANDIN_NO_STAMP=1 $PROJECT_DIR/tests/lib/fake_standin.sh"
# The seams are honoured ONLY under this flag, so it is set once here and every
# `AITASKS_FREEZE_FAIL_AT` / `AITASKS_FROZEN_PAUSE_AT` below relies on it.
export AITASKS_TEST_MODE=1
# The lease grace, shortened from 60 s so the takeover races finish in seconds.
# It shortens the TIMER only — case 3a is the assertion that the liveness half
# is untouched.
export AITASKS_STALE_OP_GRACE=1
GRACE_SLEEP=2

chmod +x "$PROJECT_DIR/tests/lib/fake_standin.sh" 2>/dev/null || true
chmod +x "$PROJECT_DIR/tests/lib/fake_agent.sh" 2>/dev/null || true
FAKE_AGENT="$PROJECT_DIR/tests/lib/fake_agent.sh"
FROZEN_SH="$PROJECT_DIR/.aitask-scripts/aitask_frozen.sh"
SESSIONS_SH="$PROJECT_DIR/.aitask-scripts/aitask_agent_sessions.sh"

# --- fixture helpers ---------------------------------------------------------
#
# `tm`, `pane_fmt`, `pane_exists`, `window_exists`, `store`, `record_of_pane`,
# `record_field`, `section`, `make_agent_window`, `wait_for_record_state`,
# `wait_for_ready`, `wait_stopped` and `cleanup` are shared with
# `test_restore_flows_live.sh` and `test_frozen_agents_acceptance.sh` (t1705_8).
# The variables above (REAL_TMUX, REAL_PATH, SESSIONS_SH, FAKE_AGENT,
# FIXTURE_DIR) are this file's half of that library's contract.
#
# The wait_* helpers poll 100 times at 0.1 s rather than the library's default
# 120: cases 4 and 5 deliberately wait for a stamp that never arrives, so the
# budget is a real cost here, not just a failure-path ceiling.
FROZEN_WAIT_TRIES=100
# shellcheck source=lib/frozen_fixtures.sh
. "$PROJECT_DIR/tests/lib/frozen_fixtures.sh"

trap cleanup EXIT

tm new-session -d -s "$SESSION" -n scratch -c "$ROOT_A" "sleep 1000"
tm new-session -d -s "$SESSION_B" -n scratch -c "$ROOT_B" "sleep 1000"
sleep 0.4

# ---------------------------------------------------------------------------
section "Case 1 — happy freeze"
# ---------------------------------------------------------------------------
(
    read -r AGENT COMPANION < <(make_agent_window "$SESSION" "agent-pick-1705" "$ROOT_A")
    sleep 0.3
    agent_pid="$(pane_fmt "$AGENT" '#{pane_pid}')"
    comp_pid_before="$(pane_fmt "$COMPANION" '#{pane_pid}')"

    out="$("$FROZEN_SH" freeze "$AGENT" 2>&1)"
    rc=$?
    assert_eq "freeze exits 0" "0" "$rc"
    assert_contains "freeze reports FROZEN" "FROZEN:" "$out"

    rid="$(record_of_pane "$AGENT")"
    assert_eq "the pane carries a canonical record id" "8" "${#rid}"
    assert_eq "record state is frozen" "frozen" "$(record_field "$rid" state)"
    assert_eq "the frozen stamp names the record" "$rid" \
        "$(pane_fmt "$AGENT" '#{@aitask_frozen}')"

    # `respawn-pane -k` keeps the PANE ID and replaces the PROCESS. Asserting
    # the id alone would pass even if nothing had been respawned, so the pid is
    # the load-bearing half.
    new_pid="$(pane_fmt "$AGENT" '#{pane_pid}')"
    assert_eq "the pane id is unchanged" "$AGENT" "$(pane_fmt "$AGENT" '#{pane_id}')"
    if [ "$new_pid" != "$agent_pid" ]; then assert_record_pass; else
        assert_record_fail
        echo "FAIL: #{pane_pid} did not change — the agent was never respawned"
    fi
    assert_eq "standin_pid is the respawned process" "$new_pid" \
        "$(record_field "$rid" standin_pid)"

    # The companion and the window are what the whole design protects.
    assert_eq "the companion pane still exists" "$COMPANION" \
        "$(pane_fmt "$COMPANION" '#{pane_id}')"
    assert_eq "the companion's process is untouched" "$comp_pid_before" \
        "$(pane_fmt "$COMPANION" '#{pane_pid}')"
    if window_exists "agent-pick-1705" "$SESSION"; then assert_record_pass; else
        assert_record_fail; echo "FAIL: the window did not survive the freeze"
    fi

    # The viewer stamps its own readiness once it mounts.
    if wait_for_ready "$AGENT" "$rid"; then assert_record_pass; else
        assert_record_fail; echo "FAIL: the stand-in never stamped @aitask_standin_ready"
    fi

    ansi="$(record_field "$rid" capture_ansi)"
    txt="$(record_field "$rid" capture_txt)"
    for f in "$ansi" "$txt"; do
        if [ -f "$f" ]; then assert_record_pass; else
            assert_record_fail; echo "FAIL: missing capture file $f"
        fi
        # `stat` rather than `ls -l`: the octal mode is the assertion, and it
        # is the same on both platforms once the format flag is right.
        if stat -f '%Lp' "$f" >/dev/null 2>&1; then
            mode="$(stat -f '%Lp' "$f")"        # BSD / macOS
        else
            mode="$(stat -c '%a' "$f")"         # GNU
        fi
        assert_eq "capture file is 0600 ($(basename "$f"))" "600" "$mode"
    done
    lines="$(record_field "$rid" capture_lines)"
    actual_lines="$(wc -l < "$txt" | tr -d ' ')"
    assert_eq "capture_lines matches the file" "$lines" "$actual_lines"
)

# ---------------------------------------------------------------------------
section "Case 2 — failure injection at every stage"
# ---------------------------------------------------------------------------
for stage in capture begin stamp respawn; do
    (
        W="agent-fail-$stage"
        read -r AGENT COMPANION < <(make_agent_window "$SESSION" "$W" "$ROOT_A")
        sleep 0.3
        agent_pid="$(pane_fmt "$AGENT" '#{pane_pid}')"

        out="$(AITASKS_FREEZE_FAIL_AT="$stage" "$FROZEN_SH" freeze "$AGENT" 2>&1)"
        rc=$?
        assert_eq "[$stage] freeze exits 1" "1" "$rc"
        assert_contains "[$stage] reports the stage" "FREEZE_FAILED:$stage" "$out"

        # The invariant every rollback shares: the AGENT IS STILL RUNNING.
        assert_eq "[$stage] the agent process is untouched" "$agent_pid" \
            "$(pane_fmt "$AGENT" '#{pane_pid}')"
        assert_eq "[$stage] no frozen stamp is left behind" "" \
            "$(pane_fmt "$AGENT" '#{@aitask_frozen}')"
        if window_exists "$W" "$SESSION"; then assert_record_pass; else
            assert_record_fail; echo "FAIL: [$stage] the window was destroyed"
        fi

        rid="$(record_of_pane "$AGENT")"
        if [ -n "$rid" ]; then
            assert_eq "[$stage] the record is back to live" "live" \
                "$(record_field "$rid" state)"
            if [ ! -d "$AITASKS_FROZEN_DIR/$rid" ]; then assert_record_pass; else
                assert_record_fail
                echo "FAIL: [$stage] capture files survived a rolled-back freeze"
            fi
        fi
    )
done

(
    # `commit` is the ONE stage with no rollback, and that is deliberate: the
    # agent is already gone, so aborting would leave a `live` record with no
    # process behind it. `freezing` is the honest state; reconcile finishes it.
    W="agent-fail-commit"
    read -r AGENT COMPANION < <(make_agent_window "$SESSION" "$W" "$ROOT_A")
    sleep 0.3
    out="$(AITASKS_FREEZE_FAIL_AT=commit "$FROZEN_SH" freeze "$AGENT" 2>&1)"
    assert_contains "[commit] reports the stage" "FREEZE_FAILED:commit" "$out"
    rid="$(record_of_pane "$AGENT")"
    assert_eq "[commit] the record stays freezing for reconcile" "freezing" \
        "$(record_field "$rid" state)"
    assert_eq "[commit] the pane IS stamped (the swap happened)" "$rid" \
        "$(pane_fmt "$AGENT" '#{@aitask_frozen}')"

    # And reconcile completes it, once the abandoned lease goes stale.
    sleep "$GRACE_SLEEP"
    wait_for_ready "$AGENT" "$rid" || true
    out="$("$FROZEN_SH" reconcile 2>&1)"
    assert_contains "[commit] reconcile commits the freeze" "FROZEN:$rid" "$out"
    assert_eq "[commit] the record is frozen" "frozen" "$(record_field "$rid" state)"
)

# ---------------------------------------------------------------------------
section "Case 3a — a PAUSED coordinator keeps its lease"
# ---------------------------------------------------------------------------
(
    # `_lease_stale` is `grace elapsed AND owner dead`, and `_pid_alive` is
    # fail-closed — only ESRCH proves death, so a SIGSTOPped process is ALIVE.
    # The second reconcile, run PAST the grace, is the load-bearing assertion:
    # it is what a grace-only implementation would fail.
    W="agent-paused"
    read -r AGENT COMPANION < <(make_agent_window "$SESSION" "$W" "$ROOT_A")
    sleep 0.3
    agent_pid="$(pane_fmt "$AGENT" '#{pane_pid}')"

    AITASKS_FROZEN_PAUSE_AT=begin "$FROZEN_SH" freeze "$AGENT" >/dev/null 2>&1 &
    coord=$!
    if wait_stopped "$coord"; then assert_record_pass; else
        assert_record_fail; echo "FAIL: the coordinator never stopped itself"
    fi

    rid="$(record_of_pane "$AGENT")"
    assert_eq "the record is freezing while the owner holds it" "freezing" \
        "$(record_field "$rid" state)"

    out="$("$FROZEN_SH" reconcile 2>&1)"
    assert_contains "reconcile refuses inside the grace" "LEASE_HELD:$rid" "$out"

    sleep "$GRACE_SLEEP"
    out="$("$FROZEN_SH" reconcile 2>&1)"
    assert_contains "reconcile STILL refuses past the grace (live owner)" \
        "LEASE_HELD:$rid" "$out"
    assert_eq "the state is untouched by both passes" "freezing" \
        "$(record_field "$rid" state)"
    assert_eq "the agent is still running" "$agent_pid" \
        "$(pane_fmt "$AGENT" '#{pane_pid}')"

    kill -CONT "$coord" 2>/dev/null || true
    wait "$coord" 2>/dev/null
    assert_eq "the resumed coordinator finishes its own freeze" "frozen" \
        "$(record_field "$rid" state)"
)

# ---------------------------------------------------------------------------
section "Case 3b — a DEAD coordinator's lease is taken over"
# ---------------------------------------------------------------------------
(
    # Killed between the stamp and the respawn: the agent is still running, and
    # no stand-in was ever started. The §C row "agent alive, stand-in not up"
    # applies — unstamp both options, `freeze-abort`, captures deleted.
    W="agent-killed"
    read -r AGENT COMPANION < <(make_agent_window "$SESSION" "$W" "$ROOT_A")
    sleep 0.3
    agent_pid="$(pane_fmt "$AGENT" '#{pane_pid}')"

    AITASKS_FROZEN_PAUSE_AT=stamp "$FROZEN_SH" freeze "$AGENT" >/dev/null 2>&1 &
    coord=$!
    wait_stopped "$coord" || true
    rid="$(record_of_pane "$AGENT")"
    assert_eq "the pane is stamped before the pause" "$rid" \
        "$(pane_fmt "$AGENT" '#{@aitask_frozen}')"

    kill -9 "$coord" 2>/dev/null || true
    kill -CONT "$coord" 2>/dev/null || true   # SIGKILL needs CONT to reap a stopped proc
    wait "$coord" 2>/dev/null

    sleep "$GRACE_SLEEP"
    out="$("$FROZEN_SH" reconcile 2>&1)"
    assert_contains "reconcile takes over and aborts the freeze" "LIVE:$rid" "$out"
    assert_eq "the record is back to live" "live" "$(record_field "$rid" state)"
    assert_eq "the frozen stamp is cleared" "" \
        "$(pane_fmt "$AGENT" '#{@aitask_frozen}')"
    assert_eq "the agent survived the whole episode" "$agent_pid" \
        "$(pane_fmt "$AGENT" '#{pane_pid}')"
    if [ ! -d "$AITASKS_FROZEN_DIR/$rid" ]; then assert_record_pass; else
        assert_record_fail; echo "FAIL: an aborted freeze left its captures behind"
    fi
)

# ---------------------------------------------------------------------------
section "Case 3c — a coordinator killed AFTER the respawn"
# ---------------------------------------------------------------------------
(
    # The stand-in is up, so the §C row "stamped and ready" applies and
    # reconcile completes the commit the dead coordinator never sent.
    W="agent-killed-late"
    read -r AGENT COMPANION < <(make_agent_window "$SESSION" "$W" "$ROOT_A")
    sleep 0.3

    AITASKS_FROZEN_PAUSE_AT=commit "$FROZEN_SH" freeze "$AGENT" >/dev/null 2>&1 &
    coord=$!
    wait_stopped "$coord" || true
    kill -9 "$coord" 2>/dev/null || true
    kill -CONT "$coord" 2>/dev/null || true
    wait "$coord" 2>/dev/null

    rid="$(record_of_pane "$AGENT")"
    wait_for_ready "$AGENT" "$rid" || true
    sleep "$GRACE_SLEEP"
    out="$("$FROZEN_SH" reconcile 2>&1)"
    assert_contains "reconcile commits the abandoned freeze" "FROZEN:$rid" "$out"
    assert_eq "standin_pid is the live stand-in" "$(pane_fmt "$AGENT" '#{pane_pid}')" \
        "$(record_field "$rid" standin_pid)"
)

# ---------------------------------------------------------------------------
section "Case 4 — a stand-in that never stamps is INDETERMINATE"
# ---------------------------------------------------------------------------
(
    # A viewer that is still booting is indistinguishable from one that never
    # will be, so reconcile makes NO transition and re-checks next pass. Two
    # passes are asserted because a single one could pass by accident against an
    # implementation that transitions on the second.
    W="agent-nostamp"
    read -r AGENT COMPANION < <(make_agent_window "$SESSION" "$W" "$ROOT_A")
    sleep 0.3

    AITASKS_FROZEN_STANDIN_CMD="$STANDIN_NO_STAMP" AITASKS_FREEZE_FAIL_AT=commit \
        "$FROZEN_SH" freeze "$AGENT" >/dev/null 2>&1
    rid="$(record_of_pane "$AGENT")"
    assert_eq "the record is freezing" "freezing" "$(record_field "$rid" state)"
    assert_eq "the stand-in never stamped readiness" "" \
        "$(pane_fmt "$AGENT" '#{@aitask_standin_ready}')"

    sleep "$GRACE_SLEEP"
    for pass in 1 2; do
        out="$(AITASKS_FROZEN_STANDIN_CMD="$STANDIN_NO_STAMP" \
            "$FROZEN_SH" reconcile 2>&1)"
        assert_contains "pass $pass: reported indeterminate" \
            "INDETERMINATE:$rid" "$out"
        assert_eq "pass $pass: the state is unchanged" "freezing" \
            "$(record_field "$rid" state)"
    done
)

# ---------------------------------------------------------------------------
section "Case 5 — a dead stand-in pane is respawned"
# ---------------------------------------------------------------------------
(
    W="agent-deadstandin"
    read -r AGENT COMPANION < <(make_agent_window "$SESSION" "$W" "$ROOT_A")
    sleep 0.3
    "$FROZEN_SH" freeze "$AGENT" >/dev/null 2>&1
    rid="$(record_of_pane "$AGENT")"
    wait_for_ready "$AGENT" "$rid" || true

    # `remain-on-exit` keeps the pane after its process dies, which is exactly
    # the `pane_dead=1` observation the §C row keys on.
    tm set-option -p -t "$AGENT" remain-on-exit on
    standin_pid="$(pane_fmt "$AGENT" '#{pane_pid}')"
    kill -9 "$standin_pid" 2>/dev/null || true
    i=0
    while [ "$i" -lt 50 ] && [ "$(pane_fmt "$AGENT" '#{pane_dead}')" != "1" ]; do
        sleep 0.1; i=$((i + 1))
    done
    assert_eq "the pane is dead" "1" "$(pane_fmt "$AGENT" '#{pane_dead}')"

    out="$("$FROZEN_SH" reconcile 2>&1)"
    assert_contains "reconcile respawned the stand-in" "STANDIN:$rid" "$out"
    assert_eq "the pane is alive again" "0" "$(pane_fmt "$AGENT" '#{pane_dead}')"
    new_pid="$(pane_fmt "$AGENT" '#{pane_pid}')"
    if [ "$new_pid" != "$standin_pid" ]; then assert_record_pass; else
        assert_record_fail; echo "FAIL: the stand-in was not actually respawned"
    fi
    assert_eq "standin_pid was updated" "$new_pid" "$(record_field "$rid" standin_pid)"
)

# ---------------------------------------------------------------------------
section "Case 6 — the window disappears while freezing"
# ---------------------------------------------------------------------------
(
    W="agent-windowgone"
    read -r AGENT COMPANION < <(make_agent_window "$SESSION" "$W" "$ROOT_A")
    sleep 0.3
    AITASKS_FROZEN_STANDIN_CMD="$STANDIN_NO_STAMP" AITASKS_FREEZE_FAIL_AT=commit \
        "$FROZEN_SH" freeze "$AGENT" >/dev/null 2>&1
    rid="$(record_of_pane "$AGENT")"
    assert_eq "precondition: freezing" "freezing" "$(record_field "$rid" state)"

    tm kill-window -t "$AGENT" 2>/dev/null || true
    sleep 0.3
    if pane_exists "$AGENT"; then
        assert_record_fail; echo "FAIL: the pane survived kill-window"
    else
        assert_record_pass
    fi

    sleep "$GRACE_SLEEP"
    out="$("$FROZEN_SH" reconcile 2>&1)"
    assert_contains "reconcile commits with the gone-pane pair" \
        "FROZEN:$rid|pane_gone" "$out"
    assert_eq "the record is frozen and restorable" "frozen" \
        "$(record_field "$rid" state)"
    assert_eq "the recorded pane id is empty" "" "$(record_field "$rid" pane_id)"
    assert_eq "the recorded standin pid is 0" "0" "$(record_field "$rid" standin_pid)"
)

# ---------------------------------------------------------------------------
section "Case 7 — Freeze-All never touches a helper pane"
# ---------------------------------------------------------------------------
(
    # `classify_pane` reads ONLY the window name, so every pane in an `agent-*`
    # window classifies as AGENT — the companion minimonitor included. Selecting
    # on the category alone would respawn the very pane the freeze design exists
    # to preserve. The pid assertion is what proves it: `respawn-pane -k` keeps
    # the pane id, so checking the id alone would pass either way.
    W="agent-freezeall"
    read -r AGENT COMPANION < <(make_agent_window "$SESSION" "$W" "$ROOT_A")
    SHADOW="$(tm split-window -d -t "$AGENT" -c "$ROOT_A" -P -F '#{pane_id}' "sleep 1000")"
    tm set-option -p -t "$SHADOW" @aitask_shadow_target "$AGENT"
    sleep 0.3

    comp_pid="$(pane_fmt "$COMPANION" '#{pane_pid}')"
    shadow_pid="$(pane_fmt "$SHADOW" '#{pane_pid}')"

    "$FROZEN_SH" freeze --all >/dev/null 2>&1
    # Count the records belonging to THIS window. Counting `FROZEN:` lines would
    # be wrong: Freeze-All sweeps the whole session, so earlier cases' windows
    # contribute their own results to the same run.
    frozen_count="$(store list --root "$ROOT_A" 2>/dev/null | grep -cF "|$W|")"

    assert_eq "the agent was frozen" "$(record_of_pane "$AGENT")" \
        "$(pane_fmt "$AGENT" '#{@aitask_frozen}')"
    assert_eq "the companion's PROCESS is unchanged" "$comp_pid" \
        "$(pane_fmt "$COMPANION" '#{pane_pid}')"
    assert_eq "the companion's marker is intact" "minimonitor:$comp_pid" \
        "$(pane_fmt "$COMPANION" '#{@aitask_monitor_kind}')"
    assert_eq "the companion got no record" "" "$(record_of_pane "$COMPANION")"
    assert_eq "the shadow's PROCESS is unchanged" "$shadow_pid" \
        "$(pane_fmt "$SHADOW" '#{pane_pid}')"
    assert_eq "the shadow got no record" "" "$(record_of_pane "$SHADOW")"
    assert_eq "exactly ONE record exists for this window" "1" "$frozen_count"

    # NEGATIVE CONTROL: the category-only selection the plan warns about really
    # does pick up the helpers, so the assertion above is not vacuous.
    picked="$(PYTHONPATH="$PROJECT_DIR/.aitask-scripts:$PROJECT_DIR/.aitask-scripts/lib" \
        AIT_SESSION="$SESSION" AIT_WINDOW="$W" \
        AITASKS_TMUX_SOCKET="" TMUX_TMPDIR="$FIXTURE_DIR" \
        "$PYTHON_BIN" - <<'PYEOF'
import os

from monitor.monitor_core import PaneCategory, TmuxMonitor

session = os.environ["AIT_SESSION"]
window = os.environ["AIT_WINDOW"]
mon = TmuxMonitor(session=session, multi_session=False, exclude_pane="")

# What a category-only selection would have picked: every pane of the window,
# classified by WINDOW NAME alone.
rc, out = mon.tmux_run(["list-panes", "-s", "-t", f"={session}",
                        "-F", "#{window_name}\t#{pane_id}"])
naive = [ln.split("\t")[1] for ln in out.splitlines()
         if ln.split("\t")[0] == window
         and mon.classify_pane(window) == PaneCategory.AGENT]

# What the shipped selection picks.
safe = [p.pane_id for p in mon.discover_panes() if p.window_name == window]
print(len(naive))
print(len(safe))
PYEOF
)"
    naive_n="$(printf '%s' "$picked" | sed -n '1p')"
    safe_n="$(printf '%s' "$picked" | sed -n '2p')"
    if [ "${naive_n:-0}" -gt "${safe_n:-0}" ]; then assert_record_pass; else
        assert_record_fail
        echo "FAIL: negative control — a category-only selection picked $naive_n"
        echo "      panes and discover_panes() picked $safe_n; the helper filter"
        echo "      is not being exercised, so Case 7 proves nothing."
    fi
)

# ---------------------------------------------------------------------------
section "Case 8 — two sessions: targeting, per-session outcomes, purge safety"
# ---------------------------------------------------------------------------
(
    # An untargeted `list-panes -s` silently returns whichever session tmux
    # considers current, so a test that only checks aggregate outcomes can pass
    # while one session is enumerated twice. Both halves are asserted.
    read -r AGENT_A _ < <(make_agent_window "$SESSION" "agent-two-a" "$ROOT_A")
    read -r AGENT_B _ < <(make_agent_window "$SESSION_B" "agent-two-b" "$ROOT_B")
    sleep 0.3

    # A logging tmux shim, first on PATH, records every argv the engine issues.
    TMUX_LOG="$FIXTURE_DIR/tmux_calls.log"
    mkdir -p "$FIXTURE_DIR/logbin"
    cat > "$FIXTURE_DIR/logbin/tmux" <<SHIM
#!/usr/bin/env bash
printf '%s\n' "\$*" >> "$TMUX_LOG"
exec "$REAL_TMUX" "\$@"
SHIM
    chmod +x "$FIXTURE_DIR/logbin/tmux"

    "$FROZEN_SH" freeze "$AGENT_A" >/dev/null 2>&1
    "$FROZEN_SH" freeze "$AGENT_B" >/dev/null 2>&1
    rid_a="$(record_of_pane "$AGENT_A")"
    rid_b="$(record_of_pane "$AGENT_B")"
    wait_for_ready "$AGENT_A" "$rid_a" || true
    wait_for_ready "$AGENT_B" "$rid_b" || true

    assert_eq "session A's agent is frozen" "frozen" "$(record_field "$rid_a" state)"
    assert_eq "session B's agent is frozen" "frozen" "$(record_field "$rid_b" state)"

    : > "$TMUX_LOG"
    PATH="$FIXTURE_DIR/logbin:$REAL_PATH" "$FROZEN_SH" reconcile >/dev/null 2>&1
    targets="$(grep -F 'list-panes -s -t' "$TMUX_LOG" \
        | sed -n 's/.*list-panes -s -t \([^ ]*\).*/\1/p' | sort -u)"
    assert_contains "session A was targeted explicitly" "=$SESSION" "$targets"
    assert_contains "session B was targeted explicitly" "=$SESSION_B" "$targets"
    distinct="$(printf '%s\n' "$targets" | grep -c '^=ait_freeze')"
    if [ "$distinct" -ge 2 ]; then assert_record_pass; else
        assert_record_fail
        echo "FAIL: the two enumerations did not carry DISTINCT -t targets"
        echo "      (got: $targets) — an untargeted pass would look like this"
    fi

    # PURGE SAFETY. Force session B's enumeration to fail and assert that B's
    # records SURVIVE. Without the fail-closed rule, a `ROOT` row for a root
    # that was never enumerated makes `purge`'s `dead_window` rule delete every
    # live record in that project.
    LIVE_W="agent-live-b"
    read -r LIVE_B _ < <(make_agent_window "$SESSION_B" "$LIVE_W" "$ROOT_B")
    sleep 0.3
    # Register it in the store WITHOUT freezing it: a plain `live` record is
    # exactly what a wrong `ROOT` row would destroy.
    live_pid="$(pane_fmt "$LIVE_B" '#{pane_pid}')"
    store upsert --root "$ROOT_B" --window "$LIVE_W" \
        --pane "$LIVE_B" --pane-pid "$live_pid" >/dev/null 2>&1
    live_rid="$(store list --root "$ROOT_B" 2>/dev/null \
        | grep -F "|$LIVE_W|" | head -n1 | cut -d: -f2 | cut -d'|' -f1)"
    assert_eq "the live control record exists" "live" \
        "$(record_field "$live_rid" state)"

    mkdir -p "$FIXTURE_DIR/failbin"
    cat > "$FIXTURE_DIR/failbin/tmux" <<FAILSHIM
#!/usr/bin/env bash
# Fail ONLY session B's enumeration; everything else is the real binary.
if [ "\$1" = "list-panes" ] && printf '%s' "\$*" | grep -q -- "=$SESSION_B"; then
    exit 1
fi
exec "$REAL_TMUX" "\$@"
FAILSHIM
    chmod +x "$FIXTURE_DIR/failbin/tmux"

    PATH="$FIXTURE_DIR/failbin:$REAL_PATH" "$FROZEN_SH" reconcile >/dev/null 2>&1
    assert_eq "B's live record SURVIVED an unenumerable session" "live" \
        "$(record_field "$live_rid" state)"
    assert_eq "B's frozen record survived too" "frozen" \
        "$(record_field "$rid_b" state)"
)

# ---------------------------------------------------------------------------
section "Case 8b — reconcile does not lease a healthy frozen record"
# ---------------------------------------------------------------------------
(
    # `lease-take` WRITES: it mints a nonce, stamps the caller as owner, and
    # resets `op_started_at`. Nothing clears it afterwards, so a reconcile that
    # leased every non-`live` record would leave every frozen record owned by a
    # pid that exits moments later — and any real coordinator needing a nonce
    # for that record would then get LEASE_HELD until the grace elapsed.
    # Reconcile would be locking out the work it exists to enable.
    W="agent-nolease"
    read -r AGENT COMPANION < <(make_agent_window "$SESSION" "$W" "$ROOT_A")
    sleep 0.3
    "$FROZEN_SH" freeze "$AGENT" >/dev/null 2>&1
    rid="$(record_of_pane "$AGENT")"
    wait_for_ready "$AGENT" "$rid" || true
    assert_eq "precondition: frozen" "frozen" "$(record_field "$rid" state)"
    assert_eq "a committed freeze left NO lease" "" "$(record_field "$rid" op_nonce)"

    out="$("$FROZEN_SH" reconcile 2>&1)"
    assert_contains "reconcile reports it as kept" "KEEP:$rid|frozen" "$out"
    assert_eq "and left no lease behind" "" "$(record_field "$rid" op_nonce)"
    assert_eq "nor an owner pid" "0" "$(record_field "$rid" op_owner_pid)"

    # The consequence, asserted directly: a coordinator can still take a lease
    # on that record immediately, with no grace to wait out.
    out="$(store lease-take "$rid" --owner-pid $$ 2>&1)"
    assert_contains "a coordinator can lease it right away" "LEASED:$rid" "$out"
)

# ---------------------------------------------------------------------------
section "Case 9 — kill_agent_pane_smart on a frozen pane"
# ---------------------------------------------------------------------------
(
    W="agent-killfrozen"
    read -r AGENT COMPANION < <(make_agent_window "$SESSION" "$W" "$ROOT_A")
    SIBLING="$(tm split-window -d -t "$AGENT" -c "$ROOT_A" -P -F '#{pane_id}' "sleep 1000")"
    sleep 0.3
    "$FROZEN_SH" freeze "$AGENT" >/dev/null 2>&1
    rid="$(record_of_pane "$AGENT")"
    assert_eq "precondition: frozen" "frozen" "$(record_field "$rid" state)"
    if [ -d "$AITASKS_FROZEN_DIR/$rid" ]; then assert_record_pass; else
        assert_record_fail; echo "FAIL: no capture dir to remove"
    fi

    PYTHONPATH="$PROJECT_DIR/.aitask-scripts:$PROJECT_DIR/.aitask-scripts/lib" \
    AIT_SESSION="$SESSION" AIT_TARGET="$AGENT" \
    AITASKS_TMUX_SOCKET="" TMUX_TMPDIR="$FIXTURE_DIR" \
    AITASKS_AGENT_SESSIONS_FILE="$AITASKS_AGENT_SESSIONS_FILE" \
    AITASKS_FROZEN_DIR="$AITASKS_FROZEN_DIR" \
    "$PYTHON_BIN" - >/dev/null 2>&1 <<'PYEOF'
import os

from monitor.monitor_core import TmuxMonitor

mon = TmuxMonitor(session=os.environ["AIT_SESSION"], multi_session=False,
                  exclude_pane="")
mon.discover_panes()          # populate the cache the real caller relies on
mon.kill_agent_pane_smart(os.environ["AIT_TARGET"])
PYEOF

    assert_eq "the record was dropped" "" "$(record_field "$rid" state)"
    if [ ! -d "$AITASKS_FROZEN_DIR/$rid" ]; then assert_record_pass; else
        assert_record_fail; echo "FAIL: drop left the capture files behind"
    fi
    # The sibling rule is unchanged: a real sibling remains, so only the pane
    # went and the window (with its companion) survives.
    if window_exists "$W" "$SESSION"; then assert_record_pass; else
        assert_record_fail
        echo "FAIL: the window collapsed although a real sibling remained"
    fi
    if pane_exists "$SIBLING"; then assert_record_pass; else
        assert_record_fail; echo "FAIL: the live sibling was killed"
    fi
)

echo ""
echo "=== Summary ==="
assert_counters_load
echo "Passed: $PASS / $TOTAL"
if [[ "$FAIL" -eq 0 ]]; then echo "ALL TESTS PASSED"; else echo "SOME TESTS FAILED ($FAIL)"; fi
[[ "$FAIL" -eq 0 ]]
