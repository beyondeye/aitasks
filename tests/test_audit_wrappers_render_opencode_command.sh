#!/usr/bin/env bash
# test_audit_wrappers_render_opencode_command.sh - t1831.
# Run: bash tests/test_audit_wrappers_render_opencode_command.sh
#
# Pins `aitask_audit_wrappers.sh render-wrapper opencode-command` to the two
# shapes it must emit:
#   Test 1 - a TEMPLATED skill (has SKILL.md.j2) renders the profile-aware stub,
#            byte-identical to the committed .opencode/commands/<skill>.md.
#   Test 2 - every templated skill's rendered BODY equals the committed command's
#            body, renders with `--agent opencode`, and never @-includes the
#            Claude stub (the t1831 defect: the legacy form pulled in the Claude
#            stub, which renders `--agent claude` and dispatches to the wrong
#            agent's variant).
#   Test 3 - negative control: a NON-templated skill still renders the legacy
#            @-include form, so the branch keys on templating, not on everything.
#   Test 4 - the legacy form fails aitask_skill_verify.sh's opencode-cmd
#            stub-surface markers, and the new form passes them. This is the
#            "would verify have caught it?" question the task asked, answered
#            against the verifier's own three greps.
#
# Read-only against the real repo: renders to stdout, compares with committed
# files, writes nothing.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

AUDIT="$PROJECT_DIR/.aitask-scripts/aitask_audit_wrappers.sh"

# The audit script resolves its own repo root from the cwd, and this file starts
# in an empty non-repo scratch dir (scratch_cwd.sh), so every call runs from the
# project dir inside a subshell `&&` chain (the cd_guard_lint-sanctioned form).
audit() {
    (cd "$PROJECT_DIR" && "$AUDIT" "$@")
}

# Everything after the closing `---` of the frontmatter. The committed commands
# carry only `description:`, and three of them (pick / pickrem / pickweb) have a
# pre-existing description difference from the source SKILL.md stub, so the
# whole-set check below compares bodies while Test 1 pins two files exactly.
body_of() {
    sed '1,/^---$/d' "$1" | sed '1,/^---$/d'
}

echo "=== Test 1: a templated skill renders the committed profile-aware stub ==="

for skill in aitask-shadow aitask-brainstorm-discuss; do
    rendered="$(audit render-wrapper opencode-command "$skill")"
    assert_eq "Test 1: $skill render is byte-identical to the committed command" \
        "$(cat "$PROJECT_DIR/.opencode/commands/$skill.md")" "$rendered"
done

echo ""
echo "=== Test 2: every templated skill renders an OpenCode-dispatching body ==="

templated=()
for tpl in "$PROJECT_DIR"/.claude/skills/*/SKILL.md.j2; do
    [[ -f "$tpl" ]] || continue
    templated+=("$(basename "$(dirname "$tpl")")")
done

assert_exit_zero "Test 2: the repo has templated skills to check" \
    test "${#templated[@]}" -gt 0

for skill in "${templated[@]}"; do
    committed="$PROJECT_DIR/.opencode/commands/$skill.md"
    assert_file_exists "Test 2: $skill has a committed OpenCode command" "$committed"
    [[ -f "$committed" ]] || continue

    rendered_file="$(mktemp)"
    audit render-wrapper opencode-command "$skill" > "$rendered_file"

    assert_eq "Test 2: $skill rendered body matches the committed command body" \
        "$(body_of "$committed")" "$(body_of "$rendered_file")"

    rendered="$(cat "$rendered_file")"
    assert_contains "Test 2: $skill renders for the opencode agent" \
        "aitask_skill_render.sh $skill --profile <profile> --agent opencode" "$rendered"
    assert_not_contains "Test 2: $skill does not @-include the Claude stub" \
        "@.claude/skills/" "$rendered"

    rm -f "$rendered_file"
done

echo ""
echo "=== Test 3: negative control - a non-templated skill keeps the legacy form ==="

# aitask-create ships no SKILL.md.j2, so it must still get the static wrapper.
assert_file_not_exists "Test 3: aitask-create is genuinely non-templated" \
    "$PROJECT_DIR/.claude/skills/aitask-create/SKILL.md.j2"

legacy="$(audit render-wrapper opencode-command aitask-create)"
assert_contains "Test 3: non-templated skill @-includes the Claude SKILL.md" \
    "@.claude/skills/aitask-create/SKILL.md" "$legacy"
assert_not_contains "Test 3: non-templated skill gets no resolver call" \
    "aitask_skill_resolve_profile.sh" "$legacy"

echo ""
echo "=== Test 4: the legacy form fails the verifier's opencode-cmd markers ==="

# The three greps aitask_skill_verify.sh applies to the .opencode/commands/<skill>.md
# surface (see its stub-pattern check). Restated here as the contract a generated
# command for a TEMPLATED skill must satisfy.
verify_markers_missing() {
    local text="$1" skill="$2" key="${2#aitask-}" missing=0
    printf '%s' "$text" | grep -q "aitask_skill_resolve_profile\.sh ${key}" || missing=$((missing + 1))
    printf '%s' "$text" | grep -q "aitask_skill_render.sh ${skill}" || missing=$((missing + 1))
    printf '%s' "$text" | grep -qF -- ".opencode/skills/${skill}-<profile>-/SKILL.md" || missing=$((missing + 1))
    printf '%s\n' "$missing"
}

# The legacy text as it would be rendered for a templated skill: the same static
# body, with aitask-shadow substituted in. Built here rather than by reverting the
# fix, so the control needs no working-tree mutation.
legacy_for_templated="---
description: irrelevant
---

@.opencode/skills/opencode_tool_mapping.md

Execute the following Claude Code skill. Follow each step precisely, translating tool references per the mapping above.

Arguments: \$ARGUMENTS

@.claude/skills/aitask-shadow/SKILL.md"

assert_eq "Test 4: the legacy form misses all three verifier markers" \
    "3" "$(verify_markers_missing "$legacy_for_templated" aitask-shadow)"

assert_eq "Test 4: the rendered form misses none of them" \
    "0" "$(verify_markers_missing "$(audit render-wrapper opencode-command aitask-shadow)" aitask-shadow)"

# ============================================================
# Summary
# ============================================================
echo ""
echo "=============================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=============================="

if [[ "$FAIL" -gt 0 ]]; then
    exit 1
fi
