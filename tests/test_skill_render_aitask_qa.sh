#!/usr/bin/env bash
# test_skill_render_aitask_qa.sh - Regression tests for t777_11:
#   - .claude/skills/aitask-qa/SKILL.md.j2 (entry-point template)
#   - 3 profile-bearing procedure files (task-selection / test-execution /
#     test-plan-proposal) wrapped with Jinja profile conditionals
#   - 3 per-agent stubs (claude/codex/opencode)
#   - 3 entry-point goldens under tests/golden/skills/aitask-qa/ (3 profiles, claude canonical)
#   - 5 procedure goldens under tests/golden/procs/aitask-qa/
#     (task-selection × 3 profiles + test-execution + test-plan-proposal canonical)
# Coverage:
#   1.  Per-profile golden diff for the entry-point template (claude render).
#   1b. Agent-dimension invariance for the entry-point (no {% if agent %}).
#   1p. Procedure goldens: per-(file, profile) diff for the profile-varying
#       file (task-selection), and a single canonical golden for the
#       profile-invariant files (test-execution, test-plan-proposal), each
#       with profile- and agent-invariance assertions.
#   2.  Profile-conditional sanity for qa_tier / qa_mode / qa_run_tests /
#       skip_task_confirmation.
#   3.  No Jinja markers leak into entry-point or procedure renders.
#   3b. Rendered output must NOT re-resolve profile (t777_26 forbidden tokens).
#   4.  Per-agent reference rewrites for the task-workflow full-path ref.
#   5.  Stub markers present on all 3 stub files (canonical body fingerprint
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
AGENTS=(claude codex opencode)
# Procedure files rendered into the closure. All carry profile conditionals,
# but only task-selection's conditional is activated by a committed profile;
# test-execution / test-plan-proposal render identically across all profiles.
PROC_FILES=(task-selection test-execution test-plan-proposal)
PROC_FILES_VARYING=(task-selection)
PROC_FILES_INVARIANT=(test-execution test-plan-proposal)

# === Test 1: per-profile entry-point golden diffs (claude render is canonical) ===

echo "=== Test 1: golden diffs for entry-point × 3 profiles ==="
for profile in "${PROFILES[@]}"; do
    rendered="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    golden_content="$(cat "$SKILL_GOLDEN_DIR/SKILL-${profile}-claude.md")"
    assert_eq "golden SKILL × $profile" "$golden_content" "$rendered"
done

# === Test 1b: entry-point agent dimension invariance ===
#
# The entry-point template has no {% if agent %} gate, so the basic
# stdout render is byte-identical across all 4 agents. Replaces the 9
# deleted per-agent goldens; fails LOUDLY if agent gating is ever added.
echo "=== Test 1b: agent renders are byte-identical (no {% if agent %} in template) ==="
for profile in "${PROFILES[@]}"; do
    base="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    for agent in codex opencode; do
        cmp="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" "$agent" 2>&1)"
        assert_eq "agent invariance $profile/$agent" "$base" "$cmp"
    done
done

# === Test 1p: procedure golden diffs + profile/agent invariance ===
#
# Procedure files carry no per-agent (full-path) refs, so all renders are
# agent-invariant — goldens are claude-only. task-selection's profile
# conditional is activated by committed profiles, so it keeps one golden per
# profile. test-execution / test-plan-proposal are profile-invariant (no
# committed profile activates their conditionals): a single canonical
# -default golden replaces the 4 deleted profile dupes, and an invariance
# assertion across all profiles × agents fails LOUDLY if that ever changes.

echo "=== Test 1p: procedure golden diffs + profile/agent invariance ==="
# Profile-varying procedures: one golden per profile, agent-invariant.
for f in "${PROC_FILES_VARYING[@]}"; do
    for profile in "${PROFILES[@]}"; do
        rendered="$($RENDER ".claude/skills/aitask-qa/$f.md" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
        golden_content="$(cat "$PROC_GOLDEN_DIR/$f-$profile.md")"
        assert_eq "golden proc $f × $profile" "$golden_content" "$rendered"
        for agent in codex opencode; do
            other="$($RENDER ".claude/skills/aitask-qa/$f.md" "$PROFILES_DIR/$profile.yaml" "$agent" 2>&1)"
            assert_eq "proc $f × $profile agent-invariant ($agent==claude)" "$rendered" "$other"
        done
    done
done
# Profile-invariant procedures: single canonical -default golden + invariance
# across every profile × agent combination.
for f in "${PROC_FILES_INVARIANT[@]}"; do
    base="$($RENDER ".claude/skills/aitask-qa/$f.md" "$PROFILES_DIR/default.yaml" claude 2>&1)"
    golden_content="$(cat "$PROC_GOLDEN_DIR/$f-default.md")"
    assert_eq "golden proc $f (canonical)" "$golden_content" "$base"
    for profile in "${PROFILES[@]}"; do
        for agent in "${AGENTS[@]}"; do
            cmp="$($RENDER ".claude/skills/aitask-qa/$f.md" "$PROFILES_DIR/$profile.yaml" "$agent" 2>&1)"
            assert_eq "proc $f invariance $profile/$agent" "$base" "$cmp"
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
    ".agents/skills/task-workflow-fast-codex-/satisfaction-feedback.md" \
    "$(cat .agents/skills/aitask-qa-fast-codex-/SKILL.md)"
assert_contains "opencode/fast: task-workflow ref rewritten under .opencode/skills" \
    ".opencode/skills/task-workflow-fast-/satisfaction-feedback.md" \
    "$(cat .opencode/skills/aitask-qa-fast-/SKILL.md)"

# Procedure files render into the same per-profile dir as the entry point.
assert_contains "claude/fast: procedure files rendered into closure dir" \
    "Test Plan Proposal Procedure" \
    "$(cat .claude/skills/aitask-qa-fast-/test-plan-proposal.md)"

# === Test 5: stub-marker checks ===

echo "=== Test 5: 3 stub files contain canonical markers ==="
CLAUDE_STUB=".claude/skills/aitask-qa/SKILL.md"
CODEX_STUB=".agents/skills/aitask-qa/SKILL.md"
OPENCODE_STUB=".opencode/commands/aitask-qa.md"

for stub in "$CLAUDE_STUB" "$CODEX_STUB" "$OPENCODE_STUB"; do
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
assert_contains "opencode stub: --agent opencode" "--agent opencode" "$(cat "$OPENCODE_STUB")"

# Per-agent rendered-variant Read target checks
assert_contains "claude stub: reads from .claude/skills/aitask-qa-<profile>-" \
    ".claude/skills/aitask-qa-<profile>-/SKILL.md" "$(cat "$CLAUDE_STUB")"
assert_contains "codex stub: reads from .agents/skills/aitask-qa-<profile>-" \
    ".agents/skills/aitask-qa-<profile>-codex-/SKILL.md" "$(cat "$CODEX_STUB")"
assert_contains "opencode stub: reads from .opencode/skills/aitask-qa-<profile>-" \
    ".opencode/skills/aitask-qa-<profile>-/SKILL.md" "$(cat "$OPENCODE_STUB")"

# === Summary ===

echo ""
echo "Tests: $TOTAL, Passed: $PASS, Failed: $FAIL"
[[ "$FAIL" -eq 0 ]] || exit 1
