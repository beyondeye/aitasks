#!/usr/bin/env bash
# test_sync_holder_pane_live.sh - a sync deferral names the holder's pane and
# prompt state, and --require-waiting commits only for a waiting pane (t1725_4).
#
# Run: bash tests/test_sync_holder_pane_live.sh
#
# A real tmux pane on a private server stands in for the holding agent session.
# It redraws its screen from a file, so a case can switch it between an
# AskUserQuestion prompt and ordinary output. The lock is anchored to that pane's
# own pid, the way a real claim anchors to an agent launched as its pane's process.
#
# SOCKET CONTRACT, the part that makes these cases mean anything:
#   * tests/lib/sync_fixture.sh pins every sweep to a socket NOTHING serves unless
#     SYNC_FIXTURE_TMUX_SOCKET names another. Positive sweeps here go through
#     run_sync_live, which names THIS test's server; negative controls name
#     $NOSRV explicitly. A sweep that named neither would silently measure the
#     no-server default and only ever exercise refusal, so the footer greps this
#     file for one.
#   * require_isolated_tmux runs before the server starts, so TMUX_TMPDIR is
#     exported first and inherited by every run_sync subshell: both sides resolve
#     `-L $SOCK` to the same socket file.
#   * before each positive sweep the test asserts $SOCK lists the holder's pane;
#     each negative control asserts $NOSRV has no server.
#
#   P1/P2  the probe CLI, the clone's shipping copy run from outside the repo:
#          waiting -> waiting_claude_askuserquestion, plain -> active, one line,
#          empty stderr (the import-bootstrap pin through the real entry point)
#   S1     a deferred sweep's record carries tmux's own target for the pane and
#          waiting_claude_askuserquestion; the stderr line names both
#   S1c    CONTROL: the identical sweep via $NOSRV -> the same record with both
#          pane columns empty, and the stderr line back to its bare "(pid N)"
#   S2     plain screen -> the same pane, `active`
#   S3     post-phase pane_unresolvable_degrades_to_pid: a live lock whose pid is
#          in no pane (this test's shell) with the server reachable -> pid,
#          email and host filled, both pane columns empty, and the first stdout
#          line still a batch token
#   E1     the screen switches from waiting to plain between a deferred sync and
#          the --require-waiting retry -> holder_not_waiting (observed: active),
#          nothing committed, and the record carries the re-probed state
#   E2     screen left waiting -> committed
#   E2c    CONTROL: E2 via $NOSRV -> refused (observed: unresolvable)

set -uo pipefail

TEST_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_SCRIPT_DIR/.." && pwd)"
export PROJECT_DIR

PASS=0
FAIL=0
TOTAL=0

if ! command -v tmux >/dev/null 2>&1; then
    echo "SKIP: tmux not available"
    exit 0
fi

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
# Before any server exists: exports the private TMUX_TMPDIR that this test's
# server and every run_sync subshell both resolve `-L <name>` against.
# shellcheck source=lib/tmux_isolation.sh
. "$TEST_SCRIPT_DIR/lib/tmux_isolation.sh"
require_isolated_tmux
# shellcheck source=lib/sync_fixture.sh
. "$PROJECT_DIR/tests/lib/sync_fixture.sh"

# The AskUserQuestion footer is matched on its `·` and `↑/↓`. Read under a
# non-UTF-8 locale those come back as `_`, and no pane would ever read as waiting.
if [[ "$(locale charmap 2>/dev/null)" != "UTF-8" ]]; then
    export LC_ALL=C.UTF-8
fi

PY="$( . "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh" >/dev/null 2>&1 && resolve_python 2>/dev/null )"

SOCK="ait_syncpane_$$"
NOSRV="ait_syncpane_nosrv_$$"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/test_sync_pane_XXXXXX")"
SCREEN="$TMP/screen.txt"
: > "$SCREEN"

# sync_fixture.sh already owns the EXIT trap; chain it rather than replace it.
# shellcheck disable=SC2329  # invoked indirectly, by the EXIT trap below
cleanup() {
    tmux -L "$SOCK" kill-server 2>/dev/null || true
    rm -rf "$TMP"
    _sync_fixture_cleanup
}
trap cleanup EXIT

fail_setup() {
    echo "FAIL: $1"
    echo ""
    echo "Results: $PASS passed, $((FAIL + 1)) failed, $((TOTAL + 1)) total"
    echo "SOME TESTS FAILED"
    exit 1
}

[[ -n "$PY" ]] || fail_setup "no python resolved (lib/python_resolve.sh)"

# Advance origin/aitask-data from a second clone, so the local repo is behind.
# (Same helper as test_sync_deferral_and_quarantine.sh.)
advance_remote() {
    local tmpdir="$1"
    rm -rf "$tmpdir/pc2"
    git clone -q --branch aitask-data "$tmpdir/remote.git" "$tmpdir/pc2" 2>/dev/null
    (
        cd "$tmpdir/pc2" || exit 1
        git config user.email pc2@test.com
        git config user.name PC2
        git config commit.gpgsign false
        printf 'from pc2\n' >> aitasks/t30_gamma.md
        git add -A && git commit -q -m "pc2: advance data branch"
        git push -q origin aitask-data 2>/dev/null
    ) >/dev/null 2>&1
    (cd "$tmpdir/local" && git -C .aitask-data fetch -q origin 2>/dev/null)
}

# A fixture whose t10 is live-locked by <pid> as THIS user (class `self`) with a
# tracked edit, plus a t20 edit that gives the run a local commit to replay, and a
# remote that is ahead: the Test-1 shape of test_sync_deferral_and_quarantine.sh,
# which makes the run defer and emit its DEFERRED_FILE: records.
new_fixture() {
    local t; t="$(setup_repo)"
    plant_lock "$t" 10 "$(lock_yaml_live 10 testhost "$1")"
    set_userconfig_email "$t" other@x.com
    (cd "$t/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md \
                   && printf 'edit20\n' >> .aitask-data/aitasks/t20_beta.md)
    advance_remote "$t"
    echo "$t"
}

run_sync_live() { SYNC_FIXTURE_TMUX_SOCKET="$SOCK" run_sync "$@"; }

# records <tmpdir> <task> — that task's DEFERRED_FILE: records from the last run,
# read through the REAL parser, one per line, fields separated by \x1f and closed
# by an END sentinel, so an empty pane column can never shift the others.
records() {
    "$PY" - "$1/sync_stdout" "$2" <<'PYEOF'
import os
import sys
sys.path.insert(0, os.path.join(os.environ["PROJECT_DIR"], ".aitask-scripts", "lib"))
from sync_action_runner import parse_sync_output
with open(sys.argv[1], encoding="utf-8") as fh:
    result = parse_sync_output(fh.read())
want = sys.argv[2].lstrip("t")
for f in result.deferred_files:
    if str(f.task).lstrip("t") == want:
        print("\x1f".join(str(v) for v in (
            f.sub_reason, f.pid, f.email, f.host, f.pane, f.pane_state, "END")))
PYEOF
}
# Split the first record for <task> into r_* variables.
read_record() {
    local rec; rec="$(records "$1" "$2" | head -n1)"
    IFS=$'\x1f' read -r r_reason r_pid r_email r_host r_pane r_state r_end <<<"$rec"
    r_count="$(records "$1" "$2" | wc -l | tr -d ' ')"
}

assert_sock_has_pane() {
    local listed=no
    tmux -L "$SOCK" list-panes -a -F '#{pane_pid}' 2>/dev/null | grep -qx "$PANE_PID" && listed=yes
    assert_eq "$1: precondition - \$SOCK serves the holder's pane" "yes" "$listed"
}
assert_nosrv_empty() {
    local served=no
    tmux -L "$NOSRV" list-sessions >/dev/null 2>&1 && served=yes
    assert_eq "$1: precondition - no server answers on \$NOSRV" "no" "$served"
}

# --- The holder's pane ------------------------------------------------------
# Redraws only on change and in ONE write per frame, so a capture never lands
# between the clear and the content.
cat > "$TMP/render.sh" <<'RENDER'
last=""
while :; do
    cur="$(cat "$1" 2>/dev/null)"
    if [ "$cur" != "$last" ]; then
        printf '\033[H\033[2J%s' "$cur"
        last="$cur"
    fi
    sleep 0.1
done
RENDER

# `|` in the session name: the record's pane column must survive the %7C
# round-trip through the real parser.
tmux -L "$SOCK" new-session -d -s 'ait|t10' -x 100 -y 12 "sh '$TMP/render.sh' '$SCREEN'" 2>/dev/null

line=""
for _ in $(seq 1 50); do
    line="$(tmux -L "$SOCK" list-panes -a -F '#{pane_pid} #{pane_id} #{pane_height}' 2>/dev/null | head -1)"
    [[ -n "$line" ]] && break
    sleep 0.1
done
[[ -n "$line" ]] || fail_setup "could not start the holder's pane"
read -r PANE_PID PANE_ID PANE_H <<<"$line"
TARGET="$(tmux -L "$SOCK" list-panes -a -F '#{session_name}:#{window_id}.#{pane_id}' 2>/dev/null | head -1)"

ASK_LINE='Enter to select · ↑/↓ to navigate · Esc to cancel'
# set_screen <waiting|plain> — rewrite the screen, bottom-aligned (agent CLIs
# draw their footer on the last rows, and prompt detection reads only the
# bottom of a capture), then wait until the pane actually shows it.
set_screen() {
    local mode="$1" body want gone n i pad="" shown
    if [[ "$mode" == waiting ]]; then
        body=$'◆ Which base branch?\n  1. main\n  2. develop\n'"$ASK_LINE"
        want="$ASK_LINE"; gone="12 passed"
    else
        body=$'running the suite...\n  12 passed, 0 failed\n> '
        want="12 passed"; gone="Enter to select"
    fi
    n="$(printf '%s\n' "$body" | wc -l | tr -d ' ')"
    for ((i = n; i < PANE_H; i++)); do pad+=$'\n'; done
    printf '%s%s' "$pad" "$body" > "$SCREEN.tmp" && mv "$SCREEN.tmp" "$SCREEN"
    for i in $(seq 1 50); do
        shown="$(tmux -L "$SOCK" capture-pane -p -t "$PANE_ID" 2>/dev/null)"
        [[ "$shown" == *"$want"* && "$shown" != *"$gone"* ]] && return 0
        sleep 0.1
    done
    return 1
}

set +e

echo "=== sync deferral: the holder's pane and prompt state (t1725_4) ==="
echo ""

# --- P1/P2: the probe CLI through the shipping file -------------------------
echo "--- P1/P2: pane_state_probe.py, the clone's copy, from outside the repo ---"
TP="$(setup_repo)"
PROBE_CLONE="$TP/local/.aitask-scripts/lib/pane_state_probe.py"
assert_file_exists "P0. the fixture clone carries the probe" "$PROBE_CLONE"

set_screen waiting || fail_setup "the pane never showed the AskUserQuestion footer (UTF-8 locale?)"
(cd "$TMP" && AITASKS_TMUX_SOCKET="$SOCK" "$PY" "$PROBE_CLONE" "$PANE_ID" >"$TMP/p.out" 2>"$TMP/p.err"); rc=$?
assert_eq "P1a. exit 0" "0" "$rc"
assert_eq "P1b. exactly one line" "1" "$(wc -l < "$TMP/p.out" | tr -d ' ')"
assert_eq "P1c. a waiting pane reads as waiting" "waiting_claude_askuserquestion" "$(cat "$TMP/p.out")"
assert_eq "P1d. empty stderr: the monitor imports resolved" "" "$(cat "$TMP/p.err")"

set_screen plain || fail_setup "the pane never switched to plain output"
(cd "$TMP" && AITASKS_TMUX_SOCKET="$SOCK" "$PY" "$PROBE_CLONE" "$PANE_ID" >"$TMP/p.out" 2>"$TMP/p.err"); rc=$?
assert_eq "P2a. exit 0" "0" "$rc"
assert_eq "P2b. plain output reads as active" "active" "$(cat "$TMP/p.out")"
assert_eq "P2c. empty stderr" "" "$(cat "$TMP/p.err")"

# --- S1: a waiting holder ---------------------------------------------------
echo "--- S1: a waiting holder's record and stderr line ---"
T="$(new_fixture "$PANE_PID")"
set_screen waiting || fail_setup "S1: screen"
assert_sock_has_pane "S1"
run_sync_live "$T" > "$T/sync_stdout"
assert_eq "S1a. the run defers" "DEFERRED:protected_dirty" "$(head -n1 "$T/sync_stdout" | cut -d: -f1-2)"
read_record "$T" 10
assert_eq "S1b. t10 has exactly one record" "1" "$r_count"
assert_eq "S1c. sub-reason" "live_lock" "$r_reason"
assert_eq "S1d. pid" "$PANE_PID" "$r_pid"
assert_eq "S1e. pane = tmux's own target, '|' intact after the round-trip" "$TARGET" "$r_pane"
assert_eq "S1f. pane_state" "waiting_claude_askuserquestion" "$r_state"
assert_eq "S1g. the record is whole" "END" "$r_end"
assert_contains "S1h. stderr names the pane" "pane $TARGET" "$(sync_err "$T")"
assert_contains "S1i. stderr says it is waiting" "waiting on a prompt: claude_askuserquestion" "$(sync_err "$T")"

# --- S1c: control, no server ------------------------------------------------
echo "--- S1c: control - the identical sweep with no server reachable ---"
T="$(new_fixture "$PANE_PID")"
set_screen waiting || fail_setup "S1c: screen"
assert_nosrv_empty "S1c"
SYNC_FIXTURE_TMUX_SOCKET="$NOSRV" run_sync "$T" > "$T/sync_stdout"
read_record "$T" 10
assert_eq "S1c-a. sub-reason unchanged" "live_lock" "$r_reason"
assert_eq "S1c-b. pid still filled" "$PANE_PID" "$r_pid"
assert_eq "S1c-c. pane empty" "" "$r_pane"
assert_eq "S1c-d. pane_state empty" "" "$r_state"
assert_contains "S1c-e. stderr back to the bare pid" "live session on this host (pid $PANE_PID)" "$(sync_err "$T")"

# --- S2: an active holder ---------------------------------------------------
echo "--- S2: an active holder ---"
T="$(new_fixture "$PANE_PID")"
set_screen plain || fail_setup "S2: screen"
assert_sock_has_pane "S2"
run_sync_live "$T" > "$T/sync_stdout"
read_record "$T" 10
assert_eq "S2a. the same pane" "$TARGET" "$r_pane"
assert_eq "S2b. pane_state" "active" "$r_state"
assert_contains "S2c. stderr says it is running" "running — not at a prompt" "$(sync_err "$T")"

# --- S3: post-phase pane_unresolvable_degrades_to_pid -----------------------
echo "--- S3: a live holder in no pane degrades to a pid-only record ---"
T="$(new_fixture "$$")"
assert_sock_has_pane "S3"
run_sync_live "$T" > "$T/sync_stdout"
assert_contains_re "S3a. first stdout line is a batch token" '^DEFERRED:' "$(head -n1 "$T/sync_stdout")"
read_record "$T" 10
assert_eq "S3b. the record is still emitted" "1" "$r_count"
assert_eq "S3c. pid" "$$" "$r_pid"
assert_eq "S3d. email" "other@x.com" "$r_email"
assert_eq "S3e. host" "testhost" "$r_host"
assert_eq "S3f. pane empty" "" "$r_pane"
assert_eq "S3g. pane_state empty" "" "$r_state"

# --- E1: the screen changes between the snapshot and the retry --------------
echo "--- E1: --require-waiting re-probes, and refuses a holder that moved on ---"
T="$(new_fixture "$PANE_PID")"
set_screen waiting || fail_setup "E1: screen (waiting)"
assert_sock_has_pane "E1"
run_sync_live "$T" > "$T/sync_stdout"
read_record "$T" 10
assert_eq "E1a. the snapshot said waiting" "waiting_claude_askuserquestion" "$r_state"
set_screen plain || fail_setup "E1: screen (plain)"
assert_sock_has_pane "E1"
run_sync_live "$T" --commit-for-task 10 --require-waiting > "$T/sync_stdout"
assert_contains "E1b. refused on the fresh observation" "is not parked on a prompt (observed: active)" "$(sync_err "$T")"
assert_not_contains "E1c. nothing was committed for t10" "Auto-commit t10" "$(data_log "$T")"
read_record "$T" 10
assert_eq "E1d. the record says why" "holder_not_waiting" "$r_reason"
assert_eq "E1e. …with the pane it re-probed" "$TARGET" "$r_pane"
assert_eq "E1f. …and the state it observed" "active" "$r_state"

# --- E2: a holder still waiting ---------------------------------------------
echo "--- E2: --require-waiting commits for a holder parked on a prompt ---"
T="$(new_fixture "$PANE_PID")"
set_screen waiting || fail_setup "E2: screen"
assert_sock_has_pane "E2"
run_sync_live "$T" --commit-for-task 10 --require-waiting > "$T/sync_stdout"
assert_contains "E2a. t10 was committed on its behalf" "Auto-commit t10" "$(data_log "$T")"
assert_not_contains "E2b. and not refused" "is not parked on a prompt" "$(sync_err "$T")"

# --- E2c: control, no server ------------------------------------------------
echo "--- E2c: control - E2 with no server reachable ---"
T="$(new_fixture "$PANE_PID")"
set_screen waiting || fail_setup "E2c: screen"
assert_nosrv_empty "E2c"
SYNC_FIXTURE_TMUX_SOCKET="$NOSRV" run_sync "$T" --commit-for-task 10 --require-waiting > "$T/sync_stdout"
assert_contains "E2c-a. refused: nothing established" "is not parked on a prompt (observed: unresolvable)" "$(sync_err "$T")"
assert_not_contains "E2c-b. nothing committed" "Auto-commit t10" "$(data_log "$T")"

# --- The socket contract, enforced on this file ------------------------------
bare="$(grep -nE '(^|[;&|[:space:](])run_sync[[:space:]]' "${BASH_SOURCE[0]}" \
        | grep -vE '^[0-9]+:[[:space:]]*#' \
        | grep -v 'SYNC_FIXTURE_TMUX_SOCKET=')"
assert_eq "every sweep in this file names its socket" "" "$bare"

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ "$FAIL" -eq 0 ]]; then
    echo "ALL TESTS PASSED"
    exit 0
fi
echo "SOME TESTS FAILED"
exit 1
