#!/usr/bin/env bash
# test_lock_live_holder_gate.sh - Tests for the acquire-time liveness gate (t1466).
#
# t1465 made the lock's `pid:` name the agent SESSION and made the liveness
# verdict three-valued. It stopped there: acquisition itself was still ungated,
# so `lock_task()`'s same-email refresh branch handed a task held by a LIVE
# second session straight to whoever asked last, silently. Two /aitask-pick
# panes owned one task and duplicated its work.
#
# This file pins the gate that closes it. The contract under test, for a lock
# on the SAME host under the SAME email:
#
#   this session's own anchor  -> refreshed silently (unchanged)
#   provably dead              -> acquired, RECLAIM_CRASH (unchanged)
#   provably alive             -> REFUSED before anything is written, exit 13
#   recorded but undecidable   -> REFUSED before anything is written, exit 14
#   never recorded ("-"/"0")   -> acquired, RECLAIM_STATUS (unchanged)
#
# The last row is load-bearing, not an oversight: a lock that never named a
# session has nothing to verify, and refusing it would bar every pre-anchor
# lock and every claim made outside tmux from ever being resumed.
#
# Both refusals are proven to be refusals of the ACQUISITION, not after-the-fact
# signals — the lock file and the task file must both come out untouched. That
# is what makes the headless lane (aitask-pickrem, which parses no RECLAIM_*
# signal at all) safe by construction rather than by parsing.
#
# Every anchor here is driven through the documented AIT_AGENT_PID seam against
# real `sleep` processes, so "alive" and "dead" are facts about this machine
# rather than fixture decoration. Test 2 is the positive control.
#
# Run: bash tests/test_lock_live_holder_gate.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"

PASS=0
FAIL=0
TOTAL=0

# Shared core helpers (assert_eq, assert_contains, …) live in tests/lib/asserts.sh.
. "$PROJECT_DIR/tests/lib/asserts.sh"

# Set up paired bare+local repo, copy framework files, init lock branch.
setup_paired_repos() {
    local tmpdir
    tmpdir="$(mktemp -d)"

    local remote_dir="$tmpdir/remote.git"
    git init --bare --quiet "$remote_dir"

    local local_dir="$tmpdir/local"
    git clone --quiet "$remote_dir" "$local_dir"
    (
        cd "$local_dir"
        git config user.email "test@test.com"
        git config user.name "Test"

        mkdir -p aitasks/archived aitasks/metadata aiplans bin

        cat > aitasks/t1_test_task.md <<'TASK'
---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: []
created_at: 2026-01-01 00:00
updated_at: 2026-01-01 00:00
---

Test task for the acquire-time liveness gate.
TASK

        # Hostname shim (TEST_HOSTNAME env override).
        cat > bin/hostname <<'SH'
#!/usr/bin/env bash
echo "${TEST_HOSTNAME:-unknown-host}"
SH
        chmod +x bin/hostname

        setup_fake_aitask_repo "$PWD"
        cp "$PROJECT_DIR/.aitask-scripts/aitask_lock.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_pick_own.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/lib/pid_anchor.sh" .aitask-scripts/lib/
        cp "$PROJECT_DIR/ait" . 2>/dev/null || true
        chmod +x .aitask-scripts/*.sh ait 2>/dev/null || true

        git add -A
        git commit -m "Initial setup" --quiet
        git push --quiet 2>/dev/null
    )

    echo "$tmpdir"
}

# Init the aitask-locks branch on origin.
init_lock_branch() {
    local tmpdir="$1" host="${2:-pc-A}"
    (cd "$tmpdir/local" && PATH="$tmpdir/local/bin:$PATH" TEST_HOSTNAME="$host" \
        ./.aitask-scripts/aitask_lock.sh --init >/dev/null 2>&1)
}

# Plant a fake lock YAML on origin/aitask-locks, bypassing the lock script.
plant_lock() {
    local tmpdir="$1" task_id="$2" yaml="$3"
    (
        cd "$tmpdir/local"
        git fetch origin aitask-locks --quiet 2>/dev/null
        local parent_hash current_tree_hash blob_hash new_tree_hash commit_hash
        parent_hash=$(git rev-parse origin/aitask-locks)
        current_tree_hash=$(git rev-parse "origin/aitask-locks^{tree}")
        blob_hash=$(echo "$yaml" | git hash-object -w --stdin)
        new_tree_hash=$( {
            git ls-tree "$current_tree_hash" | grep -v "	t${task_id}_lock\.yaml$" || true
            printf "100644 blob %s\tt%s_lock.yaml\n" "$blob_hash" "$task_id"
        } | git mktree )
        commit_hash=$(echo "test: plant lock for t$task_id" | \
            git commit-tree "$new_tree_hash" -p "$parent_hash")
        git push --quiet origin "$commit_hash:refs/heads/aitask-locks" 2>/dev/null
    )
}

# Read one field out of the lock YAML on origin/aitask-locks.
lock_field() {
    local tmpdir="$1" task_id="$2" key="$3"
    (cd "$tmpdir/local" && git fetch origin aitask-locks --quiet 2>/dev/null \
        && git show "origin/aitask-locks:t${task_id}_lock.yaml" 2>/dev/null) \
        | awk -v k="^${key}:" '$0 ~ k { sub(/^[^:]*: */, ""); print; exit }'
}

# Content fingerprint of the task file — the "was anything claimed?" probe.
task_file_hash() {
    local tmpdir="$1"
    (cd "$tmpdir/local" && git hash-object aitasks/t1_test_task.md)
}

# Run a real claim through aitask_pick_own.sh.
#   run_claim <tmpdir> <task_id> <hostname> [VAR=value ...] [-- <extra args>]
#
# The environment is pinned rather than inherited: AIT_AGENT_PID/TMUX/TMUX_PANE
# are cleared first, so a runner that happens to sit inside a tmux pane cannot
# quietly supply an anchor and make a "different session" read as self. `env`
# applies -u before the assignments, so a caller-supplied AIT_AGENT_PID still
# wins.
run_claim() {
    local tmpdir="$1" task_id="$2" host="$3"; shift 3
    local envs=() args=()
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --) shift; args=("$@"); break ;;
            *)  envs+=("$1"); shift ;;
        esac
    done
    (cd "$tmpdir/local" && env -u AIT_AGENT_PID -u TMUX -u TMUX_PANE \
        "PATH=$tmpdir/local/bin:$PATH" "TEST_HOSTNAME=$host" "${envs[@]}" \
        ./.aitask-scripts/aitask_pick_own.sh "$task_id" \
        --email "alice@test.com" "${args[@]}" 2>&1)
}

# Long-lived stand-in for an agent session:
#
#     sleep 300 & SESSION_X=$!
#
# Deliberately NOT wrapped in a helper that returns the pid via command
# substitution: the backgrounded job would inherit the substitution's pipe and
# hold it open for its whole lifetime, so `$(start_session)` never returns. It
# also has to be a direct child of THIS shell, because stop_session must be
# able to `wait` for it — an unreaped zombie still has a /proc entry and answers
# `kill -0`, so it would read as ALIVE and quietly invalidate every "dead"
# assertion below.

# Kill a session stand-in AND reap it, so its pid becomes genuinely absent.
stop_session() {
    kill "$1" 2>/dev/null || true
    wait "$1" 2>/dev/null || true
}

set +e

# The anchor lib itself, for the fixture's own liveness assertions.
# shellcheck source=../.aitask-scripts/lib/pid_anchor.sh
. "$PROJECT_DIR/.aitask-scripts/lib/pid_anchor.sh"

echo "=== Lock Acquire-Time Liveness Gate Tests (t1466) ==="
echo ""

# =====================================================================
# Tests 1-4: one fixture, one live "session A", the full verdict ladder.
# =====================================================================

TMPDIR_1="$(setup_paired_repos)"
init_lock_branch "$TMPDIR_1" pc-A

sleep 300 >/dev/null 2>&1 & SESSION_A=$!
out_a=$(run_claim "$TMPDIR_1" 1 pc-A "AIT_AGENT_PID=$SESSION_A")
assert_contains "Session A claims the task" "OWNED:1" "$out_a"
assert_eq "Lock is anchored to session A" "$SESSION_A" "$(lock_field "$TMPDIR_1" 1 pid)"

# The fixture must be telling the truth about A before anything is asserted
# about the gate: a holder that already read as dead would make Test 1 pass for
# entirely the wrong reason.
assert_eq "Fixture check: session A reads as ALIVE" "alive" \
    "$(lock_holder_liveness "$(lock_field "$TMPDIR_1" 1 pid)" \
                            "$(lock_field "$TMPDIR_1" 1 pid_starttime)" \
                            "$(lock_field "$TMPDIR_1" 1 pid_starttime_kind)")"

# --- Test 1: the acceptance criterion — a live holder is not taken over ---
echo "--- Test 1: second session vs. a provably LIVE holder → refused ---"

hash_before_1=$(task_file_hash "$TMPDIR_1")
sleep 300 >/dev/null 2>&1 & SESSION_B=$!
out1=$(run_claim "$TMPDIR_1" 1 pc-A "AIT_AGENT_PID=$SESSION_B")
exit1=$?

assert_eq "Claim against a live holder exits non-zero" "1" "$exit1"
assert_contains "Emits LOCK_LIVE_HOLDER" "LOCK_LIVE_HOLDER:alice@test.com" "$out1"
assert_contains "LOCK_LIVE_HOLDER names the holding pid" "|${SESSION_A}" "$out1"
assert_not_contains "Nothing was claimed (no OWNED)" "OWNED:" "$out1"
assert_not_contains "A live holder is never called a crash" "RECLAIM_CRASH" "$out1"

# The refusal must precede every write, not undo them afterwards.
assert_eq "Lock still belongs to session A" "$SESSION_A" "$(lock_field "$TMPDIR_1" 1 pid)"
assert_eq "Task file was not touched" "$hash_before_1" "$(task_file_hash "$TMPDIR_1")"

# --- Test 2: positive control — the same claim succeeds once A dies ---
echo "--- Test 2: positive control — holder dies, claim proceeds ---"

stop_session "$SESSION_A"
assert_eq "Fixture check: session A now reads as DEAD" "dead" \
    "$(lock_holder_liveness "$(lock_field "$TMPDIR_1" 1 pid)" \
                            "$(lock_field "$TMPDIR_1" 1 pid_starttime)" \
                            "$(lock_field "$TMPDIR_1" 1 pid_starttime_kind)")"

out2=$(run_claim "$TMPDIR_1" 1 pc-A "AIT_AGENT_PID=$SESSION_B")
exit2=$?

assert_eq "Dead-holder claim exits 0" "0" "$exit2"
assert_contains "Dead holder → claim proceeds" "OWNED:1" "$out2"
assert_contains "Dead holder → RECLAIM_CRASH" "RECLAIM_CRASH:" "$out2"
assert_not_contains "Dead holder is not a live-holder refusal" "LOCK_LIVE_HOLDER" "$out2"

# --- Test 3: this session's own lock is still refreshed silently ---
echo "--- Test 3: self re-claim refreshes silently ---"

# Session B now holds the lock and is alive. Without a self-exemption the gate
# would refuse B its own lock — which is the Step 7 ownership guard, an in-pane
# re-pick and every in-flight resume.
assert_eq "Fixture check: the lock is now B's, and B is alive" "alive" \
    "$(lock_holder_liveness "$(lock_field "$TMPDIR_1" 1 pid)" \
                            "$(lock_field "$TMPDIR_1" 1 pid_starttime)" \
                            "$(lock_field "$TMPDIR_1" 1 pid_starttime_kind)")"

out3=$(run_claim "$TMPDIR_1" 1 pc-A "AIT_AGENT_PID=$SESSION_B")
exit3=$?

assert_eq "Self re-claim exits 0" "0" "$exit3"
assert_contains "Self re-claim succeeds" "OWNED:1" "$out3"
assert_not_contains "Self re-claim is not refused" "LOCK_LIVE_HOLDER" "$out3"
assert_not_contains "Self re-claim is not undecidable" "LOCK_UNVERIFIABLE_HOLDER" "$out3"

# --- Test 4: --force overrides a live holder, and asks only once ---
echo "--- Test 4: --force takes the lock from a live holder ---"

sleep 300 >/dev/null 2>&1 & SESSION_C=$!
out4=$(run_claim "$TMPDIR_1" 1 pc-A "AIT_AGENT_PID=$SESSION_C" -- --force)
exit4=$?

assert_eq "Forced claim exits 0" "0" "$exit4"
assert_contains "Forced claim reports the takeover" "FORCE_UNLOCKED:" "$out4"
assert_contains "Forced claim succeeds" "OWNED:1" "$out4"
assert_eq "Lock is re-anchored to the forcing session" \
    "$SESSION_C" "$(lock_field "$TMPDIR_1" 1 pid)"
# The user has just confirmed the takeover. Re-emitting a reclaim signal here
# would make task-workflow immediately ask "reclaim and continue?" for the
# decision they just made.
assert_not_contains "No reclaim prompt after a confirmed force" "RECLAIM_" "$out4"

stop_session "$SESSION_B"
stop_session "$SESSION_C"
rm -rf "$TMPDIR_1"

# --- Test 5: cross-host is not gated (it has its own confirmation path) ---
echo "--- Test 5: cross-host re-claim is unaffected ---"

TMPDIR_5="$(setup_paired_repos)"
init_lock_branch "$TMPDIR_5" pc-A

sleep 300 >/dev/null 2>&1 & SESSION_5=$!
run_claim "$TMPDIR_5" 1 pc-A "AIT_AGENT_PID=$SESSION_5" >/dev/null

# Same live anchor, different host. The PID is meaningless on pc-B, so the gate
# must stay out of the way and leave this to LOCK_RECLAIM.
sleep 300 >/dev/null 2>&1 & SESSION_5B=$!
out5=$(run_claim "$TMPDIR_5" 1 pc-B "AIT_AGENT_PID=$SESSION_5B")
exit5=$?

assert_eq "Cross-host claim exits 0" "0" "$exit5"
assert_contains "Cross-host claim succeeds" "OWNED:1" "$out5"
assert_contains "Cross-host emits LOCK_RECLAIM" "LOCK_RECLAIM:pc-A" "$out5"
assert_not_contains "Cross-host is not gated on the foreign pid" "LOCK_LIVE_HOLDER" "$out5"
assert_not_contains "Cross-host is not gated as undecidable" "LOCK_UNVERIFIABLE_HOLDER" "$out5"

stop_session "$SESSION_5"
stop_session "$SESSION_5B"
rm -rf "$TMPDIR_5"

# --- Test 6: "cannot tell" is its own outcome ---
echo "--- Test 6: undecidable holder → its own refusal ---"

TMPDIR_6="$(setup_paired_repos)"
init_lock_branch "$TMPDIR_6" pc-A

sleep 300 >/dev/null 2>&1 & SESSION_6=$!
sleep 300 >/dev/null 2>&1 & SESSION_6B=$!

# A live process with no identity token: it exists, but nothing proves it is
# the process the lock recorded rather than a recycled PID. Neither alive nor
# dead — and the one thing it must not do is quietly hand over the lock.
plant_lock "$TMPDIR_6" 1 "task_id: 1
locked_by: alice@test.com
locked_at: 2026-01-01 00:00
hostname: pc-A
pid: $SESSION_6
pid_starttime: -"

assert_eq "Fixture check: untokened live pid reads as UNKNOWN" "unknown" \
    "$(lock_holder_liveness "$SESSION_6" "-" proc)"

hash_before_6=$(task_file_hash "$TMPDIR_6")
out6=$(run_claim "$TMPDIR_6" 1 pc-A "AIT_AGENT_PID=$SESSION_6B")
exit6=$?

assert_eq "Undecidable holder exits non-zero" "1" "$exit6"
assert_contains "Emits LOCK_UNVERIFIABLE_HOLDER" "LOCK_UNVERIFIABLE_HOLDER:alice@test.com" "$out6"
assert_contains "Names the undecidable pid" "|${SESSION_6}" "$out6"
assert_not_contains "Nothing was claimed" "OWNED:" "$out6"
assert_not_contains "Undecidable is not reported as alive" "LOCK_LIVE_HOLDER" "$out6"
assert_not_contains "Undecidable is not reported as a crash" "RECLAIM_CRASH" "$out6"
assert_eq "Task file was not touched" "$hash_before_6" "$(task_file_hash "$TMPDIR_6")"

# The weak-token variant reaches the same outcome by a different route: the
# token matches, but a one-second-resolution `ps` token cannot exclude a PID
# recycled within that second. Linux has both token sources, so the dispatch is
# plantable here even though it only occurs natively on BSD/macOS.
if [[ "$(uname)" == "Linux" ]]; then
    ps_tok_6=$(_pid_starttime_ps "$SESSION_6")
    plant_lock "$TMPDIR_6" 1 "task_id: 1
locked_by: alice@test.com
locked_at: 2026-01-01 00:00
hostname: pc-A
pid: $SESSION_6
pid_starttime: $ps_tok_6
pid_starttime_kind: ps"

    out6b=$(run_claim "$TMPDIR_6" 1 pc-A "AIT_AGENT_PID=$SESSION_6B")
    assert_contains "Weak-token holder → LOCK_UNVERIFIABLE_HOLDER" \
        "LOCK_UNVERIFIABLE_HOLDER:" "$out6b"
    assert_not_contains "Weak token cannot license a live-holder verdict" \
        "LOCK_LIVE_HOLDER" "$out6b"
else
    echo "  (weak-token variant skipped on non-Linux: needs both token sources)"
fi

stop_session "$SESSION_6"
stop_session "$SESSION_6B"
rm -rf "$TMPDIR_6"

# --- Test 7: a lock that never named a session still acquires ---
echo "--- Test 7: no recorded anchor → unchanged, still acquires ---"

# This is the split the gate depends on. "Undecidable" (Test 6) is a lock that
# NAMED a session we cannot resolve. A lock carrying "-" or "0" named nothing
# at all — a pre-anchor lock, or a claim made outside tmux — so there is no
# holder to verify. Refusing those would make every such task unresumable
# without --force, which is a far bigger breakage than the one being fixed.
TMPDIR_7="$(setup_paired_repos)"
init_lock_branch "$TMPDIR_7" pc-A

for sentinel in "-" "0"; do
    (
        cd "$TMPDIR_7/local"
        cat > aitasks/t1_test_task.md <<'TASK'
---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: []
assigned_to: alice@test.com
created_at: 2026-01-01 00:00
updated_at: 2026-01-01 00:00
---

Test task already in Implementing status.
TASK
        git add -A && git commit -m "Pre-set to Implementing" --quiet
        git push --quiet 2>/dev/null
    )
    plant_lock "$TMPDIR_7" 1 "task_id: 1
locked_by: alice@test.com
locked_at: 2026-01-01 00:00
hostname: pc-A
pid: $sentinel
pid_starttime: -"

    out7=$(run_claim "$TMPDIR_7" 1 pc-A)
    exit7=$?

    assert_eq "pid: $sentinel → claim exits 0" "0" "$exit7"
    assert_contains "pid: $sentinel → claim proceeds" "OWNED:1" "$out7"
    assert_contains "pid: $sentinel → RECLAIM_STATUS" "RECLAIM_STATUS:" "$out7"
    assert_not_contains "pid: $sentinel → not gated as a live holder" \
        "LOCK_LIVE_HOLDER" "$out7"
    assert_not_contains "pid: $sentinel → not gated as undecidable" \
        "LOCK_UNVERIFIABLE_HOLDER" "$out7"
done

rm -rf "$TMPDIR_7"

# --- Test 8: lock_anchor_is_self verdict table (unit) ---
echo "--- Test 8: lock_anchor_is_self ---"

sleep 300 >/dev/null 2>&1 & SESSION_8=$!
AIT_AGENT_PID="$SESSION_8"
export AIT_AGENT_PID
# Drop the memo: the helper caches this session's anchor on first use, and the
# assertions below deliberately change what "this session" resolves to.
_AIT_SELF_ANCHOR_CACHED=""

tok_8=$(get_pid_starttime "$SESSION_8")
kind_8=$(get_pid_starttime_kind "$SESSION_8")

lock_anchor_is_self "$SESSION_8" "$tok_8" "$kind_8"
assert_eq "Own anchor is self" "0" "$?"

lock_anchor_is_self "$SESSION_8" "99999999" "$kind_8"
assert_eq "Same pid, different token (recycled) is NOT self" "1" "$?"

lock_anchor_is_self "$SESSION_8" "$tok_8" "bogus"
assert_eq "Same pid+token, different token kind is NOT self" "1" "$?"

lock_anchor_is_self 4000000 "$tok_8" "$kind_8"
assert_eq "A different pid is NOT self" "1" "$?"

lock_anchor_is_self "-" "-" proc
assert_eq "The UNKNOWN sentinel is NOT self" "1" "$?"

lock_anchor_is_self "" "" ""
assert_eq "An empty anchor is NOT self" "1" "$?"

# A session that cannot name its own process must not be able to claim that
# someone else's recorded process is it — the asymmetry that makes the helper
# fail toward the gate rather than around it.
stop_session "$SESSION_8"
sleep 300 >/dev/null 2>&1 & SESSION_8B=$!
tok_8b=$(get_pid_starttime "$SESSION_8B")
kind_8b=$(get_pid_starttime_kind "$SESSION_8B")
unset AIT_AGENT_PID
_AIT_SELF_ANCHOR_CACHED=""
(
    unset TMUX TMUX_PANE
    _AIT_SELF_ANCHOR_CACHED=""
    lock_anchor_is_self "$SESSION_8B" "$tok_8b" "$kind_8b"
)
assert_eq "An unresolvable own anchor never claims identity" "1" "$?"
stop_session "$SESSION_8B"
_AIT_SELF_ANCHOR_CACHED=""

# --- Test 9: Syntax checks ---
echo "--- Test 9: Syntax checks ---"

for f in aitask_lock.sh aitask_pick_own.sh lib/pid_anchor.sh; do
    TOTAL=$((TOTAL + 1))
    if bash -n "$PROJECT_DIR/.aitask-scripts/$f"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $f syntax check"
    fi
done

# --- Summary ---
echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
