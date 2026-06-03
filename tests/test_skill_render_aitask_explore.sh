#!/usr/bin/env bash
# test_skill_render_aitask_explore.sh - Regression tests for t777_8:
#   - .claude/skills/aitask-explore/SKILL.md.j2 (entry-point template)
#   - 3 per-agent stubs (claude/codex/opencode)
#   - 3 golden files under tests/golden/skills/aitask-explore/ (3 profiles, claude canonical)
# Coverage:
#   1.  Per-profile golden diff for the entry-point template (claude render).
#   1b. Agent-dimension invariance: codex/opencode renders are
#       byte-identical to the claude render (no {% if agent %} in the
#       template). Per-agent reference rewrites are a walk-write property
#       covered by Test 4, not the basic stdout render.
#   2. Profile-conditional sanity: all live profiles have explore_auto_continue
#      false or undefined, so the AskUserQuestion branch must fire and the
#      auto-continue branch must NOT fire under any of them.
#   3. No Jinja markers leak into any rendered entry-point.
#   3b. Rendered body must NOT re-resolve profile (t777_26 forbidden tokens).
#   4. Stub markers present on all 3 stub files (canonical body fingerprint
#      from aidocs/framework/stub-skill-pattern.md §3b/§3c/§3d).
# Run: bash tests/test_skill_render_aitask_explore.sh

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
TEMPLATE=".claude/skills/aitask-explore/SKILL.md.j2"
GOLDEN_DIR="tests/golden/skills/aitask-explore"
PROFILES_DIR="aitasks/metadata/profiles"

PROFILES=(default fast remote)
AGENTS=(claude codex opencode)

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
# assertion replaces the 9 deleted per-agent goldens; if a future
# template introduces agent gating it fails LOUDLY — re-add per-agent
# goldens for that skill then (see aidocs/framework/stub-skill-pattern.md).
echo "=== Test 1b: agent renders are byte-identical (no {% if agent %} in template) ==="
for profile in "${PROFILES[@]}"; do
    base="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    for agent in codex opencode; do
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
        'Task created successfully. How would you like to proceed?' "$rendered"
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

echo "=== Test 4: per-agent reference rewrites via walk-write ==="
for agent in "${AGENTS[@]}"; do
    ./.aitask-scripts/aitask_skill_render.sh aitask-explore --profile fast --agent "$agent" --force >/dev/null 2>&1
done

assert_contains "claude/fast: task-workflow ref rewritten under .claude/skills" \
    ".claude/skills/task-workflow-fast-/SKILL.md" "$(cat .claude/skills/aitask-explore-fast-/SKILL.md)"
assert_contains "codex/fast: task-workflow ref rewritten under .agents/skills" \
    ".agents/skills/task-workflow-fast-codex-/SKILL.md" "$(cat .agents/skills/aitask-explore-fast-codex-/SKILL.md)"
assert_contains "opencode/fast: task-workflow ref rewritten under .opencode/skills" \
    ".opencode/skills/task-workflow-fast-/SKILL.md" "$(cat .opencode/skills/aitask-explore-fast-/SKILL.md)"

# === Test 5: stub-marker checks ===

echo "=== Test 5: 3 stub files contain canonical markers ==="
CLAUDE_STUB=".claude/skills/aitask-explore/SKILL.md"
CODEX_STUB=".agents/skills/aitask-explore/SKILL.md"
OPENCODE_STUB=".opencode/commands/aitask-explore.md"

for stub in "$CLAUDE_STUB" "$CODEX_STUB" "$OPENCODE_STUB"; do
    body="$(cat "$stub")"
    assert_contains "$stub: resolve_profile uses short name 'explore' (t777_26)" \
        "aitask_skill_resolve_profile.sh explore" "$body"
    assert_not_contains "$stub: resolve_profile does NOT use full slug 'aitask-explore'" \
        "aitask_skill_resolve_profile.sh aitask-explore" "$body"
    assert_contains "$stub: skill render invocation present" \
        "aitask_skill_render.sh aitask-explore" "$body"
    assert_contains "$stub: Read-and-follow marker present" \
        "Dispatch via Read-and-follow" "$body"
done

# Per-agent agent_literal substitution checks
assert_contains "claude stub: --agent claude" "--agent claude" "$(cat "$CLAUDE_STUB")"
assert_contains "codex stub: --agent codex" "--agent codex" "$(cat "$CODEX_STUB")"
assert_contains "opencode stub: --agent opencode" "--agent opencode" "$(cat "$OPENCODE_STUB")"

# Per-agent rendered-variant Read target checks
assert_contains "claude stub: reads from .claude/skills/aitask-explore-<profile>-" \
    ".claude/skills/aitask-explore-<profile>-/SKILL.md" "$(cat "$CLAUDE_STUB")"
assert_contains "codex stub: reads from .agents/skills/aitask-explore-<profile>-" \
    ".agents/skills/aitask-explore-<profile>-codex-/SKILL.md" "$(cat "$CODEX_STUB")"
assert_contains "opencode stub: reads from .opencode/skills/aitask-explore-<profile>-" \
    ".opencode/skills/aitask-explore-<profile>-/SKILL.md" "$(cat "$OPENCODE_STUB")"

# === Test 6: cross-repo paired-planning trigger (t832_11) ===
#
# explore sets `xdeprepo` at task creation (auto-detected from the user's
# free-text exploration scope); the cross-repo design + creation dispatch is
# INHERITED from the task-workflow handoff, never duplicated into explore.

echo "=== Test 6: cross-repo scope detection + inherited dispatch ==="
for profile in "${PROFILES[@]}"; do
    rendered="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"

    assert_contains "$profile: cross-repo scope detection reads registry" \
        "aitask_project_resolve.sh list" "$rendered"
    assert_contains "$profile: runtime var cross_repo_scope present" \
        "cross_repo_scope" "$rendered"
    assert_contains "$profile: sets xdeprepo at creation" \
        "xdeprepo" "$rendered"
    assert_contains "$profile: conditional cross-repo paired option" \
        "Create as cross-repo paired task" "$rendered"

    # Dispatch is inherited from task-workflow, NOT duplicated into explore.
    assert_not_contains "$profile: does NOT dispatch planning-cross-repo.md" \
        "planning-cross-repo.md" "$rendered"
    assert_not_contains "$profile: does NOT dispatch cross-repo-child-assignment.md" \
        "cross-repo-child-assignment.md" "$rendered"

    # The first "what to explore" prompt must precede any registry read
    # (no upfront I/O before the first AskUserQuestion).
    prompt_ln="$(printf '%s\n' "$rendered" | grep -n 'What would you like to explore?' | head -1 | cut -d: -f1)"
    probe_ln="$(printf '%s\n' "$rendered" | grep -n 'aitask_project_resolve.sh list' | head -1 | cut -d: -f1)"
    TOTAL=$((TOTAL + 1))
    if [[ -n "$prompt_ln" && -n "$probe_ln" && "$prompt_ln" -lt "$probe_ln" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $profile: first explore prompt (line $prompt_ln) must precede registry read (line $probe_ln)"
    fi
done

# === Summary ===

echo ""
echo "Tests: $TOTAL, Passed: $PASS, Failed: $FAIL"
[[ "$FAIL" -eq 0 ]] || exit 1
