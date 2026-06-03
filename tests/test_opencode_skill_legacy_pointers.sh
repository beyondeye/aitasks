#!/usr/bin/env bash
# test_opencode_skill_legacy_pointers.sh — Regression for t777_29.
#
# Every templated skill (one with .claude/skills/<skill>/SKILL.md.j2) must
# have a §3d-style stub at .opencode/skills/<skill>/SKILL.md. The pre-
# templating-era "Source of Truth" pointer that routed OpenCode through
# the Claude agent root is the bug this test guards against.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

# Shared core helpers (assert_eq, assert_contains, …) live in tests/lib/asserts.sh.
. "$PROJECT_DIR/tests/lib/asserts.sh"

cd "$PROJECT_DIR"

mapfile -t templates < <(
    find .claude/skills -mindepth 2 -maxdepth 3 -name 'SKILL.md.j2' -type f 2>/dev/null | sort
)

if [[ ${#templates[@]} -eq 0 ]]; then
    echo "SKIP: no .j2 templates found — nothing to check."
    exit 0
fi

for tpl in "${templates[@]}"; do
    skill="$(basename "$(dirname "$tpl")")"
    stub=".opencode/skills/${skill}/SKILL.md"
    short="${skill#aitask-}"

    TOTAL=$((TOTAL + 1))
    if [[ -f "$stub" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $skill: missing OpenCode skill stub at $stub"
        continue
    fi

    body="$(cat "$stub")"
    assert_not_contains "$skill: stub has no legacy 'Source of Truth' phrase" \
        "Source of Truth" "$body"
    assert_not_contains "$skill: stub does not redirect to .claude/skills/${skill}/SKILL.md" \
        ".claude/skills/${skill}/SKILL.md" "$body"
    assert_contains "$skill: stub uses short-name resolver call" \
        "aitask_skill_resolve_profile.sh ${short}" "$body"
    assert_not_contains "$skill: stub does NOT use full slug in resolver call" \
        "aitask_skill_resolve_profile.sh aitask-${short}" "$body"
    assert_contains "$skill: stub invokes renderer with full slug" \
        "aitask_skill_render.sh ${skill}" "$body"
    assert_contains "$skill: stub hardcodes --agent opencode" \
        "--agent opencode" "$body"
    assert_contains "$skill: stub reads from .opencode/skills/${skill}-<profile>-" \
        ".opencode/skills/${skill}-<profile>-/SKILL.md" "$body"
    assert_contains "$skill: stub has Read-and-follow marker" \
        "Dispatch via Read-and-follow" "$body"
done

echo ""
echo "Tests: $TOTAL, Passed: $PASS, Failed: $FAIL"
[[ "$FAIL" -eq 0 ]] || exit 1
