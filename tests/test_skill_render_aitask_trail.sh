#!/usr/bin/env bash
# test_skill_render_aitask_trail.sh - Regression tests for t1210_3:
#   - .claude/skills/aitask-trail/SKILL.md.j2 (entry-point template)
#   - 3 per-agent stubs (claude/codex/opencode)
#   - 3 entry-point goldens under tests/golden/skills/aitask-trail/
# Coverage:
#   1.  Per-profile golden diff for the entry-point template (claude render).
#   1b. Agent-dimension invariance (no {% if agent %} in the template).
#   2.  Profile-conditional sanity: the headless guard renders for remote
#       only (the sole profile conditional in the template).
#   3.  No Jinja markers leak into any render.
#   4.  Cross-agent reference rewrite for the task-workflow full-path ref.
#   5.  Stub markers present on all 3 stub files.
# Run: bash tests/test_skill_render_aitask_trail.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

# Shared core helpers (assert_eq, assert_contains, …) live in tests/lib/asserts.sh.
. "$PROJECT_DIR/tests/lib/asserts.sh"

cd "$PROJECT_DIR"

# shellcheck source=.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"
PYTHON="$(require_ait_python)"
if ! "$PYTHON" -c 'import minijinja' 2>/dev/null; then
    echo "SKIP: minijinja not installed in framework venv ($PYTHON). Run 'ait setup' first."
    exit 0
fi

RENDER="$PYTHON $PROJECT_DIR/.aitask-scripts/lib/skill_template.py"
TEMPLATE=".claude/skills/aitask-trail/SKILL.md.j2"
SKILL_GOLDEN_DIR="tests/golden/skills/aitask-trail"
PROFILES_DIR="aitasks/metadata/profiles"

PROFILES=(default fast remote)
AGENTS=(claude codex opencode)

# === Test 1: per-profile entry-point golden diffs (claude render is canonical) ===

echo "=== Test 1: golden diffs for entry-point × 3 profiles ==="
for profile in "${PROFILES[@]}"; do
    rendered="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    golden_content="$(cat "$SKILL_GOLDEN_DIR/SKILL-${profile}-claude.md")"
    assert_eq "golden SKILL × $profile" "$golden_content" "$rendered"
done

# === Test 1b: entry-point agent dimension invariance ===
#
# The template has no {% if agent %} gate, so the basic stdout render is
# byte-identical across agents. Fails LOUDLY if agent gating is ever added.
echo "=== Test 1b: agent renders are byte-identical (no {% if agent %} in template) ==="
for profile in "${PROFILES[@]}"; do
    base="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    for agent in codex opencode; do
        cmp="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" "$agent" 2>&1)"
        assert_eq "agent invariance $profile/$agent" "$base" "$cmp"
    done
done

# === Test 2: profile-conditional sanity (headless guard) ===
#
# remote.yaml is the only committed profile with headless: true, so the
# headless guard paragraph must render for remote and be absent otherwise.

echo "=== Test 2: headless guard fires for remote only ==="
for profile in "${PROFILES[@]}"; do
    skill="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    if [[ "$profile" == "remote" ]]; then
        assert_contains "$profile: headless guard present" \
            "Headless profile guard" "$skill"
        assert_contains "$profile: headless write refusal" \
            "Never write the artifact headless" "$skill"
    else
        assert_not_contains "$profile: no headless guard" \
            "Headless profile guard" "$skill"
    fi
done

# === Test 3: no Jinja markers leak ===

echo "=== Test 3: rendered output has no Jinja markers ==="
for profile in "${PROFILES[@]}"; do
    for agent in "${AGENTS[@]}"; do
        rendered="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" "$agent" 2>&1)"
        assert_not_contains "no Jinja {% leak SKILL × $profile × $agent" "{%" "$rendered"
        assert_not_contains "no Jinja {{ leak SKILL × $profile × $agent" "{{" "$rendered"
    done
done

# === Test 4: cross-agent reference rewrites (via walk-write on-disk output) ===

echo "=== Test 4: per-agent reference rewrites via walk-write ==="
for agent in "${AGENTS[@]}"; do
    ./.aitask-scripts/aitask_skill_render.sh aitask-trail --profile fast --agent "$agent" --force >/dev/null 2>&1
done

assert_contains "claude/fast: task-workflow ref rewritten under .claude/skills" \
    ".claude/skills/task-workflow-fast-/model-self-detection.md" \
    "$(cat .claude/skills/aitask-trail-fast-/SKILL.md)"
assert_contains "codex/fast: task-workflow ref rewritten under .agents/skills" \
    ".agents/skills/task-workflow-fast-codex-/model-self-detection.md" \
    "$(cat .agents/skills/aitask-trail-fast-codex-/SKILL.md)"
assert_contains "opencode/fast: task-workflow ref rewritten under .opencode/skills" \
    ".opencode/skills/task-workflow-fast-/model-self-detection.md" \
    "$(cat .opencode/skills/aitask-trail-fast-/SKILL.md)"

# === Test 5: stub-marker checks ===

echo "=== Test 5: 3 stub files contain canonical markers ==="
CLAUDE_STUB=".claude/skills/aitask-trail/SKILL.md"
CODEX_STUB=".agents/skills/aitask-trail/SKILL.md"
OPENCODE_STUB=".opencode/commands/aitask-trail.md"

for stub in "$CLAUDE_STUB" "$CODEX_STUB" "$OPENCODE_STUB"; do
    body="$(cat "$stub")"
    assert_contains "$stub: resolve_profile uses short name 'trail'" \
        "aitask_skill_resolve_profile.sh trail" "$body"
    assert_not_contains "$stub: resolve_profile does NOT use full slug 'aitask-trail'" \
        "aitask_skill_resolve_profile.sh aitask-trail" "$body"
    assert_contains "$stub: skill render invocation present" \
        "aitask_skill_render.sh aitask-trail" "$body"
    assert_contains "$stub: Read-and-follow marker present" \
        "Dispatch via Read-and-follow" "$body"
done

# Per-agent agent_literal substitution checks
assert_contains "claude stub: --agent claude" "--agent claude" "$(cat "$CLAUDE_STUB")"
assert_contains "codex stub: --agent codex" "--agent codex" "$(cat "$CODEX_STUB")"
assert_contains "opencode stub: --agent opencode" "--agent opencode" "$(cat "$OPENCODE_STUB")"

# Per-agent rendered-variant Read target checks
assert_contains "claude stub: reads from .claude/skills/aitask-trail-<profile>-" \
    ".claude/skills/aitask-trail-<profile>-/SKILL.md" "$(cat "$CLAUDE_STUB")"
assert_contains "codex stub: reads from .agents/skills/aitask-trail-<profile>-codex-" \
    ".agents/skills/aitask-trail-<profile>-codex-/SKILL.md" "$(cat "$CODEX_STUB")"
assert_contains "opencode stub: reads from .opencode/skills/aitask-trail-<profile>-" \
    ".opencode/skills/aitask-trail-<profile>-/SKILL.md" "$(cat "$OPENCODE_STUB")"

# === Summary ===

echo ""
echo "Tests: $TOTAL, Passed: $PASS, Failed: $FAIL"
[[ "$FAIL" -eq 0 ]] || exit 1
