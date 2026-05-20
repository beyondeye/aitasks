#!/usr/bin/env bash
# test_skill_render_aitask_qa.sh - Regression tests for t777_11:
#   - .claude/skills/aitask-qa/SKILL.md.j2 (entry-point template)
#   - 3 profile-bearing procedure files (task-selection / test-execution /
#     test-plan-proposal) wrapped with Jinja profile conditionals
#   - 4 per-agent stubs (claude/codex/gemini/opencode)
#   - 12 entry-point goldens under tests/golden/skills/aitask-qa/
#   - 9 procedure goldens under tests/golden/procs/aitask-qa/
# Coverage:
#   1.  Per-(profile, agent) golden diff for the entry-point template.
#   1p. Per-(file, profile) golden diff for the 3 wrapped procedure files,
#       plus agent-invariance (procedures carry no per-agent refs).
#   2.  Profile-conditional sanity for qa_tier / qa_mode / qa_run_tests /
#       skip_task_confirmation.
#   3.  No Jinja markers leak into entry-point or procedure renders.
#   3b. Rendered output must NOT re-resolve profile (t777_26 forbidden tokens).
#   4.  Per-agent reference rewrites for the task-workflow full-path ref.
#   5.  Stub markers present on all 4 stub files (canonical body fingerprint
#       from aidocs/stub-skill-pattern.md §3b/§3c/§3d).
# Run: bash tests/test_skill_render_aitask_qa.sh

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
TEMPLATE=".claude/skills/aitask-qa/SKILL.md.j2"
SKILL_GOLDEN_DIR="tests/golden/skills/aitask-qa"
PROC_GOLDEN_DIR="tests/golden/procs/aitask-qa"
PROFILES_DIR="aitasks/metadata/profiles"

PROFILES=(default fast remote)
AGENTS=(claude codex gemini opencode)
# Procedure files that carry profile conditionals (rendered into the closure).
PROC_FILES=(task-selection test-execution test-plan-proposal)

# === Test 1: 12 per-(profile, agent) entry-point golden diffs ===

echo "=== Test 1: golden diffs for entry-point × 3 profiles × 4 agents ==="
for profile in "${PROFILES[@]}"; do
    for agent in "${AGENTS[@]}"; do
        rendered="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" "$agent" 2>&1)"
        golden_path="$SKILL_GOLDEN_DIR/SKILL-${profile}-${agent}.md"
        golden_content="$(cat "$golden_path")"
        assert_eq "golden SKILL × $profile × $agent" "$golden_content" "$rendered"
    done
done

# === Test 1p: 9 per-(file, profile) procedure golden diffs + agent-invariance ===
#
# The 3 wrapped procedure files reference only each other / the main workflow
# via prose and carry no per-agent (full-path) refs, so their render is
# agent-invariant — goldens are claude-only and the codex/gemini/opencode
# renders must match the claude render byte-for-byte.

echo "=== Test 1p: procedure golden diffs + agent-invariance ==="
for f in "${PROC_FILES[@]}"; do
    for profile in "${PROFILES[@]}"; do
        rendered="$($RENDER ".claude/skills/aitask-qa/$f.md" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
        golden_content="$(cat "$PROC_GOLDEN_DIR/$f-$profile.md")"
        assert_eq "golden proc $f × $profile" "$golden_content" "$rendered"
        for agent in codex gemini opencode; do
            other="$($RENDER ".claude/skills/aitask-qa/$f.md" "$PROFILES_DIR/$profile.yaml" "$agent" 2>&1)"
            assert_eq "proc $f × $profile agent-invariant ($agent==claude)" "$rendered" "$other"
        done
    done
done

# === Test 2: profile-conditional sanity ===
#
# No committed profile sets qa_tier or qa_run_tests; qa_mode is only ever
# "ask" (fast) or unset (default/remote) — all fall through to the {% else %}
# arm. skip_task_confirmation is true for fast/remote, unset for default, so
# both arms get real golden coverage.

echo "=== Test 2: profile branches fire correctly ==="
for profile in "${PROFILES[@]}"; do
    skill="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    # qa_tier else arm fires; if arm (baked Display) does not.
    assert_contains "$profile: qa_tier else arm (AskUserQuestion)" \
        "Select QA analysis depth:" "$skill"
    assert_not_contains "$profile: no qa_tier if-arm" "': qa_tier=" "$skill"

    tpp="$($RENDER ".claude/skills/aitask-qa/test-plan-proposal.md" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    # qa_mode else arm fires; no baked-action if/elif arms.
    assert_contains "$profile: qa_mode else arm (AskUserQuestion)" \
        "How would you like to proceed with the test plan?" "$tpp"
    assert_not_contains "$profile: no qa_mode if-arm" "': qa_mode=" "$tpp"

    texec="$($RENDER ".claude/skills/aitask-qa/test-execution.md" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    # qa_run_tests one-armed block stays empty (key unset everywhere).
    assert_not_contains "$profile: qa_run_tests block empty" \
        "test execution disabled" "$texec"

    tsel="$($RENDER ".claude/skills/aitask-qa/task-selection.md" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    if [[ "$profile" == "default" ]]; then
        assert_contains "$profile: skip_task_confirmation else arm (AskUserQuestion)" \
            "Run QA analysis on this task?" "$tsel"
        assert_not_contains "$profile: no skip_task_confirmation if-arm" \
            "': auto-confirming task selection" "$tsel"
    else
        assert_contains "$profile: skip_task_confirmation if arm (auto-confirm)" \
            "': auto-confirming task selection" "$tsel"
        assert_not_contains "$profile: no skip_task_confirmation else arm" \
            "Run QA analysis on this task?" "$tsel"
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
    for f in "${PROC_FILES[@]}"; do
        rendered="$($RENDER ".claude/skills/aitask-qa/$f.md" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
        assert_not_contains "no Jinja {% leak $f × $profile" "{%" "$rendered"
        assert_not_contains "no Jinja {{ leak $f × $profile" "{{" "$rendered"
    done
done

# === Test 3b: rendered body must NOT re-resolve profile at runtime (t777_26) ===

echo "=== Test 3b: rendered output has no runtime profile-resolution tokens ==="
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
            assert_not_contains "SKILL $profile × $agent has no '$token'" \
                "$token" "$rendered"
        done
    done
    for f in "${PROC_FILES[@]}"; do
        rendered="$($RENDER ".claude/skills/aitask-qa/$f.md" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
        for token in "${FORBIDDEN_TOKENS[@]}"; do
            assert_not_contains "$f $profile has no '$token'" "$token" "$rendered"
        done
    done
done

# === Test 4: cross-agent reference rewrites (via walk-write on-disk output) ===

echo "=== Test 4: per-agent reference rewrites via walk-write ==="
for agent in "${AGENTS[@]}"; do
    ./.aitask-scripts/aitask_skill_render.sh aitask-qa --profile fast --agent "$agent" --force >/dev/null 2>&1
done

assert_contains "claude/fast: task-workflow ref rewritten under .claude/skills" \
    ".claude/skills/task-workflow-fast-/satisfaction-feedback.md" \
    "$(cat .claude/skills/aitask-qa-fast-/SKILL.md)"
assert_contains "codex/fast: task-workflow ref rewritten under .agents/skills" \
    ".agents/skills/task-workflow-fast-/satisfaction-feedback.md" \
    "$(cat .agents/skills/aitask-qa-fast-/SKILL.md)"
assert_contains "gemini/fast: task-workflow ref rewritten under .gemini/skills" \
    ".gemini/skills/task-workflow-fast-/satisfaction-feedback.md" \
    "$(cat .gemini/skills/aitask-qa-fast-/SKILL.md)"
assert_contains "opencode/fast: task-workflow ref rewritten under .opencode/skills" \
    ".opencode/skills/task-workflow-fast-/satisfaction-feedback.md" \
    "$(cat .opencode/skills/aitask-qa-fast-/SKILL.md)"

# Procedure files render into the same per-profile dir as the entry point.
assert_contains "claude/fast: procedure files rendered into closure dir" \
    "Test Plan Proposal Procedure" \
    "$(cat .claude/skills/aitask-qa-fast-/test-plan-proposal.md)"

# === Test 5: stub-marker checks ===

echo "=== Test 5: 4 stub files contain canonical markers ==="
CLAUDE_STUB=".claude/skills/aitask-qa/SKILL.md"
CODEX_STUB=".agents/skills/aitask-qa/SKILL.md"
GEMINI_STUB=".gemini/commands/aitask-qa.toml"
OPENCODE_STUB=".opencode/commands/aitask-qa.md"

for stub in "$CLAUDE_STUB" "$CODEX_STUB" "$GEMINI_STUB" "$OPENCODE_STUB"; do
    body="$(cat "$stub")"
    assert_contains "$stub: resolve_profile uses short name 'qa' (t777_26)" \
        "aitask_skill_resolve_profile.sh qa" "$body"
    assert_not_contains "$stub: resolve_profile does NOT use full slug 'aitask-qa'" \
        "aitask_skill_resolve_profile.sh aitask-qa" "$body"
    assert_contains "$stub: skill render invocation present" \
        "aitask_skill_render.sh aitask-qa" "$body"
    assert_contains "$stub: Read-and-follow marker present" \
        "Dispatch via Read-and-follow" "$body"
done

# Per-agent agent_literal substitution checks
assert_contains "claude stub: --agent claude" "--agent claude" "$(cat "$CLAUDE_STUB")"
assert_contains "codex stub: --agent codex" "--agent codex" "$(cat "$CODEX_STUB")"
assert_contains "gemini stub: --agent gemini" "--agent gemini" "$(cat "$GEMINI_STUB")"
assert_contains "opencode stub: --agent opencode" "--agent opencode" "$(cat "$OPENCODE_STUB")"

# Per-agent rendered-variant Read target checks
assert_contains "claude stub: reads from .claude/skills/aitask-qa-<profile>-" \
    ".claude/skills/aitask-qa-<profile>-/SKILL.md" "$(cat "$CLAUDE_STUB")"
assert_contains "codex stub: reads from .agents/skills/aitask-qa-<profile>-" \
    ".agents/skills/aitask-qa-<profile>-/SKILL.md" "$(cat "$CODEX_STUB")"
assert_contains "gemini stub: reads from .gemini/skills/aitask-qa-<profile>-" \
    ".gemini/skills/aitask-qa-<profile>-/SKILL.md" "$(cat "$GEMINI_STUB")"
assert_contains "opencode stub: reads from .opencode/skills/aitask-qa-<profile>-" \
    ".opencode/skills/aitask-qa-<profile>-/SKILL.md" "$(cat "$OPENCODE_STUB")"

# === Summary ===

echo ""
echo "Tests: $TOTAL, Passed: $PASS, Failed: $FAIL"
[[ "$FAIL" -eq 0 ]] || exit 1
