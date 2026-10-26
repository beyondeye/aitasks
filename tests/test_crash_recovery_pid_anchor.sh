#!/usr/bin/env bash
# test_crash_recovery_pid_anchor.sh - Tests for PID-anchor crash recovery.
#
# Tests 1-7 (t723) cover the READER contract with hand-planted anchors:
# RECLAIM_CRASH: when the prior agent's PID is dead, PID-recycling defense via
# pid_starttime, and backward compat for pre-anchor locks.
#
# Tests 8-18 (t1465) cover what those could not: the WRITER's choice of PID,
# and the three-state liveness verdict. Every anchor in tests 1-7 is planted,
# so `get_lock_pid()` returning $PPID — the claim script itself, dead seconds
# later — kept the whole suite green while RECLAIM_CRASH fired on every
# same-host re-pick.
#
# Test 19 (t2152) covers the strong macOS token kind `bsdinfo`: the source
# ladder, the reader's same-source rule, and the real probe on macOS.
#
# Live-tmux coverage of the default anchor rung lives in a separate file
# (tests/test_lock_anchor_tmux_live.sh) so this one stays boot-free.
#
# Tests 14 and 17 were retargeted by t1466, which put a liveness gate on the
# ACQUIRE path: a same-host, same-email lock whose holder is alive or
# undecidable is now refused before anything is written, instead of being
# absorbed into the RECLAIM_STATUS bucket after the fact. Their original
# invariant — an undecidable anchor is never reported as a crash — is asserted
# unchanged; only the outcome that follows it moved. The gate itself is covered
# in tests/test_lock_live_holder_gate.sh.
#
# Run: bash tests/test_crash_recovery_pid_anchor.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

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
        cd "$local_dir" || exit 1
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

Test task for crash-recovery tests.
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

# Init the aitask-locks branch on origin (called once per scenario).
init_lock_branch() {
    local tmpdir="$1" host="${2:-pc-A}"
    (cd "$tmpdir/local" && PATH="$tmpdir/local/bin:$PATH" TEST_HOSTNAME="$host" \
        ./.aitask-scripts/aitask_lock.sh --init >/dev/null 2>&1)
}

# Plant a fake lock YAML on origin/aitask-locks. Bypasses the lock script
# so we can simulate any prior-agent state we want.
plant_lock() {
    local tmpdir="$1" task_id="$2" yaml="$3"
    local local_dir="$tmpdir/local"
    (
        cd "$local_dir" || exit 1
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

# Run a real claim through aitask_pick_own.sh inside a fixture. Extra
# `VAR=value` assignments may be passed before the task id via `env`-style
# arguments in $3.. — they are applied to the claim only.
run_claim() {
    local tmpdir="$1" task_id="$2"; shift 2
    (cd "$tmpdir/local" && env "PATH=$tmpdir/local/bin:$PATH" TEST_HOSTNAME=pc-A "$@" \
        ./.aitask-scripts/aitask_pick_own.sh "$task_id" --email "alice@test.com" 2>&1)
}

# Set the test task's status + assigned_to inline (no aitask_update.sh
# needed; we just rewrite the YAML frontmatter).
set_task_implementing() {
    local tmpdir="$1" email="$2"
    (
        cd "$tmpdir/local" || exit 1
        cat > aitasks/t1_test_task.md <<TASK
---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: []
assigned_to: $email
created_at: 2026-01-01 00:00
updated_at: 2026-01-01 00:00
---

Test task already in Implementing status.
TASK
        git add -A
        git commit -m "Pre-set task to Implementing" --quiet
        git push --quiet 2>/dev/null
    )
}

set +e

# The anchor lib itself, for the unit-level assertions in Tests 15/16 and the
# liveness checks the signal-level tests make about their own fixtures.
# shellcheck source=../.aitask-scripts/lib/pid_anchor.sh
. "$PROJECT_DIR/.aitask-scripts/lib/pid_anchor.sh"
# shellcheck source=lib/proc_fixtures.sh
. "$PROJECT_DIR/tests/lib/proc_fixtures.sh"

echo "=== Crash Recovery PID Anchor Tests (t723, t1465) ==="
echo ""

# --- Test 1: Lock writes pid + pid_starttime fields ---
echo "--- Test 1: Lock writes pid + pid_starttime fields ---"

TMPDIR_1="$(setup_paired_repos)"
init_lock_branch "$TMPDIR_1"

(cd "$TMPDIR_1/local" && PATH="$TMPDIR_1/local/bin:$PATH" TEST_HOSTNAME=pc-A \
    ./.aitask-scripts/aitask_lock.sh --lock 1 --email "alice@test.com" >/dev/null 2>&1)

yaml1=$(cd "$TMPDIR_1/local" && git fetch origin aitask-locks --quiet 2>/dev/null \
    && git show "origin/aitask-locks:t1_lock.yaml" 2>/dev/null)

assert_contains "Lock YAML contains pid: line" "pid:" "$yaml1"
if [[ "$(uname)" == "Linux" ]]; then
    assert_contains "Lock YAML contains pid_starttime: (Linux)" "pid_starttime:" "$yaml1"
else
    echo "  (skipping pid_starttime assertion on non-Linux)"
fi

rm -rf "$TMPDIR_1"

# --- Test 2: Same-host crash → RECLAIM_CRASH ---
echo "--- Test 2: Same-host dead-PID lock → RECLAIM_CRASH ---"

TMPDIR_2="$(setup_paired_repos)"
init_lock_branch "$TMPDIR_2" pc-A

set_task_implementing "$TMPDIR_2" "alice@test.com"
plant_lock "$TMPDIR_2" 1 "task_id: 1
locked_by: alice@test.com
locked_at: 2026-01-01 00:00
hostname: pc-A
pid: 999999
pid_starttime: 99999999"

output2=$(cd "$TMPDIR_2/local" && PATH="$TMPDIR_2/local/bin:$PATH" TEST_HOSTNAME=pc-A \
    ./.aitask-scripts/aitask_pick_own.sh 1 --email "alice@test.com" 2>&1)
exit2=$?

assert_eq "Re-pick exits 0" "0" "$exit2"
assert_contains "Emits OWNED" "OWNED:1" "$output2"
assert_contains "Emits RECLAIM_CRASH" "RECLAIM_CRASH:" "$output2"
assert_contains "RECLAIM_CRASH includes prior PID" "|999999" "$output2"
assert_not_contains "No RECLAIM_STATUS when CRASH fires" "RECLAIM_STATUS" "$output2"

rm -rf "$TMPDIR_2"

# --- Test 3 (Linux only): PID-recycling defense via starttime mismatch ---
if [[ "$(uname)" == "Linux" ]]; then
    echo "--- Test 3: Live PID with mismatched starttime → RECLAIM_CRASH ---"

    TMPDIR_3="$(setup_paired_repos)"
    init_lock_branch "$TMPDIR_3" pc-A
    set_task_implementing "$TMPDIR_3" "alice@test.com"

    # PID 1 (init) is always alive on a running Linux system, but we plant
    # a deliberately-wrong starttime — the anchor lib must treat that as
    # a recycled PID and report dead.
    plant_lock "$TMPDIR_3" 1 "task_id: 1
locked_by: alice@test.com
locked_at: 2026-01-01 00:00
hostname: pc-A
pid: 1
pid_starttime: 99999999"

    output3=$(cd "$TMPDIR_3/local" && PATH="$TMPDIR_3/local/bin:$PATH" TEST_HOSTNAME=pc-A \
        ./.aitask-scripts/aitask_pick_own.sh 1 --email "alice@test.com" 2>&1)

    assert_contains "PID-recycling defense → RECLAIM_CRASH" "RECLAIM_CRASH:" "$output3"
    rm -rf "$TMPDIR_3"
else
    echo "--- Test 3: skipped on non-Linux (no /proc starttime) ---"
fi

# --- Test 4: Cross-host still emits LOCK_RECLAIM (regression check) ---
echo "--- Test 4: Cross-host re-pick still emits LOCK_RECLAIM ---"

TMPDIR_4="$(setup_paired_repos)"
init_lock_branch "$TMPDIR_4" pc-A
(cd "$TMPDIR_4/local" && PATH="$TMPDIR_4/local/bin:$PATH" TEST_HOSTNAME=pc-A \
    ./.aitask-scripts/aitask_lock.sh --lock 1 --email "alice@test.com" >/dev/null 2>&1)

output4=$(cd "$TMPDIR_4/local" && PATH="$TMPDIR_4/local/bin:$PATH" TEST_HOSTNAME=pc-B \
    ./.aitask-scripts/aitask_pick_own.sh 1 --email "alice@test.com" 2>&1)

assert_contains "Cross-host emits LOCK_RECLAIM" "LOCK_RECLAIM:pc-A" "$output4"
assert_contains "Cross-host also includes PRIOR_LOCK" "PRIOR_LOCK:" "$output4"

rm -rf "$TMPDIR_4"

# --- Test 5: Backward compat — pre-anchor lock falls back to RECLAIM_STATUS ---
echo "--- Test 5: Pre-anchor lock (no pid: field) → RECLAIM_STATUS ---"

TMPDIR_5="$(setup_paired_repos)"
init_lock_branch "$TMPDIR_5" pc-A
set_task_implementing "$TMPDIR_5" "alice@test.com"

# Plant a legacy lock without pid:/pid_starttime: fields.
plant_lock "$TMPDIR_5" 1 "task_id: 1
locked_by: alice@test.com
locked_at: 2026-01-01 00:00
hostname: pc-A"

output5=$(cd "$TMPDIR_5/local" && PATH="$TMPDIR_5/local/bin:$PATH" TEST_HOSTNAME=pc-A \
    ./.aitask-scripts/aitask_pick_own.sh 1 --email "alice@test.com" 2>&1)

# A pre-anchor lock has prior_pid="-", so its liveness is UNKNOWN — and t1465
# made that its own state rather than a synonym for "crashed". "This lock never
# recorded an anchor" is not evidence that anything died, so the honest verdict
# is the RECLAIM_STATUS anomaly path.
#
# This assertion used to accept CRASH *or* STATUS, from a time when an unknown
# anchor was deliberately reported as a crash. Do not loosen it back: the whole
# point of the fix is that RECLAIM_CRASH means something.
assert_contains "Pre-anchor lock → RECLAIM_STATUS" "RECLAIM_STATUS:" "$output5"
assert_not_contains "Pre-anchor lock is not reported as a crash" "RECLAIM_CRASH" "$output5"

rm -rf "$TMPDIR_5"

# --- Test 6: Live agent on same host (status not Implementing) — no signals ---
echo "--- Test 6: Fresh Ready task, no prior state → no reclaim signals ---"

TMPDIR_6="$(setup_paired_repos)"
init_lock_branch "$TMPDIR_6" pc-A

output6=$(cd "$TMPDIR_6/local" && PATH="$TMPDIR_6/local/bin:$PATH" TEST_HOSTNAME=pc-A \
    ./.aitask-scripts/aitask_pick_own.sh 1 --email "alice@test.com" 2>&1)

assert_contains "Emits OWNED on fresh pick" "OWNED:1" "$output6"
assert_not_contains "No RECLAIM_CRASH on fresh pick" "RECLAIM_CRASH" "$output6"
assert_not_contains "No RECLAIM_STATUS on fresh pick" "RECLAIM_STATUS" "$output6"
assert_not_contains "No LOCK_RECLAIM on fresh pick" "LOCK_RECLAIM" "$output6"

rm -rf "$TMPDIR_6"

# =====================================================================
# t1465 — the WRITER's anchor, and the three-state liveness verdict.
# =====================================================================

# --- Tests 8-10: the writer, driven through the AIT_AGENT_PID seam ---
# One fixture, one long-lived "agent" process, three consecutive real claims:
# claim it, re-pick while the agent lives, re-pick after it dies.

echo "--- Test 8: Real claim anchors to the session PID (no planted state) ---"

TMPDIR_8="$(setup_paired_repos)"
init_lock_branch "$TMPDIR_8" pc-A

# Stand-in for the agent session: a process that outlives the claim script.
sleep 300 &
ANCHOR_PID_8=$!

output8=$(run_claim "$TMPDIR_8" 1 "AIT_AGENT_PID=$ANCHOR_PID_8")

assert_contains "Claim succeeds" "OWNED:1" "$output8"

rec_pid_8=$(lock_field "$TMPDIR_8" 1 pid)
rec_tok_8=$(lock_field "$TMPDIR_8" 1 pid_starttime)
rec_kind_8=$(lock_field "$TMPDIR_8" 1 pid_starttime_kind)

assert_eq "Anchor is the session PID (not the claim script)" "$ANCHOR_PID_8" "$rec_pid_8"
assert_eq "Recorded token matches the live process" "$(get_pid_starttime "$ANCHOR_PID_8")" "$rec_tok_8"
case "$OSTYPE" in
    linux*)  assert_eq "Token kind recorded as proc (Linux)" "proc" "$rec_kind_8" ;;
    darwin*) assert_eq "Token kind recorded as bsdinfo (macOS)" "bsdinfo" "$rec_kind_8" ;;
esac

# --- liveness_token_class: the contract the live-holder suites rely on ---
# Tests that need a provably-alive holder require a STRONG token through this
# classifier, never through `uname` (t2146, t2152). The positive half pins that
# a supported host has one; the negative half pins that a BROKEN identity and a
# weak-only host both fail closed, because the product answers `unknown` for
# each and a test agreeing with it would hide the defect.

cls_rc_8=0
cls_8="$(liveness_token_class "$ANCHOR_PID_8")" || cls_rc_8=$?
assert_eq "liveness_token_class: a live pid classifies" "0" "$cls_rc_8"
assert_eq "liveness_token_class: this host has a strong token" "strong" "$cls_8"
assert_eq "expected_live_verdict expects alive" \
    "alive" "$(expected_live_verdict "$ANCHOR_PID_8")"
assert_eq "expected_live_verdict agrees with the product for a live pid" \
    "$(lock_holder_liveness "$ANCHOR_PID_8" "$(get_pid_starttime "$ANCHOR_PID_8")" \
                            "$(get_pid_starttime_kind "$ANCHOR_PID_8")")" \
    "$(expected_live_verdict "$ANCHOR_PID_8")"
assert_eq "Recorded anchor reads back as alive" \
    "alive" "$(lock_holder_liveness "$rec_pid_8" "$rec_tok_8" "$rec_kind_8")"

# Negative half. Each stub lives only inside its command substitution; the
# result comes back as "[<stdout>] <status>" and is asserted out here, so the
# counters never run inside a subshell.
# shellcheck disable=SC2329  # the stubs are called via liveness_token_class
neg_a="$( _pid_starttime_ps() { return 1; }; _pid_starttime_proc() { return 1; }
          _pid_starttime_bsdinfo() { return 1; }
          o="$(liveness_token_class "$ANCHOR_PID_8" 2>/dev/null)"; echo "[$o] $?" )"
assert_eq "class: no token from any source (token '-', kind none) fails closed" "[] 3" "$neg_a"
# shellcheck disable=SC2329  # the stubs are called via liveness_token_class
neg_a2="$( _pid_starttime_ps() { return 1; }; _pid_starttime_proc() { return 1; }
           _pid_starttime_bsdinfo() { return 1; }
           o="$(expected_live_verdict "$ANCHOR_PID_8" 2>/dev/null)"; echo "[$o] $?" )"
assert_eq "expected_live_verdict: broken identity prints nothing (never 'unknown')" "[] 3" "$neg_a2"
neg_b="$( o="$(liveness_token_class "$(dead_pid_fixture)" 2>/dev/null)"; echo "[$o] $?" )"
assert_eq "class: a dead pid has no token and fails closed" "[] 3" "$neg_b"
# shellcheck disable=SC2329  # the stubs are called via liveness_token_class
neg_c="$( get_pid_starttime_kind() { echo bogus; }
          o="$(liveness_token_class "$ANCHOR_PID_8" 2>/dev/null)"; echo "[$o] $?" )"
assert_eq "class: an unrecognised kind fails closed" "[] 3" "$neg_c"
# Stub the TOKEN, not _pid_starttime_ps: without /proc get_pid_starttime reads
# _pid_starttime_ps itself, so stubbing it would compare the stub with itself.
# shellcheck disable=SC2329  # the stubs are called via liveness_token_class
neg_d="$( get_pid_starttime_kind() { echo ps; }; get_pid_starttime() { echo 123456789; }
          o="$(liveness_token_class "$ANCHOR_PID_8" 2>/dev/null)"; echo "[$o] $?" )"
assert_eq "class: a ps kind whose token does not re-derive from ps fails closed" "[] 3" "$neg_d"
# A weak-only host: the strong sources are unavailable, so the identity is the
# real, re-derivable ps token. That is not BROKEN, but it cannot prove a live
# holder either, so it fails closed under its own status rather than skipping.
# shellcheck disable=SC2329  # the stubs are called via liveness_token_class
neg_f="$( _pid_starttime_proc() { return 1; }; _pid_starttime_bsdinfo() { return 1; }
          o="$(liveness_token_class "$ANCHOR_PID_8" 2>/dev/null)"; echo "[$o] $?" )"
assert_eq "class: a weak-only (ps) host fails closed" "[] 4" "$neg_f"
# shellcheck disable=SC2329  # the stubs are called via expected_live_verdict
neg_f2="$( _pid_starttime_proc() { return 1; }; _pid_starttime_bsdinfo() { return 1; }
           o="$(expected_live_verdict "$ANCHOR_PID_8" 2>/dev/null)"; echo "[$o] $?" )"
assert_eq "expected_live_verdict: a weak-only host prints nothing (never 'unknown')" "[] 4" "$neg_f2"
neg_e="$(bash -c '. "$1"; o="$(liveness_token_class $$ 2>/dev/null)"; echo "[$o] $?"' \
            _ "$PROJECT_DIR/tests/lib/proc_fixtures.sh")"
assert_eq "class: pid_anchor.sh not sourced is a setup error" "[] 2" "$neg_e"

echo "--- Test 9: Re-pick while the holder is ALIVE → no false crash ---"

# The task is already Implementing/alice from Test 8's claim — this is exactly
# the innocent same-host re-pick that used to report a crash.
output9=$(run_claim "$TMPDIR_8" 1 "AIT_AGENT_PID=$ANCHOR_PID_8")

assert_contains "Re-pick succeeds" "OWNED:1" "$output9"
assert_not_contains "No RECLAIM_CRASH for a live holder" "RECLAIM_CRASH" "$output9"
assert_contains "Routes to the anomaly path instead" "RECLAIM_STATUS" "$output9"

echo "--- Test 10: Positive control — a real crash is still detected ---"

# Kill the "agent" and reap it, so its PID is genuinely absent.
kill "$ANCHOR_PID_8" 2>/dev/null
wait "$ANCHOR_PID_8" 2>/dev/null
assert_eq "Killed anchor now reads as dead" \
    "dead" "$(lock_holder_liveness "$ANCHOR_PID_8" "$rec_tok_8" "$rec_kind_8")"

sleep 300 &
ANCHOR_PID_10=$!
output10=$(run_claim "$TMPDIR_8" 1 "AIT_AGENT_PID=$ANCHOR_PID_10")

assert_contains "Dead prior anchor → RECLAIM_CRASH" "RECLAIM_CRASH:" "$output10"
assert_contains "RECLAIM_CRASH names the dead session PID" "|${ANCHOR_PID_8}" "$output10"

kill "$ANCHOR_PID_10" 2>/dev/null
wait "$ANCHOR_PID_10" 2>/dev/null
rm -rf "$TMPDIR_8"

# --- Test 11: negative control for the defect itself ---
# The no-override, NO-TMUX rung: with nothing left to resolve, the writer must
# record the explicit UNKNOWN sentinel. This is the assertion the pre-fix
# writer fails — `echo "$PPID"` recorded the claim script, a real (and by now
# dead) PID, never "-".
#
# TMUX and TMUX_PANE are cleared alongside AIT_AGENT_PID and the outcome is
# pinned exactly. Leaving them inherited would make the result depend on the
# runner's environment — a pane in one place, nothing in another — in a test
# whose whole value is being boot-free and deterministic. The pane rung is not
# lost: tests/test_lock_anchor_tmux_live.sh proves it against a real server,
# which is the only place it can be proven honestly.

echo "--- Test 11: With nothing to resolve, the anchor is UNKNOWN (never a dead PID) ---"

TMPDIR_11="$(setup_paired_repos)"
init_lock_branch "$TMPDIR_11" pc-A

output11=$(cd "$TMPDIR_11/local" && env -u AIT_AGENT_PID -u TMUX -u TMUX_PANE \
    "PATH=$TMPDIR_11/local/bin:$PATH" TEST_HOSTNAME=pc-A \
    ./.aitask-scripts/aitask_pick_own.sh 1 --email "alice@test.com" 2>&1)
assert_contains "Claim succeeds without an override" "OWNED:1" "$output11"

rec_pid_11=$(lock_field "$TMPDIR_11" 1 pid)
assert_eq "Unresolvable anchor is the UNKNOWN sentinel" \
    "$AIT_PID_ANCHOR_UNKNOWN" "$rec_pid_11"
assert_eq "Unresolvable anchor records no token kind" \
    "none" "$(lock_field "$TMPDIR_11" 1 pid_starttime_kind)"
# Stated as its own check: the defect wrote a PID here, and any PID — alive or
# dead — means the writer picked a process it had no business anchoring to.
TOTAL=$((TOTAL + 1))
if [[ "$rec_pid_11" =~ ^[0-9]+$ ]]; then
    FAIL=$((FAIL + 1))
    echo "FAIL: writer recorded pid $rec_pid_11 with no session process to name (the t1465 defect)"
else
    PASS=$((PASS + 1))
fi

rm -rf "$TMPDIR_11"

# --- Tests 12-14, 17: reader verdicts, via planted anchors ---
# One fixture; each case plants a lock, re-picks, and asserts the signal.

echo "--- Test 12: UNKNOWN anchor is not a crash ---"

TMPDIR_12="$(setup_paired_repos)"
init_lock_branch "$TMPDIR_12" pc-A
set_task_implementing "$TMPDIR_12" "alice@test.com"

for sentinel in "-" "0"; do
    plant_lock "$TMPDIR_12" 1 "task_id: 1
locked_by: alice@test.com
locked_at: 2026-01-01 00:00
hostname: pc-A
pid: $sentinel
pid_starttime: -"
    out12=$(run_claim "$TMPDIR_12" 1)
    assert_not_contains "pid: $sentinel → not a crash" "RECLAIM_CRASH" "$out12"
    assert_contains "pid: $sentinel → RECLAIM_STATUS" "RECLAIM_STATUS" "$out12"
done

echo "--- Test 13: AIT_AGENT_PID never fails open ---"

out13=$(run_claim "$TMPDIR_12" 1 "AIT_AGENT_PID=4000000")
assert_contains "Dead override is reported" "AIT_AGENT_PID=4000000" "$out13"
assert_contains "Dead override is refused, not used" "does not name a live process" "$out13"
assert_eq "Dead override never becomes the anchor" \
    "" "$(lock_field "$TMPDIR_12" 1 pid | grep -x 4000000)"

echo "--- Test 14: live PID with no identity token ⇒ unknown, not crash ---"

sleep 300 &
ANCHOR_PID_14=$!
plant_lock "$TMPDIR_12" 1 "task_id: 1
locked_by: alice@test.com
locked_at: 2026-01-01 00:00
hostname: pc-A
pid: $ANCHOR_PID_14
pid_starttime: -"
out14=$(run_claim "$TMPDIR_12" 1 "AIT_AGENT_PID=$ANCHOR_PID_14")
assert_not_contains "Untokened live PID is not a crash" "RECLAIM_CRASH" "$out14"
# t1466 retarget. The invariant this test was written to protect — an
# undecidable anchor is NEVER reported as a crash — is asserted above and is
# unchanged. What changed is where the claim ends up: this case used to be
# absorbed into the RECLAIM_STATUS anomaly bucket *after* the lock had already
# been taken. It is now refused at acquire time with its own signal, which is
# what makes "cannot tell" a state of its own rather than a synonym for "go
# ahead". Do not loosen this back to RECLAIM_STATUS.
assert_contains "Untokened live PID → LOCK_UNVERIFIABLE_HOLDER" \
    "LOCK_UNVERIFIABLE_HOLDER:" "$out14"
assert_not_contains "Untokened live PID is not claimed" "OWNED:" "$out14"

echo "--- Test 17: weak (second-granular) token cannot prove liveness ---"

# Every supported host has both token sources: `ps` everywhere, plus a strong
# one (`proc` on Linux, `bsdinfo` on macOS). The strong kind is whatever this
# host records for the anchor, so the case runs on both platforms.
strong_kind_17=$(get_pid_starttime_kind "$ANCHOR_PID_14")
case "$strong_kind_17" in
    proc|bsdinfo) strong_ok_17=1 ;;
    *)            strong_ok_17=0 ;;
esac
assert_eq "Fixture check: the anchor records a strong kind (got '$strong_kind_17')" "1" "$strong_ok_17"
if (( strong_ok_17 )); then
    ps_tok_17=$(_pid_starttime_ps "$ANCHOR_PID_14")
    strong_tok_17=$(get_pid_starttime "$ANCHOR_PID_14")

    assert_eq "kind=ps + matching token ⇒ unknown (weak)" \
        "unknown" "$(lock_holder_liveness "$ANCHOR_PID_14" "$ps_tok_17" ps)"
    assert_eq "kind=$strong_kind_17 + matching token ⇒ alive (strong)" \
        "alive" "$(lock_holder_liveness "$ANCHOR_PID_14" "$strong_tok_17" "$strong_kind_17")"

    # Neither verdict is a crash — the strength gate changes the VERDICT, and
    # t1466's acquire gate then routes the two verdicts to different OUTCOMES.
    # The claim below runs with AIT_AGENT_PID equal to the planted anchor, so
    # the two halves also pin the self-identity rule:
    #
    #   strong kind — the recorded triple (pid, token, kind) is exactly this
    #     session's, so the lock is OURS. It refreshes silently, as every
    #     in-pane re-pick and in-flight resume must.
    #   kind=ps — same pid, but a second-granular token this host would never
    #     have written. That is not a provable identity, so it is not self, and
    #     the weak token cannot license an "alive" verdict either. Undecidable
    #     ⇒ refused at acquire, its own signal.
    for pair in "ps:$ps_tok_17" "$strong_kind_17:$strong_tok_17"; do
        kind_17="${pair%%:*}"; tok_17="${pair#*:}"
        plant_lock "$TMPDIR_12" 1 "task_id: 1
locked_by: alice@test.com
locked_at: 2026-01-01 00:00
hostname: pc-A
pid: $ANCHOR_PID_14
pid_starttime: $tok_17
pid_starttime_kind: $kind_17"
        out17=$(run_claim "$TMPDIR_12" 1 "AIT_AGENT_PID=$ANCHOR_PID_14")
        assert_not_contains "kind=$kind_17 live holder → not a crash" "RECLAIM_CRASH" "$out17"
        if [[ "$kind_17" != "ps" ]]; then
            assert_contains "kind=$kind_17 live holder is OUR OWN lock → refreshed" \
                "OWNED:1" "$out17"
            assert_contains "kind=$kind_17 self re-claim → RECLAIM_STATUS" \
                "RECLAIM_STATUS" "$out17"
            assert_not_contains "kind=$kind_17 self re-claim is not refused" \
                "LOCK_UNVERIFIABLE_HOLDER" "$out17"
        else
            assert_contains "kind=ps live holder → LOCK_UNVERIFIABLE_HOLDER" \
                "LOCK_UNVERIFIABLE_HOLDER:" "$out17"
            assert_not_contains "kind=ps live holder is not claimed" \
                "OWNED:" "$out17"
        fi
    done
fi

kill "$ANCHOR_PID_14" 2>/dev/null
wait "$ANCHOR_PID_14" 2>/dev/null
rm -rf "$TMPDIR_12"

# --- Test 15: _pid_exists / lock_holder_liveness verdict table (unit) ---

echo "--- Test 15: liveness verdict table ---"

sleep 300 &
UNIT_PID=$!
unit_tok=$(get_pid_starttime "$UNIT_PID")
unit_kind=$(get_pid_starttime_kind "$UNIT_PID")

_pid_exists "$UNIT_PID";  assert_eq "_pid_exists: live self-owned PID" "0" "$?"
_pid_exists 4000000;      assert_eq "_pid_exists: confirmed absent (ESRCH)" "1" "$?"
_pid_exists abc;          assert_eq "_pid_exists: non-numeric is undecidable" "2" "$?"
# PID 1 exists but cannot be signalled by a normal user: `kill -0` reports
# EPERM with the SAME exit status as ESRCH, and a hidepid procfs hides it from
# /proc and ps alike. Calling that "absent" is how a live holder gets reported
# as crashed, so it must resolve to "exists".
_pid_exists 1;            assert_eq "_pid_exists: EPERM means exists, not absent" "0" "$?"

# The matching-token row is `alive` only for a strong token, which every
# supported host records (`proc` / `bsdinfo`). Fails closed via the classifier.
unit_rc=0
liveness_token_class "$UNIT_PID" >/dev/null || unit_rc=$?
assert_eq "Fixture check: the unit pid has a strong identity token" "0" "$unit_rc"
assert_eq "live + matching $unit_kind token ⇒ alive" \
    "alive" "$(lock_holder_liveness "$UNIT_PID" "$unit_tok" "$unit_kind")"
# Same kind as the host records, so the reader re-derives from the source it can
# actually read (a `proc` kind on a host without /proc would read `unknown`).
assert_eq "live + wrong token ⇒ dead" \
    "dead"    "$(lock_holder_liveness "$UNIT_PID" "99999999" "$unit_kind")"
assert_eq "live + no token ⇒ unknown" \
    "unknown" "$(lock_holder_liveness "$UNIT_PID" "-" proc)"
assert_eq "live + unrecognised kind ⇒ unknown" \
    "unknown" "$(lock_holder_liveness "$UNIT_PID" "$unit_tok" bogus)"
assert_eq "absent pid ⇒ dead" \
    "dead"    "$(lock_holder_liveness 4000000 99999999 proc)"
assert_eq "pid '-' ⇒ unknown" "unknown" "$(lock_holder_liveness - - proc)"
assert_eq "pid 0 ⇒ unknown"   "unknown" "$(lock_holder_liveness 0 - proc)"
assert_eq "pid 'abc' ⇒ unknown" "unknown" "$(lock_holder_liveness abc - proc)"

is_lock_holder_alive 0 -
assert_eq "is_lock_holder_alive rejects the pid:0 sentinel" "1" "$?"
is_lock_holder_alive "$UNIT_PID" "$unit_tok" "$unit_kind"
assert_eq "is_lock_holder_alive accepts a proven live holder" "0" "$?"
is_lock_holder_alive "$UNIT_PID" "$(_pid_starttime_ps "$UNIT_PID")" ps
assert_eq "is_lock_holder_alive refuses a weak-token holder it cannot prove" "1" "$?"

# --- Test 16: the `ps` token generator (BSD/macOS implementation) ---
# Linux `ps` supports lstart too, so the implementation is exercisable here
# even though its DISPATCH (no /proc) is not.

echo "--- Test 16: ps-derived identity token ---"

ps_tok_a=$(_pid_starttime_ps "$UNIT_PID")
ps_tok_b=$(_pid_starttime_ps "$UNIT_PID")

TOTAL=$((TOTAL + 1))
if [[ -n "$ps_tok_a" && "$ps_tok_a" != *[[:space:]]* ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: ps token should be non-empty and whitespace-free (got: '$ps_tok_a')"
fi
assert_eq "ps token is stable across reads" "$ps_tok_a" "$ps_tok_b"

_pid_starttime_ps 4000000
assert_eq "ps token generator fails for an absent pid" "1" "$?"

sleep 1.2
sleep 300 &
UNIT_PID_2=$!
TOTAL=$((TOTAL + 1))
if [[ "$(_pid_starttime_ps "$UNIT_PID_2")" != "$ps_tok_a" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: processes started >1s apart should get different ps tokens"
fi

kill "$UNIT_PID" "$UNIT_PID_2" 2>/dev/null
wait "$UNIT_PID" "$UNIT_PID_2" 2>/dev/null

# --- Test 18: an unreachable tmux server degrades, it does not block ---
# The anchor's default rung now spawns a `tmux display-message` on the lock
# critical path. A wedged or absent server must produce UNKNOWN — not a hang,
# and not an abort under `set -euo pipefail`. Driven through the gateway's own
# socket selector (AITASKS_TMUX_SOCKET), not a test-only override.

echo "--- Test 18: claim survives an unreachable tmux server ---"

TMPDIR_18="$(setup_paired_repos)"
init_lock_branch "$TMPDIR_18" pc-A

start_18=$SECONDS
output18=$(cd "$TMPDIR_18/local" && timeout 30 env -u AIT_AGENT_PID \
    "PATH=$TMPDIR_18/local/bin:$PATH" TEST_HOSTNAME=pc-A \
    TMUX_PANE="%999" TMUX="/nonexistent/ait-sock-$$,1,0" \
    "AITASKS_TMUX_SOCKET=ait-nonexistent-$$" \
    ./.aitask-scripts/aitask_pick_own.sh 1 --email "alice@test.com" 2>&1)
rc18=$?
elapsed_18=$((SECONDS - start_18))

assert_eq "Unreachable tmux does not abort the claim" "0" "$rc18"
assert_contains "Claim still succeeds" "OWNED:1" "$output18"
assert_eq "Anchor degrades to the UNKNOWN sentinel" \
    "$AIT_PID_ANCHOR_UNKNOWN" "$(lock_field "$TMPDIR_18" 1 pid)"
assert_eq "Token kind recorded as none" "none" "$(lock_field "$TMPDIR_18" 1 pid_starttime_kind)"

TOTAL=$((TOTAL + 1))
if [[ $rc18 -ne 124 && $elapsed_18 -lt 30 ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: claim did not complete within the 30s budget (rc=$rc18, ${elapsed_18}s)"
fi

# And the UNKNOWN it recorded must read back as unknown, never as a crash.
assert_eq "UNKNOWN anchor reads back as unknown" "unknown" \
    "$(lock_holder_liveness "$(lock_field "$TMPDIR_18" 1 pid)" \
                            "$(lock_field "$TMPDIR_18" 1 pid_starttime)" \
                            "$(lock_field "$TMPDIR_18" 1 pid_starttime_kind)")"

rm -rf "$TMPDIR_18"

# --- Test 19: the bsdinfo identity token (macOS strong kind, t2152) ---
# The source ladder and the reader's same-source rule are asserted on every
# platform through stubs, so the Linux path of the shared code is exercised on a
# macOS host and vice versa. The real probe is asserted where it can run.

echo "--- Test 19: bsdinfo identity token ---"

sleep 300 &
UNIT_PID_19=$!

# A recorded bsdinfo lock whose probe now fails must read `unknown`. The ps and
# proc stubs return tokens that DIFFER from the recorded one, so a reader that
# fell back to another source would answer `dead` — a false crash.
# shellcheck disable=SC2329  # the stubs are called via lock_holder_liveness
r19_reader="$( _pid_starttime_bsdinfo() { return 1; }
               _pid_starttime_ps() { echo Mon_Jan__1_00:00:00_2001; }
               _pid_starttime_proc() { echo 1; }
               lock_holder_liveness "$UNIT_PID_19" 1793019250.025784 bsdinfo )"
assert_eq "bsdinfo probe failure on a recorded bsdinfo lock ⇒ unknown (no source switch)" \
    "unknown" "$r19_reader"

# Ladder order: proc > bsdinfo > ps > none. A lower rung must never run once a
# higher one answered. A lower-rung stub records each call in a marker file:
# get_pid_identity discards every source's stderr and stdout of a source it does
# not select, so neither channel could witness a stray probe.
CALLS_19="$(mktemp)"
# shellcheck disable=SC2329  # the stubs are called via get_pid_identity
r19_proc="$( _pid_starttime_proc() { echo 4242; }
             _pid_starttime_bsdinfo() { echo bsdinfo >> "$CALLS_19"; echo 9.000009; }
             _pid_starttime_ps() { echo ps >> "$CALLS_19"; echo X; }
             get_pid_identity "$UNIT_PID_19"
             echo "[$(get_pid_starttime_kind "$UNIT_PID_19")|$(get_pid_starttime "$UNIT_PID_19")]" )"
assert_eq "ladder: proc answers first; wrappers agree" \
    "proc 4242
[proc|4242]" "$r19_proc"
assert_eq "ladder: with proc answering, no lower source is ever probed" "" "$(cat "$CALLS_19")"
: > "$CALLS_19"
# shellcheck disable=SC2329
r19_bsd="$( _pid_starttime_proc() { return 1; }; _pid_starttime_bsdinfo() { echo 1.000001; }
            _pid_starttime_ps() { echo ps >> "$CALLS_19"; echo X; }
            get_pid_identity "$UNIT_PID_19" )"
assert_eq "ladder: no proc ⇒ bsdinfo" "bsdinfo 1.000001" "$r19_bsd"
assert_eq "ladder: with bsdinfo answering, ps is never probed" "" "$(cat "$CALLS_19")"
rm -f "$CALLS_19"
# shellcheck disable=SC2329
r19_ps="$( _pid_starttime_proc() { return 1; }; _pid_starttime_bsdinfo() { return 1; }
           _pid_starttime_ps() { echo X; }
           get_pid_identity "$UNIT_PID_19" )"
assert_eq "ladder: no strong source ⇒ ps" "ps X" "$r19_ps"
# shellcheck disable=SC2329
r19_none="$( _pid_starttime_proc() { return 1; }; _pid_starttime_bsdinfo() { return 1; }
             _pid_starttime_ps() { return 1; }
             get_pid_identity "$UNIT_PID_19" )"
assert_eq "ladder: no source ⇒ none -" "none -" "$r19_none"
assert_eq "identity of the unknown anchor is none -" "none -" "$(get_pid_identity -)"

# The writers split one get_pid_identity call with `read -r kind token`; a
# swapped order would store the kind as the token. Pinned through the
# self-anchor cache, which uses the same split. (A stub cannot reach the claim
# scripts' own processes; their writers are covered by Test 8's real claim.)
# shellcheck disable=SC2329,SC2034  # the stub and the vars are read by _ait_current_anchor
r19_writer="$( AIT_AGENT_PID=$UNIT_PID_19; _AIT_SELF_ANCHOR_CACHED=""
               _pid_starttime_proc() { echo 4242; }
               _ait_current_anchor
               echo "$_AIT_SELF_ANCHOR_PID|$_AIT_SELF_ANCHOR_KIND|$_AIT_SELF_ANCHOR_TOKEN" )"
assert_eq "writer split: kind and token land in the right fields" \
    "$UNIT_PID_19|proc|4242" "$r19_writer"

if [[ "$OSTYPE" == darwin* ]]; then
    tok_19=$(_pid_starttime_bsdinfo "$UNIT_PID_19"); rc_19=$?
    assert_eq "bsdinfo: readable for an own live pid" "0" "$rc_19"
    TOTAL=$((TOTAL + 1))
    if [[ "$tok_19" =~ ^[0-9]+\.[0-9]{6}$ ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: bsdinfo token should be <sec>.<usec6> (got: '$tok_19')"
    fi
    assert_eq "bsdinfo: stable across reads" "$tok_19" "$(_pid_starttime_bsdinfo "$UNIT_PID_19")"

    _pid_starttime_bsdinfo "$(dead_pid_fixture)" >/dev/null
    assert_eq "bsdinfo: fails for a reaped pid" "1" "$?"

    # pid 1 belongs to root. Whether this user may read it is a property of the
    # runner, so assert only that kind and token agree with what was observed.
    if p1_tok_19=$(_pid_starttime_bsdinfo 1); then
        assert_eq "pid 1 readable ⇒ recorded as bsdinfo" \
            "bsdinfo $p1_tok_19" "$(get_pid_identity 1)"
    else
        p1_id_19=$(get_pid_identity 1)
        case "${p1_id_19%% *}" in
            ps)   assert_eq "pid 1 unreadable ⇒ the ps fallback, with its own token" \
                      "ps $(_pid_starttime_ps 1)" "$p1_id_19" ;;
            none) assert_eq "pid 1 unreadable by every source ⇒ none -" "none -" "$p1_id_19" ;;
            *)    assert_eq "pid 1 unreadable ⇒ never recorded as bsdinfo" "ps|none" "$p1_id_19" ;;
        esac
    fi

    # The token is p_start, the field `ps lstart` truncates to the second. Pins
    # the struct proc_bsdinfo offset: a wrong one would not decode to this.
    lstart_19="$(LC_ALL=C date -r "${tok_19%%.*}" '+%a %b %e %T %Y' | tr -s '[:space:]' '_')"
    lstart_19="${lstart_19#_}"; lstart_19="${lstart_19%_}"
    assert_eq "bsdinfo seconds decode to the ps lstart of the same process" \
        "$(_pid_starttime_ps "$UNIT_PID_19")" "$lstart_19"

    # The case the kind exists for: processes started back to back.
    sleep 300 & PID_19A=$!
    sleep 300 & PID_19B=$!
    tok_19a=$(_pid_starttime_bsdinfo "$PID_19A"); tok_19b=$(_pid_starttime_bsdinfo "$PID_19B")
    TOTAL=$((TOTAL + 1))
    if [[ -n "$tok_19a" && -n "$tok_19b" && "$tok_19a" != "$tok_19b" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: back-to-back processes need distinct bsdinfo tokens (got '$tok_19a' / '$tok_19b')"
    fi
    if [[ "${tok_19a%%.*}" == "${tok_19b%%.*}" ]]; then
        assert_eq "same second: ps cannot tell them apart, bsdinfo can" \
            "$(_pid_starttime_ps "$PID_19A")" "$(_pid_starttime_ps "$PID_19B")"
    fi
    kill "$PID_19A" "$PID_19B" 2>/dev/null
    wait "$PID_19A" "$PID_19B" 2>/dev/null

    assert_eq "identity: macOS records bsdinfo" "bsdinfo $tok_19" "$(get_pid_identity "$UNIT_PID_19")"
    assert_eq "wrapper: kind" "bsdinfo" "$(get_pid_starttime_kind "$UNIT_PID_19")"
    assert_eq "wrapper: token" "$tok_19" "$(get_pid_starttime "$UNIT_PID_19")"
    assert_eq "live + matching bsdinfo token ⇒ alive" \
        "alive" "$(lock_holder_liveness "$UNIT_PID_19" "$tok_19" bsdinfo)"
    assert_eq "live + wrong bsdinfo token ⇒ dead" \
        "dead" "$(lock_holder_liveness "$UNIT_PID_19" 1.000000 bsdinfo)"

    # No interpreter: the writer degrades to the weak-but-consistent ps kind.
    # shellcheck disable=SC2329  # the stub is called via get_pid_identity
    r19_nopy="$( _pid_anchor_python() { return 1; }; get_pid_identity "$UNIT_PID_19" )"
    assert_eq "no Python ⇒ ps fallback, never none" \
        "ps $(_pid_starttime_ps "$UNIT_PID_19")" "$r19_nopy"
else
    _pid_starttime_bsdinfo "$UNIT_PID_19" >/dev/null
    assert_eq "bsdinfo: not a source off macOS" "1" "$?"
    assert_eq "a bsdinfo lock read off macOS ⇒ unknown, never dead" \
        "unknown" "$(lock_holder_liveness "$UNIT_PID_19" 1.000000 bsdinfo)"
fi

kill "$UNIT_PID_19" 2>/dev/null
wait "$UNIT_PID_19" 2>/dev/null

# --- Test 7: Syntax checks ---
echo "--- Test 7: Syntax checks ---"

TOTAL=$((TOTAL + 1))
if bash -n "$PROJECT_DIR/.aitask-scripts/aitask_lock.sh"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: aitask_lock.sh syntax check"
fi

TOTAL=$((TOTAL + 1))
if bash -n "$PROJECT_DIR/.aitask-scripts/aitask_pick_own.sh"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: aitask_pick_own.sh syntax check"
fi

TOTAL=$((TOTAL + 1))
if bash -n "$PROJECT_DIR/.aitask-scripts/lib/pid_anchor.sh"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: lib/pid_anchor.sh syntax check"
fi

TOTAL=$((TOTAL + 1))
if bash -n "$PROJECT_DIR/.aitask-scripts/lib/tmux_exec.sh"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: lib/tmux_exec.sh syntax check"
fi

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
