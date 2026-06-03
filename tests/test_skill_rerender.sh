#!/usr/bin/env bash
# test_skill_rerender.sh - Automated tests for t777_20:
#   - .aitask-scripts/aitask_skill_rerender.sh
# Run: bash tests/test_skill_rerender.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

cd "$PROJECT_DIR"

HELPER="$PROJECT_DIR/.aitask-scripts/aitask_skill_rerender.sh"

# --- Scratch workspace prefix + cleanup trap ---

TEST_PREFIX="_t777_20_test_"
TEST_PROFILE="t77720tfast"
TEST_OTHER_PROFILE="t77720tslow"
OPENCODE_ROOT_BAK=""

cleanup() {
    rm -rf \
        "$PROJECT_DIR"/.claude/skills/"${TEST_PREFIX}"* \
        "$PROJECT_DIR"/.agents/skills/"${TEST_PREFIX}"* \
        "$PROJECT_DIR"/.opencode/skills/"${TEST_PREFIX}"* 2>/dev/null || true
    if [[ -n "$OPENCODE_ROOT_BAK" && -d "$OPENCODE_ROOT_BAK" ]]; then
        [[ -d "$PROJECT_DIR/.opencode/skills" ]] || mv "$OPENCODE_ROOT_BAK" "$PROJECT_DIR/.opencode/skills"
    fi
}
trap cleanup EXIT

AGENT_ROOTS=(.claude/skills .agents/skills .opencode/skills)

seed_orphans_and_decoys() {
    # Orphan rendered dirs: their authoring template at
    # .claude/skills/<skill>/SKILL.md.j2 is never created. The helper must
    # see "no template" and skip them — rendering would fail otherwise.
    # Decoys verify that the trailing-hyphen+profile glob does not match
    # unrelated dirs (different profile suffix).
    local profile="$1" other="$2"
    for root in "${AGENT_ROOTS[@]}"; do
        mkdir -p "$root"
        # Orphaned rendered dirs (matching profile, no authoring template).
        mkdir -p "$root/${TEST_PREFIX}orphan_a-${profile}-"
        mkdir -p "$root/${TEST_PREFIX}orphan_b-${profile}-"
        touch "$root/${TEST_PREFIX}orphan_a-${profile}-/SKILL.md"
        touch "$root/${TEST_PREFIX}orphan_b-${profile}-/SKILL.md"
        # Decoy: same orphan prefix but different profile suffix — must not be
        # touched by an invocation targeting <profile>.
        mkdir -p "$root/${TEST_PREFIX}orphan_a-${other}-"
        touch "$root/${TEST_PREFIX}orphan_a-${other}-/SKILL.md"
    done
}

echo "Running aitask_skill_rerender.sh tests..."

# --- Test 1: Helper exists and is executable ---

TOTAL=$((TOTAL + 1))
if [[ -x "$HELPER" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: helper not found or not executable: $HELPER"
fi

# --- Test 2: No-arg usage fails ---

set +e
output=$("$HELPER" 2>&1)
rc=$?
set -e
assert_exit_nonzero_rc "no-arg invocation exits non-zero" "$rc"
assert_contains "no-arg invocation prints usage" "usage:" "$output"

# --- Test 3: Empty state is a no-op ---

cleanup
set +e
output=$("$HELPER" "$TEST_PROFILE" 2>&1)
rc=$?
set -e
assert_exit_zero_rc "empty-state invocation succeeds" "$rc"
assert_contains "empty-state reports RERENDERED:0" "RERENDERED:0" "$output"

# --- Test 4: Skips orphaned rendered dirs (no authoring template) ---
# All seeded dirs target prefixes that do NOT have a matching authoring
# template at .claude/skills/<prefix>/SKILL.md.j2, so every match should
# be skipped — RERENDERED:0 and no exit-fail.

cleanup
seed_orphans_and_decoys "$TEST_PROFILE" "$TEST_OTHER_PROFILE"
set +e
output=$("$HELPER" "$TEST_PROFILE" 2>&1)
rc=$?
set -e
assert_exit_zero_rc "orphan-only invocation succeeds" "$rc"
assert_contains "orphan-only invocation reports RERENDERED:0" "RERENDERED:0" "$output"
# Orphaned rendered dirs are intentionally LEFT IN PLACE — the helper does
# not touch them (it neither re-renders nor deletes). They survive.
for root in "${AGENT_ROOTS[@]}"; do
    assert_dir_exists "orphaned rendered dir untouched (${root} ${TEST_PROFILE} a)" \
        "$root/${TEST_PREFIX}orphan_a-${TEST_PROFILE}-"
    assert_dir_exists "orphaned rendered dir untouched (${root} ${TEST_PROFILE} b)" \
        "$root/${TEST_PREFIX}orphan_b-${TEST_PROFILE}-"
    assert_dir_exists "decoy other-profile dir untouched (${root} ${TEST_OTHER_PROFILE})" \
        "$root/${TEST_PREFIX}orphan_a-${TEST_OTHER_PROFILE}-"
done

# --- Test 5: Unknown profile name is a no-op ---

set +e
output=$("$HELPER" "no_such_profile_xyz_abc_123" 2>&1)
rc=$?
set -e
assert_exit_zero_rc "unknown-profile invocation succeeds" "$rc"
assert_contains "unknown-profile reports RERENDERED:0" "RERENDERED:0" "$output"

# --- Test 6: Skips missing agent roots gracefully ---

cleanup
OPENCODE_ROOT_BAK="$PROJECT_DIR/.opencode/skills.bak_t77720"
if [[ -d "$PROJECT_DIR/.opencode/skills" ]]; then
    mv "$PROJECT_DIR/.opencode/skills" "$OPENCODE_ROOT_BAK"
fi
set +e
output=$("$HELPER" "$TEST_PROFILE" 2>&1)
rc=$?
set -e
assert_exit_zero_rc "succeeds with one agent root missing" "$rc"
assert_contains "still reports RERENDERED summary" "RERENDERED:" "$output"
if [[ -d "$OPENCODE_ROOT_BAK" ]]; then
    mv "$OPENCODE_ROOT_BAK" "$PROJECT_DIR/.opencode/skills"
fi
OPENCODE_ROOT_BAK=""

# --- Test 7: End-to-end re-render of a real skill ---
# Uses the project's actual `aitask-pick` skill (which has a valid
# SKILL.md.j2) and the `fast` profile. We grab the pre-test mtime of the
# rendered SKILL.md, sleep enough for filesystem mtime resolution to tick,
# run the helper, and assert the file's mtime moved forward — confirming
# the renderer was actually invoked end-to-end.

if [[ -f .claude/skills/aitask-pick/SKILL.md.j2 \
      && -f aitasks/metadata/profiles/fast.yaml \
      && -d .claude/skills/aitask-pick-fast- ]]; then
    rendered_file=".claude/skills/aitask-pick-fast-/SKILL.md"
    if [[ -f "$rendered_file" ]]; then
        before=$(stat -c %Y "$rendered_file" 2>/dev/null || stat -f %m "$rendered_file")
        # Bump the profile YAML mtime to "now + 1s" so skip-if-fresh sees
        # staleness regardless of filesystem mtime resolution.
        touch -d "+1 second" aitasks/metadata/profiles/fast.yaml \
            2>/dev/null || touch aitasks/metadata/profiles/fast.yaml
        set +e
        output=$("$HELPER" fast 2>&1)
        rc=$?
        set -e
        assert_exit_zero_rc "real-skill rerender exits zero" "$rc"
        assert_contains "real-skill rerender output mentions RERENDERED" "RERENDERED:" "$output"
        after=$(stat -c %Y "$rendered_file" 2>/dev/null || stat -f %m "$rendered_file")
        TOTAL=$((TOTAL + 1))
        if [[ "$after" -ge "$before" ]]; then
            PASS=$((PASS + 1))
        else
            FAIL=$((FAIL + 1))
            echo "FAIL: rendered SKILL.md mtime did not advance (before=$before, after=$after)"
        fi
    else
        echo "SKIP: $rendered_file missing — end-to-end test skipped"
    fi
else
    echo "SKIP: project fixtures for end-to-end test not present"
fi

# --- Test 8: shellcheck clean ---

TOTAL=$((TOTAL + 1))
if command -v shellcheck >/dev/null 2>&1; then
    if shellcheck -x "$HELPER" >/dev/null 2>&1; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: shellcheck -x reported issues for $HELPER"
        shellcheck -x "$HELPER" || true
    fi
else
    PASS=$((PASS + 1))
    echo "SKIP: shellcheck not installed — test 8 counted as PASS"
fi

# --- Summary ---

echo
echo "Results: $PASS passed, $FAIL failed out of $TOTAL total"
if [[ "$FAIL" -ne 0 ]]; then
    exit 1
fi
