#!/usr/bin/env bash
# test_skill_render_aitask_revert.sh - Regression tests for t777_13:
#   - .claude/skills/aitask-revert/SKILL.md.j2 (entry-point template)
#   - 4 per-agent stubs (claude/codex/gemini/opencode)
#   - 3 golden files under tests/golden/skills/aitask-revert/ (3 profiles, claude canonical)
# Coverage:
#   1.  Per-profile golden diff for the entry-point template (claude render).
#   1b. Agent-dimension invariance: codex/gemini/opencode renders are
#       byte-identical to the claude render (no {% if agent %} in the
#       template). Per-agent reference rewrites are a walk-write property
#       covered by Test 4, not the basic stdout render.
#   2. Profile-conditional sanity: all live profiles have explore_auto_continue
#      false or undefined, so the AskUserQuestion branch must fire and the
#      auto-continue branch must NOT fire under any of them.
#   3. No Jinja markers leak into any rendered entry-point.
#   3b. Rendered body must NOT re-resolve profile (t777_26 forbidden tokens).
#   4. Per-agent reference rewrites: aitask-revert references BOTH the
#      task-workflow and user-file-select closures — both must be rewritten
#      to the per-agent rendered-variant path.
#   5. Stub markers present on all 4 stub files (canonical body fingerprint
#      from aidocs/stub-skill-pattern.md §3b/§3c/§3d).
# Run: bash tests/test_skill_render_aitask_revert.sh

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
TEMPLATE=".claude/skills/aitask-revert/SKILL.md.j2"
GOLDEN_DIR="tests/golden/skills/aitask-revert"
PROFILES_DIR="aitasks/metadata/profiles"

PROFILES=(default fast remote)
AGENTS=(claude codex gemini opencode)

# === Test 1: per-profile golden diffs (claude render is canonical) ===

echo "=== Test 1: golden diffs for entry-point × 3 profiles ==="
for profile in "${PROFILES[@]}"; do
    rendered="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    golden_content="$(cat "$GOLDEN_DIR/SKILL-${profile}-claude.md")"
    assert_eq "golden SKILL × $profile" "$golden_content" "$rendered"
done

# === Test 1b: agent dimension invariance ===
#
# The entry-point template has no {% if agent %} gate, so the basic
# stdout render is byte-identical across all 4 agents. This single
# assertion replaces per-agent goldens; if a future template introduces
# agent gating it fails LOUDLY — re-add per-agent goldens for that skill
# then (see aidocs/stub-skill-pattern.md).
echo "=== Test 1b: agent renders are byte-identical (no {% if agent %} in template) ==="
for profile in "${PROFILES[@]}"; do
    base="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    for agent in codex gemini opencode; do
        cmp="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" "$agent" 2>&1)"
        assert_eq "agent invariance $profile/$agent" "$base" "$cmp"
    done
done

# === Test 2: profile-conditional sanity ===
#
# None of the committed profiles set explore_auto_continue=true, so for all
# three profiles the AskUserQuestion (else) branch must fire and the
# auto-continue (if) branch must NOT fire. This exercises the {% else %} arm
# and the `is defined and` guard for the absent-key case (default/remote).
# The {% if %} arm is exercised structurally by `./ait skill verify` rendering
# the template without error.

echo "=== Test 2: profile branches fire correctly ==="
for profile in "${PROFILES[@]}"; do
    rendered="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    assert_contains "$profile/claude: AskUserQuestion branch fires" \
        'Revert task created successfully. How would you like to proceed?' "$rendered"
    assert_not_contains "$profile/claude: no auto-continue branch" \
        "': continuing to implementation" "$rendered"
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
# aitask-revert references TWO sibling closures — task-workflow (Step 4/5/6)
# and user-file-select (Step 1 Path B). The dep-walker must rewrite both to
# the per-agent rendered-variant path.

echo "=== Test 4: per-agent reference rewrites via walk-write ==="
for agent in "${AGENTS[@]}"; do
    ./.aitask-scripts/aitask_skill_render.sh aitask-revert --profile fast --agent "$agent" --force >/dev/null 2>&1
done

assert_contains "claude/fast: task-workflow ref rewritten under .claude/skills" \
    ".claude/skills/task-workflow-fast-/SKILL.md" "$(cat .claude/skills/aitask-revert-fast-/SKILL.md)"
assert_contains "codex/fast: task-workflow ref rewritten under .agents/skills" \
    ".agents/skills/task-workflow-fast-codex-/SKILL.md" "$(cat .agents/skills/aitask-revert-fast-codex-/SKILL.md)"
assert_contains "gemini/fast: task-workflow ref rewritten under .gemini/skills" \
    ".gemini/skills/task-workflow-fast-/SKILL.md" "$(cat .gemini/skills/aitask-revert-fast-/SKILL.md)"
assert_contains "opencode/fast: task-workflow ref rewritten under .opencode/skills" \
    ".opencode/skills/task-workflow-fast-/SKILL.md" "$(cat .opencode/skills/aitask-revert-fast-/SKILL.md)"

assert_contains "claude/fast: user-file-select ref rewritten under .claude/skills" \
    ".claude/skills/user-file-select-fast-/SKILL.md" "$(cat .claude/skills/aitask-revert-fast-/SKILL.md)"
assert_contains "codex/fast: user-file-select ref rewritten under .agents/skills" \
    ".agents/skills/user-file-select-fast-codex-/SKILL.md" "$(cat .agents/skills/aitask-revert-fast-codex-/SKILL.md)"
assert_contains "gemini/fast: user-file-select ref rewritten under .gemini/skills" \
    ".gemini/skills/user-file-select-fast-/SKILL.md" "$(cat .gemini/skills/aitask-revert-fast-/SKILL.md)"
assert_contains "opencode/fast: user-file-select ref rewritten under .opencode/skills" \
    ".opencode/skills/user-file-select-fast-/SKILL.md" "$(cat .opencode/skills/aitask-revert-fast-/SKILL.md)"

# === Test 5: stub-marker checks ===

echo "=== Test 5: 4 stub files contain canonical markers ==="
CLAUDE_STUB=".claude/skills/aitask-revert/SKILL.md"
CODEX_STUB=".agents/skills/aitask-revert/SKILL.md"
GEMINI_STUB=".gemini/commands/aitask-revert.toml"
OPENCODE_STUB=".opencode/commands/aitask-revert.md"

for stub in "$CLAUDE_STUB" "$CODEX_STUB" "$GEMINI_STUB" "$OPENCODE_STUB"; do
    body="$(cat "$stub")"
    assert_contains "$stub: resolve_profile uses short name 'revert' (t777_26)" \
        "aitask_skill_resolve_profile.sh revert" "$body"
    assert_not_contains "$stub: resolve_profile does NOT use full slug 'aitask-revert'" \
        "aitask_skill_resolve_profile.sh aitask-revert" "$body"
    assert_contains "$stub: skill render invocation present" \
        "aitask_skill_render.sh aitask-revert" "$body"
    assert_contains "$stub: Read-and-follow marker present" \
        "Dispatch via Read-and-follow" "$body"
done

# Per-agent agent_literal substitution checks
assert_contains "claude stub: --agent claude" "--agent claude" "$(cat "$CLAUDE_STUB")"
assert_contains "codex stub: --agent codex" "--agent codex" "$(cat "$CODEX_STUB")"
assert_contains "gemini stub: --agent gemini" "--agent gemini" "$(cat "$GEMINI_STUB")"
assert_contains "opencode stub: --agent opencode" "--agent opencode" "$(cat "$OPENCODE_STUB")"

# Per-agent rendered-variant Read target checks
assert_contains "claude stub: reads from .claude/skills/aitask-revert-<profile>-" \
    ".claude/skills/aitask-revert-<profile>-/SKILL.md" "$(cat "$CLAUDE_STUB")"
assert_contains "codex stub: reads from .agents/skills/aitask-revert-<profile>-" \
    ".agents/skills/aitask-revert-<profile>-codex-/SKILL.md" "$(cat "$CODEX_STUB")"
assert_contains "gemini stub: reads from .gemini/skills/aitask-revert-<profile>-" \
    ".gemini/skills/aitask-revert-<profile>-/SKILL.md" "$(cat "$GEMINI_STUB")"
assert_contains "opencode stub: reads from .opencode/skills/aitask-revert-<profile>-" \
    ".opencode/skills/aitask-revert-<profile>-/SKILL.md" "$(cat "$OPENCODE_STUB")"

# === Summary ===

echo ""
echo "Tests: $TOTAL, Passed: $PASS, Failed: $FAIL"
[[ "$FAIL" -eq 0 ]] || exit 1
