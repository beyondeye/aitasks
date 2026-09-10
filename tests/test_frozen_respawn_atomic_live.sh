#!/usr/bin/env bash
# tests/test_frozen_respawn_atomic_live.sh — the REAL-tmux contract for
# `agent_frozen_ops.respawn_if_stamped` (t1773).
#
# WHY THIS FILE EXISTS. The scripted tests in tests/test_agent_restore.py and
# tests/test_agent_frozen_ops.py assert the DECISION given a response. They
# cannot assert the tmux behaviours the whole mechanism rests on, because they
# supply those behaviours themselves — so a tmux version bump or a platform
# difference would leave every mock green while the mechanism is broken. Each
# case in Part A pins one measured fact; Part B drives the race itself.
#
# THE MECHANISM, in one paragraph. `respawn-pane -k` is destructive, and the
# recorded `%N` it targets is only a hint: pane ids are monotonic within a tmux
# server and never reused, but a RESTARTED server renumbers from %0, so a
# recorded id can come back owned by an unrelated live agent. The stamp check
# and the respawn therefore travel as ONE `if-shell -F` dispatch. `if-shell`
# exits 0 either way, so "did it fire" is proved by a fresh per-call token
# written as the LAST command of the matched branch — never by a pid delta,
# which across a restart compares two different panes.
#
# ISOLATION. `require_isolated_tmux` only (NOT `require_clean_ait_server`):
# nothing here arms `pane-died` hooks or runs framework code that reaches tmux
# outside the gateway. It drives the helper directly from a small Python driver,
# because the helper's contract is what is under test. Every tmux call — the
# `kill-server` in Part B included — is scoped to this file's own per-run
# TMUX_TMPDIR socket, so it can never touch the user's server, and this suite is
# therefore safe to run from inside tmux.
#
# Run: bash tests/test_frozen_respawn_atomic_live.sh
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

# shellcheck source=lib/tmux_isolation.sh
. "$PROJECT_DIR/tests/lib/tmux_isolation.sh"
require_isolated_tmux

# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
. "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"
PYTHON_BIN="$(require_ait_python)"

REAL_TMUX="$(command -v tmux)"
REAL_PATH="$PATH"
FIXTURE_DIR="$(cd "$(mktemp -d "${TMPDIR:-/tmp}/ait_respawn_atomic_XXXXXX")" && pwd -P)"
# Our OWN socket dir, so the Part B `kill-server` is scoped to this run.
export TMUX_TMPDIR="$FIXTURE_DIR"

# shellcheck source=lib/frozen_fixtures.sh
. "$PROJECT_DIR/tests/lib/frozen_fixtures.sh"

FROZEN_OPT="@aitask_frozen"
READY_OPT="@aitask_standin_ready"
TOKEN_OPT="@aitask_respawn_token"
RID="abc123"

# `cleanup` comes from frozen_fixtures.sh — it kills the isolated server and
# removes the fixture tree, which is exactly this suite's teardown. Redefining
# it here would shadow the shared one for no gain.
trap cleanup EXIT

# --- the driver -------------------------------------------------------------
# Prints `fired|pane|pid|reason`. Kept to one call so a paused driver is stopped
# at exactly the seam under test and nowhere else.
DRIVER="$FIXTURE_DIR/driver.py"
cat > "$DRIVER" <<'PYEOF'
import sys
sys.path.insert(0, sys.argv[1] + "/.aitask-scripts")
sys.path.insert(0, sys.argv[1] + "/.aitask-scripts/lib")
import agent_frozen_ops as ops

pane, expect, command = sys.argv[2], sys.argv[3], sys.argv[4]
unset = sys.argv[5] or None
fired, got_pane, got_pid, reason = ops.respawn_if_stamped(
    pane, command, option="@aitask_frozen", expect=expect,
    env={"V1": "one", "V2": "two"}, unset=unset)
print(f"{fired}|{got_pane}|{got_pid}|{reason}")
PYEOF

drive() {   # drive <pane> <expect> <command> [unset]
    "$PYTHON_BIN" "$DRIVER" "$PROJECT_DIR" "$1" "$2" "$3" "${4:-}"
}

fresh_server() {   # fresh_server <pane-command> -> the new session's first pane
    tm kill-server 2>/dev/null || true
    sleep 0.3
    tm new-session -d -s p "$1"
    sleep 0.3
}

# ===========================================================================
section "Part A — the tmux facts this design rests on"
# ===========================================================================

# ---------------------------------------------------------------------------
section "A1 — a matched dispatch respawns, unsets, and leaves our token"
# ---------------------------------------------------------------------------
(
    fresh_server "sleep 3001"
    tm set-option -p -t %0 "$FROZEN_OPT" "$RID"
    tm set-option -p -t %0 "$READY_OPT" 1
    before_pid="$(pane_fmt %0 '#{pane_pid}')"

    out="$(drive %0 "$RID" "sleep 3002" "$READY_OPT")"
    sleep 0.4
    IFS='|' read -r fired got_pane got_pid reason <<<"$out"

    assert_eq "A1: the helper reports it fired" "True" "$fired"
    assert_eq "A1: and hands back the pane it respawned" "%0" "$got_pane"
    assert_eq "A1: the reason is empty on success" "" "$reason"
    assert_contains "A1: the pane really is running the new command" \
        "sleep 3002" "$(pane_fmt %0 '#{pane_start_command}')"
    if [ "$(pane_fmt %0 '#{pane_pid}')" != "$before_pid" ]; then assert_record_pass; else
        assert_record_fail; echo "FAIL: A1: the pane was never respawned"
    fi
    assert_eq "A1: the ready mark was cleared inside the same branch" "" \
        "$(pane_fmt %0 "#{${READY_OPT}}")"
    # The token is per-attempt: leaving it would let a later call's equality
    # check see a stale value. The helper clears it as soon as it reads it.
    assert_eq "A1: the token did not outlive the attempt" "" \
        "$(pane_fmt %0 "#{${TOKEN_OPT}}")"
)

# ---------------------------------------------------------------------------
section "A2 — a REJECTED dispatch leaves the pane completely untouched"
# ---------------------------------------------------------------------------
# The single most important fact: if this ever stopped holding, the helper would
# be killing panes it had decided not to kill.
(
    fresh_server "sleep 3003"
    tm set-option -p -t %0 "$FROZEN_OPT" "$RID"
    tm set-option -p -t %0 "$READY_OPT" 1
    before_pid="$(pane_fmt %0 '#{pane_pid}')"
    before_cmd="$(pane_fmt %0 '#{pane_start_command}')"

    out="$(drive %0 "somebody-else" "sleep 3004" "$READY_OPT")"
    sleep 0.4
    IFS='|' read -r fired got_pane got_pid reason <<<"$out"

    assert_eq "A2: the helper reports it did NOT fire" "False" "$fired"
    assert_eq "A2: and hands back NO pane" "" "$got_pane"
    assert_eq "A2: and NO pid — nothing for a caller to adopt" "0" "$got_pid"
    assert_eq "A2: within one server generation that is a stamp mismatch" \
        "stamp-mismatch" "$reason"
    assert_eq "A2: the process was not replaced" "$before_pid" \
        "$(pane_fmt %0 '#{pane_pid}')"
    assert_eq "A2: the command was not replaced" "$before_cmd" \
        "$(pane_fmt %0 '#{pane_start_command}')"
    assert_eq "A2: the ready mark was NOT cleared" "1" \
        "$(pane_fmt %0 "#{${READY_OPT}}")"
    assert_eq "A2: no token was written" "" "$(pane_fmt %0 "#{${TOKEN_OPT}}")"
)

# ---------------------------------------------------------------------------
section "A3 — pane options do not survive a server restart"
# ---------------------------------------------------------------------------
# This is what makes the token trustworthy: a recycled `%N` on a new server
# CANNOT carry it, so a token that comes back was written by this dispatch.
(
    fresh_server "sleep 3005"
    tm set-option -p -t %0 "$FROZEN_OPT" "$RID"
    assert_eq "A3: the stamp is set before the restart" "$RID" \
        "$(pane_fmt %0 "#{${FROZEN_OPT}}")"
    srv_before="$(tm display-message -p '#{pid}')"

    fresh_server "sleep 3006"
    srv_after="$(tm display-message -p '#{pid}')"

    if [ "$srv_before" != "$srv_after" ]; then assert_record_pass; else
        assert_record_fail; echo "FAIL: A3: the server did not actually restart"
    fi
    assert_eq "A3: the SAME %N exists again on the new server" "%0" \
        "$(pane_fmt %0 '#{pane_id}')"
    assert_eq "A3: but it carries no stamp" "" "$(pane_fmt %0 "#{${FROZEN_OPT}}")"
)

# ---------------------------------------------------------------------------
section "A4 — ids are monotonic within a server, and restart at %0"
# ---------------------------------------------------------------------------
# The premise for "a server restart is the ONLY way a recorded %N can name a
# different pane". Without it the whole race analysis is wrong.
(
    fresh_server "sleep 3007"
    tm new-window -d "sleep 3008"
    sleep 0.3
    assert_eq "A4: the second pane is %1" "yes" \
        "$(pane_exists %1 && echo yes || echo no)"
    tm kill-window -t %1 2>/dev/null || true
    sleep 0.3
    tm new-window -d "sleep 3009"
    sleep 0.3
    assert_eq "A4: the killed %1 is NOT reused" "no" \
        "$(pane_exists %1 && echo yes || echo no)"
    assert_eq "A4: the next pane is %2" "yes" \
        "$(pane_exists %2 && echo yes || echo no)"

    fresh_server "sleep 3010"
    assert_eq "A4: a fresh server numbers from %0 again" "yes" \
        "$(pane_exists %0 && echo yes || echo no)"
)

# ---------------------------------------------------------------------------
section "A5 — tmux_quote carries a metacharacter-laden command intact"
# ---------------------------------------------------------------------------
# The nested command goes through tmux's OWN lexer inside `if-shell`, so this is
# the layer that breaks EVERY restore if it is wrong — not only the racy ones.
(
    fresh_server "sleep 3011"
    tm set-option -p -t %0 "$FROZEN_OPT" "$RID"
    marker="$FIXTURE_DIR/quoted.txt"
    # single quotes, double quotes, $, ; and > all in one command
    # The command writes BOTH a literal (proving the quoting survived) and the
    # two `-e` variables as the spawned process sees them (proving the env
    # delivery survived the if-shell nesting). One command, two facts, and the
    # file is the only source for either — nothing is asserted against a string
    # this test itself supplied.
    cmd="sh -c 'printf %s \"it works; V1=\$V1 V2=\$V2\" > $marker; sleep 3012'"

    out="$(drive %0 "$RID" "$cmd")"
    sleep 0.6
    IFS='|' read -r fired _ _ _ <<<"$out"

    assert_eq "A5: the quoted command was dispatched" "True" "$fired"
    assert_eq "A5: and the shell really ran it" "yes" \
        "$([ -s "$marker" ] && echo yes || echo no)"
    written="$(cat "$marker" 2>/dev/null)"
    assert_contains "A5: the quoted literal survived tmux's lexer" \
        "it works;" "$written"
    # The `-e` flags must survive the same wrapping (spike Case 3c measured four
    # on a bare respawn-pane; this proves they survive the if-shell nesting).
    assert_contains "A5: the first -e reached the process" "V1=one" "$written"
    assert_contains "A5: and so did the second" "V2=two" "$written"
)

# ===========================================================================
section "Part B — a REAL restart between the pre-read and the dispatch"
# ===========================================================================
# The race the token exists for, and the one no mock can prove. The driver is
# SIGSTOPped at the `respawn_dispatch` seam — after it has taken its `#{pid}`
# pre-read and before it dispatches — the server is restarted underneath it, the
# recorded %N is recreated holding an UNRELATED process, and only then is the
# driver resumed.
#
# Under the pid-delta inference this design rejects, the driver would come back
# `fired=True` naming that stranger's pane and pid, and a restore would go on to
# liveness-confirm somebody else's agent as its own.
(
    fresh_server "sleep 3013"
    tm set-option -p -t %0 "$FROZEN_OPT" "$RID"
    srv_before="$(tm display-message -p '#{pid}')"

    outfile="$FIXTURE_DIR/partb.out"
    AITASKS_TEST_MODE=1 AITASKS_FROZEN_PAUSE_AT=respawn_dispatch \
        "$PYTHON_BIN" "$DRIVER" "$PROJECT_DIR" %0 "$RID" "sleep 3014" "$READY_OPT" \
        > "$outfile" 2>&1 &
    driver=$!

    if wait_stopped "$driver"; then assert_record_pass; else
        assert_record_fail
        echo "FAIL: Part B: the driver never paused at respawn_dispatch"
    fi

    # The world moves while the driver is stopped: same socket, new server, and
    # %0 is handed to a process that has nothing to do with us.
    fresh_server "sleep 4242"
    srv_after="$(tm display-message -p '#{pid}')"
    marker_pid="$(pane_fmt %0 '#{pane_pid}')"
    assert_eq "Part B: the recorded %N was recreated" "%0" "$(pane_fmt %0 '#{pane_id}')"
    if [ "$srv_before" != "$srv_after" ]; then assert_record_pass; else
        assert_record_fail; echo "FAIL: Part B: the server did not restart"
    fi

    kill -CONT "$driver" 2>/dev/null || true
    wait "$driver" 2>/dev/null || true
    sleep 0.4

    IFS='|' read -r fired got_pane got_pid reason < "$outfile"
    assert_eq "Part B: the helper did NOT claim it fired" "False" "$fired"
    assert_eq "Part B: it handed back NO pane" "" "$got_pane"
    assert_eq "Part B: and NO pid — the stranger's is never adopted" "0" "$got_pid"
    assert_eq "Part B: and it named the restart" "server-restarted" "$reason"

    # THE POINT: the unrelated process is untouched.
    assert_eq "Part B: the stranger's process still holds the pane" "$marker_pid" \
        "$(pane_fmt %0 '#{pane_pid}')"
    assert_contains "Part B: still running ITS command, not ours" "4242" \
        "$(pane_fmt %0 '#{pane_start_command}')"
    assert_eq "Part B: and it was never stamped with our token" "" \
        "$(pane_fmt %0 "#{${TOKEN_OPT}}")"
)

# ===========================================================================
section "Summary"
# ===========================================================================
assert_counters_load
echo "Passed: $PASS / $TOTAL"
if [ "$FAIL" -eq 0 ]; then
    echo "ALL TESTS PASSED"
    exit 0
else
    echo "FAILED: $FAIL"
    exit 1
fi
