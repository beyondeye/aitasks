#!/usr/bin/env bash
# test_lock_reclaim.sh - Tests for LOCK_RECLAIM:/RECLAIM_STATUS: signals
# emitted when a user re-claims a task they already locked on a different
# host (the multi-PC self-reclaim case from t692).
#
# Run: bash tests/test_lock_reclaim.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

# --- Test helpers ---

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

# Create a paired repo setup with a fake `hostname` shim under bin/.
# The shim reads TEST_HOSTNAME from the environment so each test can override.
setup_paired_repos() {
    local tmpdir
    tmpdir="$(mktemp -d)"

    # Bare "remote" repo
    local remote_dir="$tmpdir/remote.git"
    git init --bare --quiet "$remote_dir"

    local local_dir="$tmpdir/local"
    git clone --quiet "$remote_dir" "$local_dir"
    (
        cd "$local_dir"
        git config user.email "test@test.com"
        git config user.name "Test"

        mkdir -p aitasks/archived aitasks/metadata aiplans bin

        # Sample task file with status: Ready (default).
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

Test task for lock reclaim tests.
TASK

        # Fake hostname shim — picks up TEST_HOSTNAME at runtime.
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
        cp "$PROJECT_DIR/ait" . 2>/dev/null || true
        chmod +x .aitask-scripts/*.sh ait 2>/dev/null || true

        git add -A
        git commit -m "Initial setup" --quiet
        git push --quiet 2>/dev/null
    )

    echo "$tmpdir"
}

# Disable strict mode for test error handling
set +e

echo "=== Lock Reclaim Tests ==="
echo ""

# --- Test 1: LOCK_RECLAIM emitted on same-email-different-host re-lock ---
echo "--- Test 1: LOCK_RECLAIM emitted on same-email-different-host re-lock ---"

TMPDIR_1="$(setup_paired_repos)"
(cd "$TMPDIR_1/local" && PATH="$TMPDIR_1/local/bin:$PATH" TEST_HOSTNAME=pc-A \
    ./.aitask-scripts/aitask_lock.sh --init >/dev/null 2>&1)

# Lock as alice from pc-A
(cd "$TMPDIR_1/local" && PATH="$TMPDIR_1/local/bin:$PATH" TEST_HOSTNAME=pc-A \
    ./.aitask-scripts/aitask_lock.sh --lock 1 --email "alice@test.com" >/dev/null 2>&1)

# Re-lock as alice from pc-B
output1=$(cd "$TMPDIR_1/local" && PATH="$TMPDIR_1/local/bin:$PATH" TEST_HOSTNAME=pc-B \
    ./.aitask-scripts/aitask_lock.sh --lock 1 --email "alice@test.com" 2>&1)
exit1=$?

assert_eq "Same-email-different-host re-lock exits 0" "0" "$exit1"
assert_contains "Output contains LOCK_RECLAIM with prev hostname" "LOCK_RECLAIM:pc-A" "$output1"
assert_contains "Output contains current hostname" "|pc-B" "$output1"

# Verify the lock was refreshed to pc-B
yaml1=$(cd "$TMPDIR_1/local" && git fetch origin aitask-locks --quiet 2>/dev/null \
    && git show "origin/aitask-locks:t1_lock.yaml" 2>/dev/null)
assert_contains "Lock YAML refreshed to pc-B" "hostname: pc-B" "$yaml1"
assert_contains "Lock YAML still owned by alice" "locked_by: alice@test.com" "$yaml1"

rm -rf "$TMPDIR_1"

# --- Test 2: Same-host same-email re-lock stays silent ---
echo "--- Test 2: Same-host same-email re-lock stays silent ---"

TMPDIR_2="$(setup_paired_repos)"
(cd "$TMPDIR_2/local" && PATH="$TMPDIR_2/local/bin:$PATH" TEST_HOSTNAME=pc-A \
    ./.aitask-scripts/aitask_lock.sh --init >/dev/null 2>&1)
(cd "$TMPDIR_2/local" && PATH="$TMPDIR_2/local/bin:$PATH" TEST_HOSTNAME=pc-A \
    ./.aitask-scripts/aitask_lock.sh --lock 1 --email "alice@test.com" >/dev/null 2>&1)

output2=$(cd "$TMPDIR_2/local" && PATH="$TMPDIR_2/local/bin:$PATH" TEST_HOSTNAME=pc-A \
    ./.aitask-scripts/aitask_lock.sh --lock 1 --email "alice@test.com" 2>&1)
exit2=$?

assert_eq "Same-host re-lock exits 0" "0" "$exit2"
assert_not_contains "No LOCK_RECLAIM on same host" "LOCK_RECLAIM" "$output2"

rm -rf "$TMPDIR_2"

# --- Test 3: pick_own.sh forwards LOCK_RECLAIM to its caller ---
echo "--- Test 3: pick_own.sh forwards LOCK_RECLAIM ---"

TMPDIR_3="$(setup_paired_repos)"
(cd "$TMPDIR_3/local" && PATH="$TMPDIR_3/local/bin:$PATH" TEST_HOSTNAME=pc-A \
    ./.aitask-scripts/aitask_lock.sh --init >/dev/null 2>&1)
(cd "$TMPDIR_3/local" && PATH="$TMPDIR_3/local/bin:$PATH" TEST_HOSTNAME=pc-A \
    ./.aitask-scripts/aitask_lock.sh --lock 1 --email "alice@test.com" >/dev/null 2>&1)

output3=$(cd "$TMPDIR_3/local" && PATH="$TMPDIR_3/local/bin:$PATH" TEST_HOSTNAME=pc-B \
    ./.aitask-scripts/aitask_pick_own.sh 1 --email "alice@test.com" 2>&1)
exit3=$?

assert_eq "pick_own re-claim exits 0" "0" "$exit3"
assert_contains "pick_own forwards LOCK_RECLAIM" "LOCK_RECLAIM:pc-A" "$output3"
assert_contains "pick_own contains current hostname" "|pc-B" "$output3"
assert_contains "pick_own confirms OWNED" "OWNED:1" "$output3"

rm -rf "$TMPDIR_3"

# --- Test 4: pick_own emits RECLAIM_STATUS when task already Implementing ---
echo "--- Test 4: pick_own emits RECLAIM_STATUS for stuck Implementing status ---"

TMPDIR_4="$(setup_paired_repos)"
(cd "$TMPDIR_4/local" && PATH="$TMPDIR_4/local/bin:$PATH" TEST_HOSTNAME=pc-A \
    ./.aitask-scripts/aitask_lock.sh --init >/dev/null 2>&1)

# Pre-set the task to Implementing assigned to alice (no lock present —
# simulates the rare "lock cleaned but status stuck" anomaly).
(
    cd "$TMPDIR_4/local"
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
    git add -A && git commit -m "Pre-set task to Implementing" --quiet
    git push --quiet 2>/dev/null
)

output4=$(cd "$TMPDIR_4/local" && PATH="$TMPDIR_4/local/bin:$PATH" TEST_HOSTNAME=pc-B \
    ./.aitask-scripts/aitask_pick_own.sh 1 --email "alice@test.com" 2>&1)
exit4=$?

assert_eq "pick_own with stuck status exits 0" "0" "$exit4"
assert_contains "pick_own emits OWNED" "OWNED:1" "$output4"
assert_contains "pick_own emits RECLAIM_STATUS" "RECLAIM_STATUS:Implementing|alice@test.com" "$output4"

rm -rf "$TMPDIR_4"

# --- Test 5: pick_own stays silent on fresh task ---
echo "--- Test 5: pick_own stays silent on fresh Ready task (no signals) ---"

TMPDIR_5="$(setup_paired_repos)"
(cd "$TMPDIR_5/local" && PATH="$TMPDIR_5/local/bin:$PATH" TEST_HOSTNAME=pc-A \
    ./.aitask-scripts/aitask_lock.sh --init >/dev/null 2>&1)

output5=$(cd "$TMPDIR_5/local" && PATH="$TMPDIR_5/local/bin:$PATH" TEST_HOSTNAME=pc-A \
    ./.aitask-scripts/aitask_pick_own.sh 1 --email "alice@test.com" 2>&1)
exit5=$?

assert_eq "Fresh-pick exits 0" "0" "$exit5"
assert_contains "Fresh-pick emits OWNED" "OWNED:1" "$output5"
assert_not_contains "No LOCK_RECLAIM on fresh pick" "LOCK_RECLAIM" "$output5"
assert_not_contains "No RECLAIM_STATUS on fresh pick" "RECLAIM_STATUS" "$output5"

rm -rf "$TMPDIR_5"

# --- Test 6: Syntax checks ---
echo "--- Test 6: Syntax checks ---"

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
