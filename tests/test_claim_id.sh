#!/usr/bin/env bash
# test_claim_id.sh - Automated tests for aitask_claim_id.sh
# Run: bash tests/test_claim_id.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"

PASS=0
FAIL=0
TOTAL=0

# --- Test helpers ---
# Core helpers (assert_eq, assert_contains[_ci], assert_exit_zero/nonzero) live
# in tests/lib/asserts.sh. This file's original assert_contains was
# case-insensitive (grep -qi); its call sites are remapped to assert_contains_ci.
. "$PROJECT_DIR/tests/lib/asserts.sh"

# Create a paired repo setup: bare "remote" + local clone with task files
setup_paired_repos() {
    local tmpdir
    tmpdir="$(mktemp -d)"

    # Create bare "remote" repo
    local remote_dir="$tmpdir/remote.git"
    git init --bare --quiet "$remote_dir"

    # Create local working repo
    local local_dir="$tmpdir/local"
    git clone --quiet "$remote_dir" "$local_dir"
    (
        cd "$local_dir"
        git config user.email "test@test.com"
        git config user.name "Test"

        # Create task directory structure with some tasks
        mkdir -p aitasks/archived
        echo "---" > aitasks/t1_first_task.md
        echo "---" > aitasks/t2_second_task.md
        echo "---" > aitasks/t3_third_task.md
        echo "---" > aitasks/t4_fourth_task.md
        echo "---" > aitasks/t5_fifth_task.md

        # Copy the scripts we need
        setup_fake_aitask_repo "$PWD"
        cp "$PROJECT_DIR/.aitask-scripts/aitask_claim_id.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/lib/archive_scan.sh" .aitask-scripts/lib/
        chmod +x .aitask-scripts/aitask_claim_id.sh

        git add -A
        git commit -m "Initial setup" --quiet
        git push --quiet 2>/dev/null
    )

    echo "$tmpdir"
}

# Create a second clone of the same remote
clone_second_local() {
    local tmpdir="$1"
    local remote_dir="$tmpdir/remote.git"
    local local2_dir="$tmpdir/local2"

    git clone --quiet "$remote_dir" "$local2_dir"
    (
        cd "$local2_dir"
        git config user.email "test2@test.com"
        git config user.name "Test2"

        # Copy scripts
        setup_fake_aitask_repo "$PWD"
        cp "$PROJECT_DIR/.aitask-scripts/aitask_claim_id.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/lib/archive_scan.sh" .aitask-scripts/lib/
        chmod +x .aitask-scripts/aitask_claim_id.sh
    )

    echo "$local2_dir"
}

# Disable strict mode for test error handling
set +e

echo "=== aitask_claim_id.sh Tests ==="
echo ""

# --- Test 1: Init creates branch ---
echo "--- Test 1: Init creates branch ---"

TMPDIR_1="$(setup_paired_repos)"
output=$(cd "$TMPDIR_1/local" && ./.aitask-scripts/aitask_claim_id.sh --init 2>&1)

# Branch should exist on remote
branch_exists=$(git -C "$TMPDIR_1/local" ls-remote --heads origin aitask-ids 2>/dev/null | grep -c "aitask-ids")
assert_eq "Branch exists on remote" "1" "$branch_exists"

# Counter should be max(5) + 1 = 6
counter_val=$(cd "$TMPDIR_1/local" && git fetch origin aitask-ids --quiet 2>/dev/null && git show origin/aitask-ids:next_id.txt 2>/dev/null | tr -d '[:space:]')
assert_eq "Counter initialized to max+1" "6" "$counter_val"

assert_contains_ci "Output mentions counter value" "6" "$output"

rm -rf "$TMPDIR_1"

# --- Test 2: Init is idempotent ---
echo "--- Test 2: Init is idempotent ---"

TMPDIR_2="$(setup_paired_repos)"
(cd "$TMPDIR_2/local" && ./.aitask-scripts/aitask_claim_id.sh --init >/dev/null 2>&1)
output2=$(cd "$TMPDIR_2/local" && ./.aitask-scripts/aitask_claim_id.sh --init 2>&1)

assert_contains_ci "Idempotent init says already exists" "already exists" "$output2"

rm -rf "$TMPDIR_2"

# --- Test 3: Claim returns correct ID ---
echo "--- Test 3: Claim returns correct ID ---"

TMPDIR_3="$(setup_paired_repos)"
(cd "$TMPDIR_3/local" && ./.aitask-scripts/aitask_claim_id.sh --init >/dev/null 2>&1)
claimed=$(cd "$TMPDIR_3/local" && ./.aitask-scripts/aitask_claim_id.sh --claim 2>/dev/null)
assert_eq "First claim returns 6" "6" "$claimed"

rm -rf "$TMPDIR_3"

# --- Test 4: Sequential claims ---
echo "--- Test 4: Sequential claims ---"

TMPDIR_4="$(setup_paired_repos)"
(cd "$TMPDIR_4/local" && ./.aitask-scripts/aitask_claim_id.sh --init >/dev/null 2>&1)
c1=$(cd "$TMPDIR_4/local" && ./.aitask-scripts/aitask_claim_id.sh --claim 2>/dev/null)
c2=$(cd "$TMPDIR_4/local" && ./.aitask-scripts/aitask_claim_id.sh --claim 2>/dev/null)
c3=$(cd "$TMPDIR_4/local" && ./.aitask-scripts/aitask_claim_id.sh --claim 2>/dev/null)
assert_eq "First sequential claim" "6" "$c1"
assert_eq "Second sequential claim" "7" "$c2"
assert_eq "Third sequential claim" "8" "$c3"

rm -rf "$TMPDIR_4"

# --- Test 5: Counter file integrity ---
echo "--- Test 5: Counter file integrity ---"

TMPDIR_5="$(setup_paired_repos)"
(cd "$TMPDIR_5/local" && ./.aitask-scripts/aitask_claim_id.sh --init >/dev/null 2>&1)
(cd "$TMPDIR_5/local" && ./.aitask-scripts/aitask_claim_id.sh --claim >/dev/null 2>&1)
(cd "$TMPDIR_5/local" && ./.aitask-scripts/aitask_claim_id.sh --claim >/dev/null 2>&1)

counter_after=$(cd "$TMPDIR_5/local" && git fetch origin aitask-ids --quiet 2>/dev/null && git show origin/aitask-ids:next_id.txt 2>/dev/null | tr -d '[:space:]')
assert_eq "Counter is 8 after 2 claims from 6" "8" "$counter_after"

rm -rf "$TMPDIR_5"

# --- Test 6: Race simulation ---
echo "--- Test 6: Race simulation ---"

TMPDIR_6="$(setup_paired_repos)"
(cd "$TMPDIR_6/local" && ./.aitask-scripts/aitask_claim_id.sh --init >/dev/null 2>&1)

local2_dir=$(clone_second_local "$TMPDIR_6")

# Run claims simultaneously from two "PCs"
(cd "$TMPDIR_6/local" && ./.aitask-scripts/aitask_claim_id.sh --claim 2>/dev/null) > "$TMPDIR_6/result1" &
pid1=$!
(cd "$local2_dir" && ./.aitask-scripts/aitask_claim_id.sh --claim 2>/dev/null) > "$TMPDIR_6/result2" &
pid2=$!

wait $pid1
wait $pid2

r1=$(cat "$TMPDIR_6/result1" | tr -d '[:space:]')
r2=$(cat "$TMPDIR_6/result2" | tr -d '[:space:]')

TOTAL=$((TOTAL + 1))
if [[ -n "$r1" && -n "$r2" && "$r1" != "$r2" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Race simulation - expected unique IDs, got '$r1' and '$r2'"
fi

rm -rf "$TMPDIR_6"

# --- Test 7: No remote = local branch counter ---
echo "--- Test 7: No remote = local branch counter ---"

TMPDIR_7="$(mktemp -d)"
(
    cd "$TMPDIR_7"
    git init --quiet
    git config user.email "test@test.com"
    git config user.name "Test"
    mkdir -p aitasks/archived
    setup_fake_aitask_repo "$PWD"
    echo "---" > aitasks/t1_first.md
    echo "---" > aitasks/t3_third.md
    cp "$PROJECT_DIR/.aitask-scripts/aitask_claim_id.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_scan.sh" .aitask-scripts/lib/
    chmod +x .aitask-scripts/aitask_claim_id.sh
    echo "init" > dummy.txt && git add dummy.txt && git commit -m "init" --quiet
)

# First claim: auto-creates local branch (max=3, counter starts at 4, claims 4)
claimed7a=$(cd "$TMPDIR_7" && ./.aitask-scripts/aitask_claim_id.sh --claim 2>/dev/null)
assert_eq "No remote: first claim returns max+1" "4" "$claimed7a"

# Second claim: counter advances monotonically (claims 5)
claimed7b=$(cd "$TMPDIR_7" && ./.aitask-scripts/aitask_claim_id.sh --claim 2>/dev/null)
assert_eq "No remote: sequential claim is monotonic" "5" "$claimed7b"

# Local branch should exist
TOTAL=$((TOTAL + 1))
if (cd "$TMPDIR_7" && git show-ref --verify --quiet refs/heads/aitask-ids); then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: No remote: local aitask-ids branch should exist"
fi

rm -rf "$TMPDIR_7"

# --- Test 8: Init scans archived tasks ---
echo "--- Test 8: Init scans archived tasks ---"

TMPDIR_8="$(setup_paired_repos)"
(
    cd "$TMPDIR_8/local"
    echo "---" > aitasks/archived/t50_archived_task.md
    git add -A && git commit -m "Add archived" --quiet && git push --quiet 2>/dev/null
)
output8=$(cd "$TMPDIR_8/local" && ./.aitask-scripts/aitask_claim_id.sh --init 2>&1)
counter8=$(cd "$TMPDIR_8/local" && git fetch origin aitask-ids --quiet 2>/dev/null && git show origin/aitask-ids:next_id.txt 2>/dev/null | tr -d '[:space:]')
assert_eq "Counter scans archived: max(50)+1=51" "51" "$counter8"

rm -rf "$TMPDIR_8"

# --- Test 9: Init scans tar archive ---
echo "--- Test 9: Init scans tar archive ---"

TMPDIR_9="$(setup_paired_repos)"
(
    cd "$TMPDIR_9/local"
    mkdir -p /tmp/tartest_$$
    echo "---" > "/tmp/tartest_$$/t100_old_task.md"
    tar -cf - -C "/tmp/tartest_$$" t100_old_task.md | zstd -q -o aitasks/archived/old.tar.zst
    rm -rf "/tmp/tartest_$$"
    git add -A && git commit -m "Add tar" --quiet && git push --quiet 2>/dev/null
)
output9=$(cd "$TMPDIR_9/local" && ./.aitask-scripts/aitask_claim_id.sh --init 2>&1)
counter9=$(cd "$TMPDIR_9/local" && git fetch origin aitask-ids --quiet 2>/dev/null && git show origin/aitask-ids:next_id.txt 2>/dev/null | tr -d '[:space:]')
assert_eq "Counter scans tar: max(100)+1=101" "101" "$counter9"

rm -rf "$TMPDIR_9"

# --- Test 10: Syntax check ---
echo "--- Test 10: Syntax check ---"

assert_exit_zero "Syntax check passes" bash -n "$PROJECT_DIR/.aitask-scripts/aitask_claim_id.sh"

# --- Test 11: No remote = init still fails ---
echo "--- Test 11: No remote = init still fails ---"

TMPDIR_11="$(mktemp -d)"
(
    cd "$TMPDIR_11"
    git init --quiet
    git config user.email "test@test.com"
    git config user.name "Test"
    setup_fake_aitask_repo "$PWD"
    cp "$PROJECT_DIR/.aitask-scripts/aitask_claim_id.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_scan.sh" .aitask-scripts/lib/
    chmod +x .aitask-scripts/aitask_claim_id.sh
    echo "init" > dummy.txt && git add dummy.txt && git commit -m "init" --quiet
)
assert_exit_nonzero "Init with no remote fails" bash -c "cd '$TMPDIR_11' && ./.aitask-scripts/aitask_claim_id.sh --init"

rm -rf "$TMPDIR_11"

# --- Test 12: No remote = peek shows counter value ---
echo "--- Test 12: No remote = peek shows counter value ---"

TMPDIR_12="$(mktemp -d)"
(
    cd "$TMPDIR_12"
    git init --quiet
    git config user.email "test@test.com"
    git config user.name "Test"
    mkdir -p aitasks/archived
    setup_fake_aitask_repo "$PWD"
    echo "---" > aitasks/t10_task.md
    cp "$PROJECT_DIR/.aitask-scripts/aitask_claim_id.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_scan.sh" .aitask-scripts/lib/
    chmod +x .aitask-scripts/aitask_claim_id.sh
    echo "init" > dummy.txt && git add dummy.txt && git commit -m "init" --quiet
)
# Peek before any claim: no local branch yet, shows max+1
peek12a=$(cd "$TMPDIR_12" && ./.aitask-scripts/aitask_claim_id.sh --peek 2>/dev/null)
assert_eq "Peek with no remote (no branch): max+1=11" "11" "$peek12a"

# After a claim, peek shows counter from local branch
(cd "$TMPDIR_12" && ./.aitask-scripts/aitask_claim_id.sh --claim >/dev/null 2>&1)
peek12b=$(cd "$TMPDIR_12" && ./.aitask-scripts/aitask_claim_id.sh --peek 2>/dev/null)
assert_eq "Peek with no remote (after claim): counter=12" "12" "$peek12b"

rm -rf "$TMPDIR_12"

# --- Test 13: No remote, no existing tasks ---
echo "--- Test 13: No remote, no existing tasks ---"

TMPDIR_13="$(mktemp -d)"
(
    cd "$TMPDIR_13"
    git init --quiet
    git config user.email "test@test.com"
    git config user.name "Test"
    mkdir -p aitasks/archived
    setup_fake_aitask_repo "$PWD"
    cp "$PROJECT_DIR/.aitask-scripts/aitask_claim_id.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_scan.sh" .aitask-scripts/lib/
    chmod +x .aitask-scripts/aitask_claim_id.sh
    echo "init" > dummy.txt && git add dummy.txt && git commit -m "init" --quiet
)
# max=0, counter starts at 1, first claim returns 1
claimed13=$(cd "$TMPDIR_13" && ./.aitask-scripts/aitask_claim_id.sh --claim 2>/dev/null)
assert_eq "No remote, no tasks: returns 1" "1" "$claimed13"

rm -rf "$TMPDIR_13"

# --- Test 14: Auto-upgrade local branch to remote ---
echo "--- Test 14: Auto-upgrade local branch to remote ---"

# Start with no remote, create some IDs
TMPDIR_14="$(mktemp -d)"
(
    cd "$TMPDIR_14"
    git init --bare --quiet remote.git
    git init --quiet local
    cd local
    git config user.email "test@test.com"
    git config user.name "Test"
    mkdir -p aitasks/archived
    setup_fake_aitask_repo "$PWD"
    echo "---" > aitasks/t1_task.md
    cp "$PROJECT_DIR/.aitask-scripts/aitask_claim_id.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_scan.sh" .aitask-scripts/lib/
    chmod +x .aitask-scripts/aitask_claim_id.sh
    echo "init" > dummy.txt && git add -A && git commit -m "init" --quiet
)

# Claim locally (no remote) — should create local branch and return 2 (max=1)
claimed14a=$(cd "$TMPDIR_14/local" && ./.aitask-scripts/aitask_claim_id.sh --claim 2>/dev/null)
assert_eq "Auto-upgrade: local claim returns 2" "2" "$claimed14a"

# Now add a remote
(cd "$TMPDIR_14/local" && git remote add origin "$TMPDIR_14/remote.git" && git push --quiet origin main 2>/dev/null)

# Next claim should auto-push local branch to remote and use remote CAS
claimed14b=$(cd "$TMPDIR_14/local" && ./.aitask-scripts/aitask_claim_id.sh --claim 2>/dev/null)
assert_eq "Auto-upgrade: remote claim returns 3" "3" "$claimed14b"

# Verify branch now exists on remote
TOTAL=$((TOTAL + 1))
if (cd "$TMPDIR_14/local" && git ls-remote --heads origin aitask-ids 2>/dev/null | grep -q aitask-ids); then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Auto-upgrade: aitask-ids branch should exist on remote"
fi

rm -rf "$TMPDIR_14"

# --- Test 15: Fetch failure with existing remote branch (no auto-upgrade loop) ---
echo "--- Test 15: Fetch failure with existing remote branch ---"

TMPDIR_15="$(setup_paired_repos)"
(cd "$TMPDIR_15/local" && ./.aitask-scripts/aitask_claim_id.sh --init >/dev/null 2>&1)

# Build a git shim that fails 'git fetch' but passes everything else (incl.
# 'git ls-remote') through to real git. This reproduces the live bug: a fetch
# failure while the remote counter branch is healthy. ls-remote does not write
# .git/FETCH_HEAD, so it still reports the branch PRESENT.
REAL_GIT="$(command -v git)"
SHIM_DIR_15="$TMPDIR_15/shim"
mkdir -p "$SHIM_DIR_15"
cat > "$SHIM_DIR_15/git" <<EOF
#!/usr/bin/env bash
if [[ "\$1" == "fetch" ]]; then
    echo "fatal: could not write to '.git/FETCH_HEAD': simulated failure" >&2
    exit 128
fi
exec "$REAL_GIT" "\$@"
EOF
chmod +x "$SHIM_DIR_15/git"

claim15_out=$(cd "$TMPDIR_15/local" && PATH="$SHIM_DIR_15:$PATH" ./.aitask-scripts/aitask_claim_id.sh --claim 2>&1)
claim15_rc=$?

assert_exit_nonzero_rc "Claim fails when fetch errors but branch exists" "$claim15_rc"
assert_contains "Surfaces the real fetch error verbatim" "FETCH_HEAD" "$claim15_out"
assert_not_contains "No misleading auto-upgrade message" "auto-upgrade" "$claim15_out"
assert_not_contains "No misleading retry-exhaustion message" "5 attempts" "$claim15_out"
assert_not_contains "No spurious 'ait setup' suggestion" "ait setup" "$claim15_out"

# Counter must be untouched — the failed claim consumed no ID.
counter15=$(cd "$TMPDIR_15/local" && git fetch origin aitask-ids --quiet 2>/dev/null && git show origin/aitask-ids:next_id.txt 2>/dev/null | tr -d '[:space:]')
assert_eq "Counter unchanged after failed claim" "6" "$counter15"

rm -rf "$TMPDIR_15"

# --- Test 16: Remote unreachable (ls-remote also fails) ---
echo "--- Test 16: Remote unreachable (ls-remote also fails) ---"

TMPDIR_16="$(setup_paired_repos)"
(cd "$TMPDIR_16/local" && ./.aitask-scripts/aitask_claim_id.sh --init >/dev/null 2>&1)

# Shim fails both 'fetch' and 'ls-remote' — a genuine connectivity failure. The
# claim must report it as such, NOT auto-upgrade or suggest 'ait setup'.
REAL_GIT="$(command -v git)"
SHIM_DIR_16="$TMPDIR_16/shim"
mkdir -p "$SHIM_DIR_16"
cat > "$SHIM_DIR_16/git" <<EOF
#!/usr/bin/env bash
if [[ "\$1" == "fetch" || "\$1" == "ls-remote" ]]; then
    echo "fatal: unable to access remote: simulated connectivity failure" >&2
    exit 128
fi
exec "$REAL_GIT" "\$@"
EOF
chmod +x "$SHIM_DIR_16/git"

claim16_out=$(cd "$TMPDIR_16/local" && PATH="$SHIM_DIR_16:$PATH" ./.aitask-scripts/aitask_claim_id.sh --claim 2>&1)
claim16_rc=$?

assert_exit_nonzero_rc "Claim fails when origin is unreachable" "$claim16_rc"
assert_contains "Reports the unreachable-origin error" "Cannot reach origin" "$claim16_out"
assert_not_contains "No auto-upgrade attempt on unreachable origin" "auto-upgrade" "$claim16_out"
assert_not_contains "No spurious 'ait setup' on connectivity failure" "ait setup" "$claim16_out"

rm -rf "$TMPDIR_16"

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
