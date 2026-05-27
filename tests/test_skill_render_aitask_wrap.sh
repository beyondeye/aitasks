#!/usr/bin/env bash
# test_skill_render_aitask_wrap.sh - Regression tests for t803:
#   - .claude/skills/aitask-wrap/SKILL.md.j2 (entry-point template)
#   - 3 per-agent stubs (claude/codex/opencode)
#   - 6 golden files under tests/golden/skills/aitask-wrap/
#     (3 profiles × {claude, codex}; codex stands in for non-claude)
# Coverage:
#   1.  Per-(profile, agent) golden diff — 3 profiles × {claude, codex}.
#       aitask-wrap is the first templated skill with an {% if agent %}
#       gate (Step 1b: Check for Recent Claude Plans), so claude and
#       non-claude renders diverge. Goldens are committed for both.
#   1b. Agent gating sanity:
#       - Claude render of each profile MUST contain the gated Step 1b
#         heading and the ~/.claude/plans path.
#       - codex/opencode renders MUST NOT contain either.
#       - codex/opencode renders of the same profile MUST be
#         byte-identical to each other (no other agent-conditional content).
#   3.  No Jinja markers leak into any rendered entry-point.
#   3b. Rendered body must NOT re-resolve profile (t777_26 forbidden tokens).
#   4.  Per-agent reference rewrites via walk-write (task-workflow refs).
#   5.  Stub markers present on all 3 stub files (canonical body fingerprint
#       from aidocs/stub-skill-pattern.md §3b/§3c/§3d).
# Run: bash tests/test_skill_render_aitask_wrap.sh

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
        echo "FAIL: $desc"
        diff <(echo "$expected") <(echo "$actual") | head -20
    fi
}

assert_contains() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qF -- "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output containing: '$expected')"
    fi
}

assert_not_contains() {
    local desc="$1" forbidden="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qF -- "$forbidden"; then
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
TEMPLATE=".claude/skills/aitask-wrap/SKILL.md.j2"
GOLDEN_DIR="tests/golden/skills/aitask-wrap"
PROFILES_DIR="aitasks/metadata/profiles"

PROFILES=(default fast remote)
AGENTS=(claude codex opencode)
GOLDEN_AGENTS=(claude codex)

# === Test 1: per-(profile, agent) golden diffs ===
#
# aitask-wrap has an {% if agent == "claude" %} gate around Step 1b, so the
# claude render and the non-claude render differ. Both are committed as
# goldens. codex stands in for the non-claude render (verified by Test 1b

echo "=== Test 1: golden diffs for entry-point × 3 profiles × {claude, codex} ==="
for profile in "${PROFILES[@]}"; do
    for agent in "${GOLDEN_AGENTS[@]}"; do
        rendered="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" "$agent" 2>&1)"
        golden_content="$(cat "$GOLDEN_DIR/SKILL-${profile}-${agent}.md")"
        assert_eq "golden SKILL × $profile × $agent" "$golden_content" "$rendered"
    done
done

# === Test 1b: agent gating sanity ===
#
# The template uses {% if agent == "claude" %} to gate Step 1b. Verify:
#   - claude render contains the gated content
#   - codex/opencode renders do NOT contain the gated content
#   - codex/opencode renders are byte-identical to each other
#     (no other agent-conditional content lives in the template)
echo "=== Test 1b: agent gate fires correctly for Step 1b ==="
for profile in "${PROFILES[@]}"; do
    claude_out="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    assert_contains "$profile/claude: Step 1b heading present" \
        "Step 1b: Check for Recent Claude Plans" "$claude_out"
    assert_contains "$profile/claude: ~/.claude/plans path present" \
        '~/.claude/plans' "$claude_out"

    codex_out="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" codex 2>&1)"
    assert_not_contains "$profile/codex: no Step 1b heading" \
        "Step 1b: Check for Recent Claude Plans" "$codex_out"
    assert_not_contains "$profile/codex: no ~/.claude/plans path" \
        '~/.claude/plans' "$codex_out"

    # codex/opencode must be byte-identical to each other (no other
    # agent-conditional content in the template).
    for other in opencode; do
        other_out="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" "$other" 2>&1)"
        assert_eq "non-claude invariance $profile codex==$other" "$codex_out" "$other_out"
    done
done

# === Test 3: no Jinja markers leak ===

echo "=== Test 3: rendered output has no Jinja markers ==="
for profile in "${PROFILES[@]}"; do
    for agent in "${AGENTS[@]}"; do
        rendered="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" "$agent" 2>&1)"
        assert_not_contains "no Jinja {% leak $profile × $agent" "{%" "$rendered"
        assert_not_contains "no Jinja {{ leak $profile × $agent" "{{" "$rendered"
    done
done

# === Test 3b: rendered body must NOT re-resolve profile at runtime (t777_26) ===

echo "=== Test 3b: rendered body has no runtime profile-resolution tokens ==="
FORBIDDEN_TOKENS=(
    "aitask_scan_profiles.sh"
    "Execute the Execution Profile Selection Procedure"
    "Select Execution Profile"
    "refresh execution profile"
)
for profile in "${PROFILES[@]}"; do
    for agent in "${AGENTS[@]}"; do
        rendered="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" "$agent" 2>&1)"
        for token in "${FORBIDDEN_TOKENS[@]}"; do
            assert_not_contains "rendered $profile × $agent has no '$token'" \
                "$token" "$rendered"
        done
    done
done

# === Test 4: cross-agent reference rewrites (via walk-write on-disk output) ===
#
# aitask-wrap references task-workflow procedures (task-creation-batch.md,
# agent-attribution.md, code-agent-commit-attribution.md, issue-update.md,
# satisfaction-feedback.md) in full-path form. The walker must rewrite each
# to the per-agent, per-profile target tree.

echo "=== Test 4: per-agent reference rewrites via walk-write ==="
for agent in "${AGENTS[@]}"; do
    ./.aitask-scripts/aitask_skill_render.sh aitask-wrap --profile fast --agent "$agent" --force >/dev/null 2>&1
done

assert_contains "claude/fast: task-workflow ref rewritten under .claude/skills" \
    ".claude/skills/task-workflow-fast-/" "$(cat .claude/skills/aitask-wrap-fast-/SKILL.md)"
assert_contains "codex/fast: task-workflow ref rewritten under .agents/skills" \
    ".agents/skills/task-workflow-fast-codex-/" "$(cat .agents/skills/aitask-wrap-fast-codex-/SKILL.md)"
assert_contains "opencode/fast: task-workflow ref rewritten under .opencode/skills" \
    ".opencode/skills/task-workflow-fast-/" "$(cat .opencode/skills/aitask-wrap-fast-/SKILL.md)"

# === Test 5: stub-marker checks ===

echo "=== Test 5: 3 stub files contain canonical markers ==="
CLAUDE_STUB=".claude/skills/aitask-wrap/SKILL.md"
CODEX_STUB=".agents/skills/aitask-wrap/SKILL.md"
OPENCODE_STUB=".opencode/commands/aitask-wrap.md"

for stub in "$CLAUDE_STUB" "$CODEX_STUB" "$OPENCODE_STUB"; do
    body="$(cat "$stub")"
    assert_contains "$stub: resolve_profile uses short name 'wrap' (t777_26)" \
        "aitask_skill_resolve_profile.sh wrap" "$body"
    assert_not_contains "$stub: resolve_profile does NOT use full slug 'aitask-wrap'" \
        "aitask_skill_resolve_profile.sh aitask-wrap" "$body"
    assert_contains "$stub: skill render invocation present" \
        "aitask_skill_render.sh aitask-wrap" "$body"
    assert_contains "$stub: Read-and-follow marker present" \
        "Dispatch via Read-and-follow" "$body"
done

# Per-agent agent_literal substitution checks
assert_contains "claude stub: --agent claude" "--agent claude" "$(cat "$CLAUDE_STUB")"
assert_contains "codex stub: --agent codex" "--agent codex" "$(cat "$CODEX_STUB")"
assert_contains "opencode stub: --agent opencode" "--agent opencode" "$(cat "$OPENCODE_STUB")"

# Per-agent rendered-variant Read target checks
assert_contains "claude stub: reads from .claude/skills/aitask-wrap-<profile>-" \
    ".claude/skills/aitask-wrap-<profile>-/SKILL.md" "$(cat "$CLAUDE_STUB")"
assert_contains "codex stub: reads from .agents/skills/aitask-wrap-<profile>-" \
    ".agents/skills/aitask-wrap-<profile>-codex-/SKILL.md" "$(cat "$CODEX_STUB")"
assert_contains "opencode stub: reads from .opencode/skills/aitask-wrap-<profile>-" \
    ".opencode/skills/aitask-wrap-<profile>-/SKILL.md" "$(cat "$OPENCODE_STUB")"

# === Summary ===

echo ""
echo "Tests: $TOTAL, Passed: $PASS, Failed: $FAIL"
[[ "$FAIL" -eq 0 ]] || exit 1
