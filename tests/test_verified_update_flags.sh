#!/usr/bin/env bash
# test_verified_update_flags.sh - Tests for --agent/--cli-id flags on aitask_verified_update.sh
# Run: bash tests/test_verified_update_flags.sh
#
# Every call runs in a scaffolded throwaway repo with no remote (t1937). The
# script records a real verified score and, in a repo with a remote, commits
# and pushes it — run against this checkout it wrote junk scores into the real
# models_claudecode.json and pushed them to origin/aitask-data.

# Clear env-var fast-path so resolver honors --cli-id / --agent-string flags.
unset AITASK_AGENT_STRING

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"

# Shared assertion helpers (see tests/lib/asserts.sh).
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

# shellcheck source=lib/metadata_update_fixture.sh
. "$PROJECT_DIR/tests/lib/metadata_update_fixture.sh"

PASS=0
FAIL=0
TOTAL=0

REPO="$(setup_local_metadata_repo aitask_verified_update.sh)"
trap 'rm -rf "$REPO"' EXIT
# The --agent/--cli-id path resolves through this helper.
cp "$PROJECT_DIR/.aitask-scripts/aitask_resolve_detected_agent.sh" "$REPO/.aitask-scripts/"
REGISTRY="$REPO/aitasks/metadata/models_claudecode.json"

# --- Test helpers ---

# run_update <args...> — run the updater inside the fixture; sets OUT and RC.
run_update() {
    RC=0
    OUT=$(cd "$REPO" && ./.aitask-scripts/aitask_verified_update.sh "$@" --silent 2>&1) || RC=$?
}

registry_get() {
    jq -r "$1" "$REGISTRY"
}

# --- Tests ---

echo "=== Fixture has no remote ==="
assert_eq "fixture repo has no remote to push to" "" "$(git -C "$REPO" remote)"

echo "=== Test: --agent/--cli-id resolves and updates ==="
run_update --agent claudecode --cli-id claude-opus-4-6 --skill test_414_flags --score 5
assert_exit_zero_rc "agent/cli-id exits 0" "$RC"
assert_contains "agent/cli-id resolves to UPDATED" "UPDATED:claudecode/opus4_6:test_414_flags:100" "$OUT"
assert_eq "agent/cli-id score written to the fixture registry" "100" \
    "$(registry_get '.models[0].verified.test_414_flags')"

echo "=== Test: --agent-string backward compat ==="
run_update --agent-string claudecode/opus4_6 --skill test_414_flags --score 4
assert_exit_zero_rc "agent-string exits 0" "$RC"
assert_contains "agent-string still works" "UPDATED:claudecode/opus4_6:test_414_flags:90" "$OUT"
assert_eq "agent-string run added to the fixture registry" "2" \
    "$(registry_get '.models[0].verifiedstats.test_414_flags.all_time.runs')"

# Every rejection below must leave the registry byte-identical.
BEFORE="$(cat "$REGISTRY")"

echo "=== Test: --agent-string and --agent together errors ==="
run_update --agent-string claudecode/opus4_6 --agent claudecode --cli-id claude-opus-4-6 --skill test_414_flags --score 3
assert_exit_nonzero_rc "mutual exclusion exits non-zero" "$RC"
assert_contains "mutual exclusion error" "cannot be combined" "$OUT"
assert_eq "mutual exclusion leaves the registry unchanged" "$BEFORE" "$(cat "$REGISTRY")"

echo "=== Test: --agent without --cli-id errors ==="
run_update --agent claudecode --skill test_414_flags --score 3
assert_exit_nonzero_rc "missing cli-id exits non-zero" "$RC"
assert_contains "missing cli-id error" "--cli-id is required" "$OUT"
assert_eq "missing cli-id leaves the registry unchanged" "$BEFORE" "$(cat "$REGISTRY")"

echo "=== Test: --cli-id without --agent errors ==="
run_update --cli-id claude-opus-4-6 --skill test_414_flags --score 3
assert_exit_nonzero_rc "missing agent exits non-zero" "$RC"
assert_contains "missing agent error" "Either --agent-string or --agent/--cli-id is required" "$OUT"
assert_eq "missing agent leaves the registry unchanged" "$BEFORE" "$(cat "$REGISTRY")"

echo "=== Test: neither --agent-string nor --agent errors ==="
run_update --skill test_414_flags --score 3
assert_exit_nonzero_rc "no agent identifier exits non-zero" "$RC"
assert_contains "no agent identifier error" "Either --agent-string or --agent/--cli-id is required" "$OUT"
assert_eq "no agent identifier leaves the registry unchanged" "$BEFORE" "$(cat "$REGISTRY")"

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
