#!/usr/bin/env bash
# test_agentcrew_terminal_push.sh - Regression test for t653_3.
#
# Verifies that `ait crew status set` pushes the worktree on terminal
# transitions (Completed/Aborted/Error), and that --no-push suppresses it.
#
# Run: bash tests/test_agentcrew_terminal_push.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ORIG_DIR="$(pwd)"

PASS=0
FAIL=0

pass() { PASS=$((PASS + 1)); echo "PASS: $1"; }
fail() { FAIL=$((FAIL + 1)); echo "FAIL: $1"; }

TMPROOT="$(mktemp -d "${TMPDIR:-/tmp}/aitask_test_terminal_push_XXXXXX")"
trap 'cd "$ORIG_DIR"; rm -rf "$TMPROOT"' EXIT

cd "$TMPROOT"
git init -q
git config user.email "test@example.com"
git config user.name "Test User"
git commit -q --allow-empty -m "init"

CREW_DIR=".aitask-crews/crew-test_crew"
mkdir -p "$CREW_DIR"

# Seed agent _status.yaml in Running state
cat > "$CREW_DIR/foo_status.yaml" <<EOF
agent_name: foo
status: Running
progress: 50
EOF
# Seed _crew_status.yaml so _recompute_crew_status has a target
cat > "$CREW_DIR/_crew_status.yaml" <<EOF
status: Running
updated_at: 2026-04-26 00:00:00
progress: 0
EOF
git add -A && git commit -q -m "seed foo"

run_status_set() {
    # Bypass `ait` (which cd's to its own repo) and call the Python script
    # directly so the synthetic crew at $TMPROOT/.aitask-crews/ is found.
    python3 "$PROJECT_DIR/.aitask-scripts/agentcrew/agentcrew_status.py" "$@" >/dev/null 2>&1
}

# --- Test 1: terminal transition without --no-push commits a new revision ---
HASH_BEFORE="$(git rev-parse HEAD)"
run_status_set --crew test_crew --agent foo set --status Completed || true
HASH_AFTER="$(git rev-parse HEAD)"

if grep -q "^status: Completed" "$CREW_DIR/foo_status.yaml"; then
    pass "agent status flipped to Completed"
else
    fail "agent status did not flip to Completed"
fi

if [[ "$HASH_BEFORE" != "$HASH_AFTER" ]]; then
    pass "terminal transition created a new commit"
else
    fail "terminal transition did not create a commit"
fi

# Confirm the commit message reflects the transition
COMMIT_MSG="$(git log -1 --pretty=format:%s)"
if [[ "$COMMIT_MSG" == *"foo: Running -> Completed"* ]]; then
    pass "commit message describes transition"
else
    fail "commit message missing transition: '$COMMIT_MSG'"
fi

# --- Test 2: --no-push suppresses the commit ---
cat > "$CREW_DIR/bar_status.yaml" <<EOF
agent_name: bar
status: Running
EOF
git add -A && git commit -q -m "seed bar"
HASH_BEFORE="$(git rev-parse HEAD)"

run_status_set --crew test_crew --agent bar set --status Completed --no-push || true

HASH_AFTER="$(git rev-parse HEAD)"
if [[ "$HASH_BEFORE" == "$HASH_AFTER" ]]; then
    pass "--no-push did not create a commit"
else
    fail "--no-push unexpectedly created a commit"
fi

if grep -q "^status: Completed" "$CREW_DIR/bar_status.yaml"; then
    pass "--no-push still wrote the YAML status"
else
    fail "--no-push prevented YAML write"
fi

# --- Test 3: non-terminal transition does NOT push ---
# Reset foo so we can test a non-terminal write. Seed a Waiting agent and
# transition to Ready (a non-terminal state).
cat > "$CREW_DIR/baz_status.yaml" <<EOF
agent_name: baz
status: Waiting
EOF
git add -A && git commit -q -m "seed baz"
HASH_BEFORE="$(git rev-parse HEAD)"

run_status_set --crew test_crew --agent baz set --status Ready || true

HASH_AFTER="$(git rev-parse HEAD)"
if [[ "$HASH_BEFORE" == "$HASH_AFTER" ]]; then
    pass "non-terminal transition did not push"
else
    fail "non-terminal transition unexpectedly pushed"
fi

# --- Summary ---
TOTAL=$((PASS + FAIL))
echo ""
echo "=========================================="
echo "Test Summary: $PASS/$TOTAL passed"
if [[ $FAIL -gt 0 ]]; then
    echo "FAILED: $FAIL test(s) failed"
    exit 1
fi
echo "All tests passed!"
exit 0
