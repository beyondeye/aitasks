#!/usr/bin/env bash
# test_live_endpoint_tmux_live.sh — LIVE isolated-tmux proof of the resolver's
# PID→pane correlation (t1657_4).
#
# `tests/test_live_endpoint_degradation.sh` pins every `LIVE_NONE` reason code
# without tmux. What it cannot answer is the one thing the whole task exists for:
# does a task id actually resolve to the RIGHT live pane, and does the target
# string it emits match how the agent-session listing renders that pane? A
# format slip there produces a target that looks correct and joins to nothing —
# every send silently reports "no session match", and no unit test notices.
#
# THE ORDERING TRAP THIS FILE EXISTS TO AVOID. Claiming a task writes only the
# lock; `implemented_with` is written later, by Agent Attribution at Step 7. The
# resolver checks the agent family (step 5) BEFORE it attempts PID→pane
# correlation (step 6). So a freshly-claimed fixture task returns
# `LIVE_NONE:agent_unknown` and the correlator is never reached — a positive case
# built on a bare claim would pass over a completely broken correlator. Case 1
# therefore SEEDS `implemented_with` first, and Case 2 is the control that proves
# the short-circuit is real rather than assumed.
#
# What this asserts, against a throwaway tmux server:
#   1. A task claimed INSIDE a pane, with `implemented_with` seeded, resolves to
#      THAT pane — pane id and pid both — and the emitted target equals what tmux
#      itself renders for `#{session_name}:#{window_id}.#{pane_id}`.
#   2. ORDERING CONTROL: the identical setup with `implemented_with` cleared
#      answers `agent_unknown`, so Case 1's success is attributable to the seed
#      and not to the pane being incidentally findable.
#   3. CORRELATION NEGATIVE CONTROL: the identical seeded run with only the
#      gateway socket repointed at a server that does not exist answers
#      `no_pane`. Without it, Case 1 could pass vacuously.
#   4. The ancestor-walk fallback: a lock anchored to a DESCENDANT of the pane
#      process (the `AIT_AGENT_PID` rung) still resolves to the pane.
#
# Isolation: creates its own server on a private `-L` socket and kills it in a
# trap. `require_isolated_tmux` additionally detaches this process from any
# inherited server, so a stray call cannot reach the user's session. This test
# arms no hooks and kills no shared server, so it does NOT need
# `require_clean_ait_server`.
#
# Not part of tests/run_all_python_tests.sh (a bash test, deliberately opt-in).
#
# Run: bash tests/test_live_endpoint_tmux_live.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

if ! command -v tmux >/dev/null 2>&1; then
    echo "SKIP: tmux not available"
    exit 0
fi

# shellcheck source=lib/tmux_isolation.sh
. "$SCRIPT_DIR/lib/tmux_isolation.sh"
require_isolated_tmux

# The override must be absent: the pane rung is what is being measured.
unset AIT_AGENT_PID

RESOLVE="$PROJECT_DIR/.aitask-scripts/aitask_live_endpoint.sh"

AITASKS_LOCK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/test_live_ep_tmux_lockbase_XXXXXX")"
export AITASKS_LOCK_DIR

SOCK="ait_liveep_$$"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/test_live_ep_tmux_XXXXXX")"
# shellcheck disable=SC2329  # invoked indirectly, by the EXIT trap below
cleanup() {
    tmux -L "$SOCK" kill-server 2>/dev/null || true
    rm -rf "$TMP" "$AITASKS_LOCK_DIR"
}
trap cleanup EXIT

# --- fixture ---------------------------------------------------------------
#
# The real hostname is used on both sides: the claim records `$(hostname)` and
# the resolver compares against `$(hostname)`. Faking it would only test the
# fixture's PATH shim.

REMOTE="$TMP/remote.git"
git init -q --bare -b main "$REMOTE"
DATA="$TMP/data"
git clone -q "$REMOTE" "$DATA" 2>/dev/null
mkdir -p "$DATA/aitasks/metadata"
git -C "$DATA" config user.email t@example.com
git -C "$DATA" config user.name Test

write_task() {   # <id> <implemented_with, or "">
    local id="$1" impl="${2:-}"
    {
        echo "---"
        echo "status: Implementing"
        [[ -n "$impl" ]] && echo "implemented_with: $impl"
        echo "---"
        echo "Task t${id} for the live endpoint test."
    } > "$DATA/aitasks/t${id}_live.md"
}
write_task 1 ""
git -C "$DATA" add -A && git -C "$DATA" commit -qm tasks
git -C "$DATA" push -q origin main 2>/dev/null || true
( cd "$DATA" && "$PROJECT_DIR/.aitask-scripts/aitask_lock.sh" --init ) >/dev/null 2>&1 || true

run_resolve() { ( cd "$DATA" && AITASKS_TMUX_SOCKET="$SOCK" "$RESOLVE" "$@" ); }

wait_for_file() {
    local f="$1" _i
    for _i in $(seq 1 120); do
        [[ -s "$f" ]] && return 0
        sleep 0.25
    done
    return 1
}

set +e

echo "=== live endpoint: real pane correlation (t1657_4) ==="
echo ""

# --- Start a pane that claims t1 and then stays alive ----------------------
#
# The claim runs as the pane's OWN command, so tmux — not the fixture — supplies
# $TMUX and $TMUX_PANE, and the lock anchors to the pane process by construction
# (get_session_anchor_pid rung 2). Setting those by hand would test the fixture.

claim_cmd="cd '$DATA' && AITASKS_LOCK_DIR='$AITASKS_LOCK_DIR'"
claim_cmd="$claim_cmd AITASKS_TMUX_SOCKET='$SOCK'"
claim_cmd="$claim_cmd '$PROJECT_DIR/.aitask-scripts/aitask_pick_own.sh' 1 --email 'alice@test.com'"
claim_cmd="$claim_cmd > claim.out 2>&1; echo \$? > claim.rc; sleep 300"

tmux -L "$SOCK" new-session -d -x 80 -y 10 -n endpoint "$claim_cmd" 2>/dev/null

PANE_PID=""
for _ in $(seq 1 30); do
    PANE_PID=$(tmux -L "$SOCK" list-panes -F '#{pane_pid}' 2>/dev/null | head -1)
    [[ -n "$PANE_PID" ]] && break
    sleep 0.2
done

TOTAL=$((TOTAL + 1))
if [[ -n "$PANE_PID" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: could not start a test pane"
    echo ""
    echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
    echo "SOME TESTS FAILED"
    exit 1
fi

if ! wait_for_file "$DATA/claim.rc"; then
    TOTAL=$((TOTAL + 1)); FAIL=$((FAIL + 1))
    echo "FAIL: in-pane claim did not finish within the budget"
    echo ""
    echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
    echo "SOME TESTS FAILED"
    exit 1
fi

assert_contains "0a. in-pane claim succeeded" "OWNED:1" "$(cat "$DATA/claim.out" 2>/dev/null)"

# Independent ground truth for the target string, read straight from tmux rather
# than rebuilt from the resolver's own format. `#{window_id}` already carries its
# own '@' — the agent-session listing renders exactly this, which is why the
# resolver must not use `@#{window_index}` (a different number for the same pane).
PANE_ID="$(tmux -L "$SOCK" list-panes -a -F '#{pane_id}' 2>/dev/null | head -1)"
EXPECT_TARGET="$(tmux -L "$SOCK" list-panes -a \
    -F '#{session_name}:#{window_id}.#{pane_id}' 2>/dev/null | head -1)"

# --- Case 2 first: the ORDERING CONTROL ------------------------------------
#
# Run before the seed, while the task is in exactly the state a real claim leaves
# it: locked, Implementing, and `implemented_with` still empty because Step 7 has
# not run. If this did NOT answer agent_unknown, Case 1's pass would prove
# nothing about the seed.

echo "--- Case 2: ordering control (implemented_with still empty) ---"
out="$(run_resolve 1 2>/dev/null)"; rc=$?
assert_eq "2a. a freshly claimed task short-circuits at the agent gate" \
    "LIVE_NONE:agent_unknown" "$out"
assert_eq "2b. …and that is a successful resolution" "0" "$rc"

# --- Case 1: the positive -------------------------------------------------

echo "--- Case 1: seeded implemented_with resolves to THIS pane ---"
write_task 1 "claudecode/opus5"

out="$(run_resolve 1 2>/dev/null)"; rc=$?
assert_eq "1a. exit 0" "0" "$rc"
assert_contains "1b. resolves to a live pane" "LIVE_PANE:" "$out"
assert_eq "1c. the WHOLE line, built from tmux's own rendering" \
    "LIVE_PANE:${PANE_ID}|${EXPECT_TARGET}|${PANE_PID}|agent=claudecode" "$out"

# Stated separately so a regression reads as "wrong pane" rather than a bare
# string inequality.
got_pane="${out#LIVE_PANE:}"; got_pane="${got_pane%%|*}"
assert_eq "1d. the pane id is THIS pane's" "$PANE_ID" "$got_pane"
got_target="${out#LIVE_PANE:*|}"; got_target="${got_target%%|*}"
assert_eq "1e. the target is session:<window_id>.<pane_id>" "$EXPECT_TARGET" "$got_target"

# The join key the adapter uses must be present in the target, or the adapter
# cannot match a listing row against it at all.
assert_contains "1f. the target ends in the pane id (the adapter's join key)" \
    ".$PANE_ID" "$got_target"

# Shape pin (mitigation `diagnosable_no_session_match`). 1c/1e compare against
# tmux's own rendering, which moves WITH tmux; this pins the literal shape the
# adapter's join depends on, so a change in either direction fails here loudly
# instead of turning every send into a silent "no session match".
assert_contains_re "1g. the target has the shape <session>:@<n>.%<n>" \
    '^[^:]+:@[0-9]+\.%[0-9]+$' "$got_target"

# --- Case 3: CORRELATION NEGATIVE CONTROL ---------------------------------
#
# Identical to Case 1 in every respect but one: the gateway is pointed at a
# server that does not exist, so no pane map can be built. Without this, Case 1
# could be passing for an incidental reason.

echo "--- Case 3: negative control (gateway socket repointed) ---"
out="$( cd "$DATA" && AITASKS_TMUX_SOCKET="ait_nonexistent_$$" "$RESOLVE" 1 2>/dev/null )"
assert_eq "3a. unreachable gateway => no_pane, not a wrong pane" \
    "LIVE_NONE:no_pane" "$out"

# --- Case 4: the ancestor-walk fallback -----------------------------------
#
# The framework's default rung anchors a lock to the pane process itself, which
# hits the pane map directly. Rung 1 (`AIT_AGENT_PID`) can name a DESCENDANT of
# the pane instead, and that must still resolve — otherwise every launcher that
# starts an agent under a wrapper silently loses live delivery.
#
# A real descendant of the live pane is spawned, and a lock is forged onto it.

echo "--- Case 4: ancestor walk from a descendant of the pane ---"
# A new window whose pane command is a wrapper shell: the wrapper IS the pane
# process, and the `sleep` it backgrounds is a genuine descendant. Anchoring the
# lock to the descendant is what forces the walk to make a real hop.
tmux -L "$SOCK" new-window -d -n walk \
    "bash -c 'sleep 300 & echo \$! > \"$DATA/child.pid\"; wait'" 2>/dev/null

if wait_for_file "$DATA/child.pid"; then
    CHILD_PID="$(cat "$DATA/child.pid")"
    # Address the walk window by NAME, not by list position — a positional pick
    # would silently follow whichever pane happened to sort last.
    walk_pane_pid="$(tmux -L "$SOCK" list-panes -a \
        -F '#{window_name} #{pane_pid}' 2>/dev/null \
        | awk '$1 == "walk" { print $2; exit }')"
    walk_pane_id="$(tmux -L "$SOCK" list-panes -a \
        -F '#{window_name} #{pane_id}' 2>/dev/null \
        | awk '$1 == "walk" { print $2; exit }')"

    # shellcheck source=../.aitask-scripts/lib/pid_anchor.sh
    . "$PROJECT_DIR/.aitask-scripts/lib/pid_anchor.sh"
    write_task 2 "claudecode/opus5"
    (
        cd "$DATA" || exit 1
        yaml="task_id: 2
locked_by: alice@test.com
locked_at: 2026-09-06 09:00
hostname: $(hostname)
pid: $CHILD_PID
pid_starttime: $(get_pid_starttime "$CHILD_PID")
pid_starttime_kind: $(get_pid_starttime_kind "$CHILD_PID")
"
        git fetch -q origin aitask-locks 2>/dev/null || true
        parent="$(git rev-parse origin/aitask-locks 2>/dev/null || true)"
        blob="$(printf '%s' "$yaml" | git hash-object -w --stdin)"
        newtree="$(
            {
                [[ -n "$parent" ]] && git ls-tree origin/aitask-locks \
                    | grep -v "$(printf '\t')t2_lock.yaml\$"
                printf '100644 blob %s\tt2_lock.yaml\n' "$blob"
            } | git mktree
        )"
        if [[ -n "$parent" ]]; then
            commit="$(echo forge | git commit-tree "$newtree" -p "$parent")"
        else
            commit="$(echo forge | git commit-tree "$newtree")"
        fi
        git push -q --force origin "$commit:refs/heads/aitask-locks"
    )

    out="$(run_resolve 2 2>/dev/null)"
    assert_contains "4a. a descendant-anchored lock still resolves to a pane" \
        "LIVE_PANE:" "$out"
    assert_contains "4b. …and to the pane that OWNS that descendant" \
        "LIVE_PANE:${walk_pane_id}|" "$out"
    assert_contains "4c. …reporting the recorded anchor pid, not the pane's" \
        "|${CHILD_PID}|" "$out"
    TOTAL=$((TOTAL + 1))
    if [[ "$CHILD_PID" != "$walk_pane_pid" ]]; then
        PASS=$((PASS + 1))   # the walk really had a hop to make
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: 4d. the descendant IS the pane process — the walk was not exercised"
    fi
else
    TOTAL=$((TOTAL + 1)); FAIL=$((FAIL + 1))
    echo "FAIL: 4. could not spawn a descendant inside a pane"
fi

# --- summary ---------------------------------------------------------------

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ "$FAIL" -eq 0 ]]; then
    echo "ALL TESTS PASSED"
    exit 0
fi
echo "SOME TESTS FAILED"
exit 1
