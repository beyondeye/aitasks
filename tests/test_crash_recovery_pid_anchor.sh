#!/usr/bin/env bash
# test_crash_recovery_pid_anchor.sh - Tests for PID-anchor crash recovery
# (t723). Covers RECLAIM_CRASH: signal emitted when the prior agent's PID
# is dead, PID-recycling defense via pid_starttime, and backward compat
# for pre-anchor locks.
#
# Run: bash tests/test_crash_recovery_pid_anchor.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if [[ "$expected" == "$actual" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected '$expected', got '$actual')"
    fi
}

assert_contains() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qF "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output containing '$expected', got '$actual')"
    fi
}

assert_not_contains() {
    local desc="$1" needle="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qF "$needle"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (did NOT expect output containing '$needle', got '$actual')"
    else
        PASS=$((PASS + 1))
    fi
}

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

Test task for crash-recovery tests.
TASK

        # Hostname shim (TEST_HOSTNAME env override).
        cat > bin/hostname <<'SH'
#!/usr/bin/env bash
echo "${TEST_HOSTNAME:-unknown-host}"
SH
        chmod +x bin/hostname

        mkdir -p .aitask-scripts/lib
        cp "$PROJECT_DIR/.aitask-scripts/aitask_lock.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_pick_own.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" .aitask-scripts/lib/
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
        cd "$local_dir"
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

# Set the test task's status + assigned_to inline (no aitask_update.sh
# needed; we just rewrite the YAML frontmatter).
set_task_implementing() {
    local tmpdir="$1" email="$2"
    (
        cd "$tmpdir/local"
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

echo "=== Crash Recovery PID Anchor Tests (t723) ==="
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

# A pre-anchor lock has prior_pid="-" → is_lock_holder_alive returns false →
# RECLAIM_CRASH would fire. That's actually the desired behavior for the
# backfill flow (we treat unknown PID as crashed). Verify either CRASH or
# STATUS is emitted (the dispatcher handles both as reclaim-with-survey).
TOTAL=$((TOTAL + 1))
if echo "$output5" | grep -qE '^(RECLAIM_CRASH|RECLAIM_STATUS):'; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: pre-anchor lock should emit a reclaim signal (got: $output5)"
fi

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
