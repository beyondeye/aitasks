#!/usr/bin/env bash
# test_crew_cleanup.sh - Tests that `ait crew cleanup` derives terminal state
# from member agent status files, so a stale persisted _crew_status.yaml never
# blocks (or wrongly permits) cleanup (t1041).
# Run: bash tests/test_crew_cleanup.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ORIG_DIR="$(pwd)"

COUNTER_FILE="$(mktemp "${TMPDIR:-/tmp}/ait_test_counters_XXXXXX")"
echo "0 0 0" > "$COUNTER_FILE"
trap 'rm -f "$COUNTER_FILE"' EXIT

_inc_pass() {
    local p f t
    read -r p f t < "$COUNTER_FILE"
    echo "$((p + 1)) $f $((t + 1))" > "$COUNTER_FILE"
}
_inc_fail() {
    local p f t
    read -r p f t < "$COUNTER_FILE"
    echo "$p $((f + 1)) $((t + 1))" > "$COUNTER_FILE"
}

# File-based assertion (counters live in COUNTER_FILE; tests run in subshells).
_check_contains() {
    local desc="$1" needle="$2" haystack="$3"
    if printf '%s' "$haystack" | grep -qF -- "$needle"; then
        _inc_pass
    else
        _inc_fail
        echo "FAIL: $desc (missing '$needle')"
        echo "----- output -----"; printf '%s\n' "$haystack"; echo "------------------"
    fi
}

setup_test_repo() {
    local tmpdir
    tmpdir="$(mktemp -d)"
    (
        cd "$tmpdir"
        git init --quiet
        git config user.email "test@test.com"
        git config user.name "Test"
        mkdir -p aitasks/metadata
        cp -R "$PROJECT_DIR/.aitask-scripts" .aitask-scripts
        find .aitask-scripts -type d -name __pycache__ -prune -exec rm -rf {} +
        chmod +x .aitask-scripts/aitask_crew_init.sh .aitask-scripts/aitask_crew_addwork.sh
        echo "email: test@test.com" > aitasks/metadata/userconfig.yaml
        git add -A
        git commit -m "Initial setup" --quiet
    )
    echo "$tmpdir"
}

cleanup_test_repo() {
    local tmpdir="$1"
    cd "$ORIG_DIR"
    if [[ -d "$tmpdir" ]]; then
        (cd "$tmpdir" && git worktree prune 2>/dev/null || true)
        rm -rf "$tmpdir"
    fi
}

# Init a crew with one member agent, then force the member + persisted crew
# status to the given values (bypassing the recompute, simulating a dead runner).
_seed_crew() {
    local cid="$1" member_status="$2" persisted_status="$3" persisted_progress="$4"
    bash .aitask-scripts/aitask_crew_init.sh --id "$cid" --add-type impl:claudecode/opus4_6 --batch >/dev/null 2>&1
    echo "# work" > /tmp/clean_work2do.md
    bash .aitask-scripts/aitask_crew_addwork.sh --crew "$cid" --name worker --work2do /tmp/clean_work2do.md --type impl --batch >/dev/null 2>&1
    rm -f /tmp/clean_work2do.md
    local mf=".aitask-crews/crew-$cid/worker_status.yaml"
    sed "s/^status: .*/status: $member_status/" "$mf" > "$mf.tmp" && mv "$mf.tmp" "$mf"
    local cf=".aitask-crews/crew-$cid/_crew_status.yaml"
    sed -e "s/^status: .*/status: $persisted_status/" -e "s/^progress: .*/progress: $persisted_progress/" \
        "$cf" > "$cf.tmp" && mv "$cf.tmp" "$cf"
}

echo "=== AgentCrew Cleanup (member-derived terminal) Tests ==="

# --- Test 1: stale persisted Running/80 + member Completed -> CLEANED ---
echo "Test 1: stale persisted Running but member Completed -> cleaned"
T1="$(setup_test_repo)"
(
    cd "$T1"
    _seed_crew stale Completed Running 80
    output=$(bash .aitask-scripts/aitask_crew_cleanup.sh --crew stale --batch 2>&1) || true
    _check_contains "stale crew cleaned" "CLEANED:stale" "$output"
    if [[ ! -d ".aitask-crews/crew-stale" ]]; then _inc_pass; else _inc_fail; echo "FAIL: worktree should be gone"; fi
)
cleanup_test_repo "$T1"

# --- Test 2: all-Aborted member -> CLEANED ---
echo "Test 2: all-aborted member -> cleaned"
T2="$(setup_test_repo)"
(
    cd "$T2"
    _seed_crew killed Aborted Killing 40
    output=$(bash .aitask-scripts/aitask_crew_cleanup.sh --crew killed --batch 2>&1) || true
    _check_contains "aborted crew cleaned" "CLEANED:killed" "$output"
)
cleanup_test_repo "$T2"

# --- Test 3: member still Running -> NOT_TERMINAL with stable reason ---
echo "Test 3: member Running -> NOT_TERMINAL:members_not_terminal"
T3="$(setup_test_repo)"
(
    cd "$T3"
    _seed_crew busy Running Completed 100   # persisted lies "Completed"; member is Running
    output=$(bash .aitask-scripts/aitask_crew_cleanup.sh --crew busy --batch 2>&1) || true
    _check_contains "running member refused" "NOT_TERMINAL:busy:members_not_terminal" "$output"
    if [[ -d ".aitask-crews/crew-busy" ]]; then _inc_pass; else _inc_fail; echo "FAIL: worktree should still exist"; fi
)
cleanup_test_repo "$T3"

# --- Test 4: no-member crew falls back to persisted status (Completed -> cleaned) ---
echo "Test 4: no-member persisted-Completed crew -> cleaned (fallback)"
T4="$(setup_test_repo)"
(
    cd "$T4"
    bash .aitask-scripts/aitask_crew_init.sh --id empty --batch >/dev/null 2>&1
    cf=".aitask-crews/crew-empty/_crew_status.yaml"
    sed 's/^status: .*/status: Completed/' "$cf" > "$cf.tmp" && mv "$cf.tmp" "$cf"
    output=$(bash .aitask-scripts/aitask_crew_cleanup.sh --crew empty --batch 2>&1) || true
    _check_contains "empty completed crew cleaned" "CLEANED:empty" "$output"
)
cleanup_test_repo "$T4"

# --- Summary ---
read -r PASS FAIL TOTAL < "$COUNTER_FILE"
echo ""
echo "=== Results: $PASS/$TOTAL passed, $FAIL failed ==="
[[ "$FAIL" -eq 0 ]]
