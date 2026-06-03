#!/usr/bin/env bash
# Regression tests for the experimental aitask-pickn staging skill.
# Run: bash tests/test_skill_render_aitask_pickn.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

assert_contains() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if grep -qF -- "$expected" <<<"$actual"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output containing: '$expected')"
    fi
}

assert_not_contains() {
    local desc="$1" forbidden="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if grep -qF -- "$forbidden" <<<"$actual"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (forbidden token '$forbidden' present)"
    else
        PASS=$((PASS + 1))
    fi
}

cd "$PROJECT_DIR"

# shellcheck source=.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"
PYTHON="$(require_ait_python)"
if ! "$PYTHON" -c 'import minijinja' 2>/dev/null; then
    echo "SKIP: minijinja not installed in framework venv ($PYTHON). Run 'ait setup' first."
    exit 0
fi

RENDER="$PYTHON $PROJECT_DIR/.aitask-scripts/lib/skill_template.py"
TEMPLATE=".claude/skills/aitask-pickn/SKILL.md.j2"
PROFILES_DIR="aitasks/metadata/profiles"

echo "=== Test 1: fast render dispatches into task-workflown ==="
FAST="$($RENDER "$TEMPLATE" "$PROFILES_DIR/fast.yaml" claude 2>&1)"
assert_contains "fast render names pickn variant" "name: aitask-pickn-fast" "$FAST"
assert_contains "fast render points to task-workflown" ".claude/skills/task-workflown/SKILL.md" "$FAST"
assert_contains "fast render uses pickn feedback key" '- **skill_name**: `"pickn"`' "$FAST"
assert_contains "fast render marks experimental staging" "Experimental staging skill" "$FAST"
assert_not_contains "fast render does not point to production workflow" ".claude/skills/task-workflow/SKILL.md" "$FAST"
assert_not_contains "fast render does not use production feedback key" '- **skill_name**: `"pick"`' "$FAST"

echo "=== Test 2: no Jinja markers leak ==="
for profile in default fast remote; do
    rendered="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    assert_not_contains "$profile: no Jinja {% leak" "{%" "$rendered"
    assert_not_contains "$profile: no Jinja {{ leak" "{{" "$rendered"
done

echo "=== Test 3: stubs dispatch to pickn rendered variants ==="
CLAUDE_STUB="$(cat .claude/skills/aitask-pickn/SKILL.md)"
CODEX_STUB="$(cat .agents/skills/aitask-pickn/SKILL.md)"
OPENCODE_COMMAND="$(cat .opencode/commands/aitask-pickn.md)"
OPENCODE_SKILL="$(cat .opencode/skills/aitask-pickn/SKILL.md)"

for body in "$CLAUDE_STUB" "$CODEX_STUB" "$OPENCODE_COMMAND" "$OPENCODE_SKILL"; do
    assert_contains "stub resolves pickn profile key" "aitask_skill_resolve_profile.sh pickn" "$body"
    assert_contains "stub renders aitask-pickn" "aitask_skill_render.sh aitask-pickn" "$body"
    assert_contains "stub documents experimental staging" "Experimental staging skill" "$body"
    assert_not_contains "stub does not resolve production pick key" "aitask_skill_resolve_profile.sh pick\`" "$body"
    assert_not_contains "stub does not render production pick" "aitask_skill_render.sh aitask-pick --profile" "$body"
done

assert_contains "claude stub reads pickn rendered dir" ".claude/skills/aitask-pickn-<profile>-/SKILL.md" "$CLAUDE_STUB"
assert_contains "codex stub reads pickn rendered dir" ".agents/skills/aitask-pickn-<profile>-codex-/SKILL.md" "$CODEX_STUB"
assert_contains "opencode command reads pickn rendered dir" ".opencode/skills/aitask-pickn-<profile>-/SKILL.md" "$OPENCODE_COMMAND"
assert_contains "opencode skill reads pickn rendered dir" ".opencode/skills/aitask-pickn-<profile>-/SKILL.md" "$OPENCODE_SKILL"

echo "=== Test 4: project default profile includes pickn ==="
assert_contains "project config defaults pickn to fast" "  pickn: fast" "$(cat aitasks/metadata/project_config.yaml)"

echo ""
echo "Tests: $TOTAL, Passed: $PASS, Failed: $FAIL"
[[ "$FAIL" -eq 0 ]] || exit 1
