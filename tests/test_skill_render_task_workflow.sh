#!/usr/bin/env bash
# test_skill_render_task_workflow.sh - Regression tests for the wrapped
# shared workflow under .claude/skills/task-workflow/:
#   - 11 wrapped .md files (6 profile-varying + 5 profile-invariant)
#   - 23 golden files under tests/golden/procs/task-workflow/
# Coverage:
#   1.  Per-(file, profile) golden diff for the 4 profile-varying wrapped
#       files × 3 profiles.
#   1b. remote-drift-check is profile-invariant — a single canonical golden
#       plus a byte-equality assertion across all 3 profile renders.
#   2. Agent byte-identity: rendering SKILL.md with profile=fast across all
#      4 agents yields byte-identical output (task-workflow uses only
#      sibling refs, which the dep-walker leaves unchanged regardless of
#      --agent).
#   3. default-profile renders contain the original AskUserQuestion blocks
#      verbatim (no key is defined → all guards fall through to {% else %}).
#   4. remote_drift_check synthetic profile demonstrates the true branch
#      fires when the key is defined (no committed profile uses it).
#   5. risk_evaluation synthetic profile demonstrates the gated risk steps
#      (planning.md eval step + mitigation design, SKILL.md two-field write +
#      "before" creation + Step 8d "after" creation) fire when the key is
#      defined; default renders show none (no committed profile uses it).
# Run: bash tests/test_skill_render_task_workflow.sh

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
WORKFLOW_DIR=".claude/skills/task-workflow"
GOLDEN_DIR="tests/golden/procs/task-workflow"
PROFILES_DIR="aitasks/metadata/profiles"

# remote-drift-check is profile-invariant (its conditional is activated only
# by a synthetic profile — see Test 4), so it keeps one canonical golden.
WRAPPED_FILES_VARYING=(
    "SKILL.md"
    "planning.md"
    "manual-verification.md"
    "manual-verification-followup.md"
    "auto-verification.md"
    "satisfaction-feedback.md"
)
WRAPPED_FILES_INVARIANT=(
    "remote-drift-check.md"
    "planning-cross-repo.md"
    "cross-repo-child-assignment.md"
    "risk-evaluation.md"
    "risk-mitigation-followup.md"
)
PROFILES=(default fast remote)
AGENTS=(claude codex opencode)

# === Test 1: Per-(file, profile) golden diff (profile-varying files) ===

echo "=== Test 1: golden diffs for 6 profile-varying wrapped files × 3 profiles ==="
for file in "${WRAPPED_FILES_VARYING[@]}"; do
    stem="${file%.md}"
    for profile in "${PROFILES[@]}"; do
        rendered="$($RENDER "$WORKFLOW_DIR/$file" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
        golden_path="$GOLDEN_DIR/${stem}-${profile}.md"
        golden_content="$(cat "$golden_path")"
        assert_eq "golden $stem × $profile" "$golden_content" "$rendered"
    done
done

# === Test 1b: profile-invariant wrapped files — canonical golden + invariance ===
#
# remote-drift-check's profile conditional is activated only by a synthetic
# profile (Test 4), so all 3 committed-profile renders are byte-identical.
# One canonical -default golden replaces the 2 deleted profile dupes; the
# invariance assertion fails LOUDLY if a committed profile ever diverges it.
echo "=== Test 1b: profile-invariant wrapped files — canonical golden + invariance ==="
for file in "${WRAPPED_FILES_INVARIANT[@]}"; do
    stem="${file%.md}"
    base="$($RENDER "$WORKFLOW_DIR/$file" "$PROFILES_DIR/default.yaml" claude 2>&1)"
    golden_content="$(cat "$GOLDEN_DIR/${stem}-default.md")"
    assert_eq "golden $stem (canonical)" "$golden_content" "$base"
    for profile in "${PROFILES[@]}"; do
        rendered="$($RENDER "$WORKFLOW_DIR/$file" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
        assert_eq "$stem profile-invariant ($profile==default)" "$base" "$rendered"
    done
done

# === Test 2: Agent byte-identity (task-workflow has only sibling refs) ===

echo "=== Test 2: agent byte-identity for SKILL.md @ profile=fast ==="
REF_OUT="$($RENDER "$WORKFLOW_DIR/SKILL.md" "$PROFILES_DIR/fast.yaml" claude 2>&1)"
for agent in "${AGENTS[@]}"; do
    out="$($RENDER "$WORKFLOW_DIR/SKILL.md" "$PROFILES_DIR/fast.yaml" "$agent" 2>&1)"
    if [[ "$out" == "$REF_OUT" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: SKILL.md fast render differs for agent=$agent vs claude"
    fi
    TOTAL=$((TOTAL + 1))
done

# === Test 2b: agent byte-identity for planning.md @ profile=fast (t818) ===
# The shared {% include "_plan_contract.md" %} resolves agent-agnostically
# (the include target is markdown, not a refs-bearing template), so the
# rendered planning.md is identical across all 4 agent trees.
echo "=== Test 2b: agent byte-identity for planning.md @ profile=fast ==="
REF_PLAN="$($RENDER "$WORKFLOW_DIR/planning.md" "$PROFILES_DIR/fast.yaml" claude 2>&1)"
for agent in "${AGENTS[@]}"; do
    out="$($RENDER "$WORKFLOW_DIR/planning.md" "$PROFILES_DIR/fast.yaml" "$agent" 2>&1)"
    if [[ "$out" == "$REF_PLAN" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: planning.md fast render differs for agent=$agent vs claude"
    fi
    TOTAL=$((TOTAL + 1))
done

# === Test 2c: planning.md resolves _planning_plan_contract.md (t818) ===
# Verifies the {% include "_planning_plan_contract.md" %} directive resolves
# through the extended minijinja loader path (search dir =
# .aitask-scripts/skill_templates/). The fragment is the planning-specific
# single-level "Detailed" spec. Catches regressions where the include target
# moves or the loader path config drifts.
echo "=== Test 2c: planning.md embeds resolved _planning_plan_contract.md ==="
for profile in "${PROFILES[@]}"; do
    rendered="$($RENDER "$WORKFLOW_DIR/planning.md" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    assert_contains "planning.md $profile: planning spec present" \
        'Create a detailed, step-by-step implementation plan. "Detailed" means:' "$rendered"
    assert_contains "planning.md $profile: planning spec continuation present" \
        "code snippets for non-trivial modifications" "$rendered"
    assert_not_contains "planning.md $profile: no literal include tag survives" \
        '{% include' "$rendered"
done

# === Test 3: default profile preserves all AskUserQuestion blocks ===

echo "=== Test 3: default profile keeps existing interactive prose ==="
DEFAULT_SKILL="$($RENDER "$WORKFLOW_DIR/SKILL.md" "$PROFILES_DIR/default.yaml" claude 2>&1)"
assert_contains "SKILL.md default: create_worktree AskUserQuestion present" \
    'Do you want to create a separate branch and worktree for this task?' "$DEFAULT_SKILL"
assert_contains "SKILL.md default: base_branch AskUserQuestion present" \
    'Which branch should the new task branch be based on?' "$DEFAULT_SKILL"
assert_contains "SKILL.md default: default_email AskUserQuestion present" \
    'Enter your email to track who is working on this task' "$DEFAULT_SKILL"

DEFAULT_PLAN="$($RENDER "$WORKFLOW_DIR/planning.md" "$PROFILES_DIR/default.yaml" claude 2>&1)"
assert_contains "planning.md default: plan_preference AskUserQuestion present" \
    'An existing implementation plan was found at' "$DEFAULT_PLAN"
assert_contains "planning.md default: post_plan_action AskUserQuestion present" \
    'Plan saved to' "$DEFAULT_PLAN"

DEFAULT_MVF="$($RENDER "$WORKFLOW_DIR/manual-verification-followup.md" "$PROFILES_DIR/default.yaml" claude 2>&1)"
assert_contains "manual-verification-followup default: 'never' guidance present" \
    'manual_verification_followup_mode' "$DEFAULT_MVF"

DEFAULT_RDC="$($RENDER "$WORKFLOW_DIR/remote-drift-check.md" "$PROFILES_DIR/default.yaml" claude 2>&1)"
assert_contains "remote-drift-check default: 'skip' fallback prose present" \
    'remote_drift_check: skip' "$DEFAULT_RDC"

DEFAULT_SF="$($RENDER "$WORKFLOW_DIR/satisfaction-feedback.md" "$PROFILES_DIR/default.yaml" claude 2>&1)"
assert_contains "satisfaction-feedback default: enableFeedbackQuestions prose present" \
    'If `enableFeedbackQuestions` is omitted' "$DEFAULT_SF"

# === Test 3b: rendered SKILL.md must NOT include Step 3b refresh (t777_26) ===

echo "=== Test 3b: SKILL.md rendered output has no Step 3b refresh ==="
for profile in "${PROFILES[@]}"; do
    rendered="$($RENDER "$WORKFLOW_DIR/SKILL.md" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    assert_not_contains "SKILL.md $profile: no Step 3b heading" \
        "Step 3b: refresh execution profile" "$rendered"
    assert_not_contains "SKILL.md $profile: no scan-profiles call" \
        "aitask_scan_profiles.sh" "$rendered"
    assert_not_contains "SKILL.md $profile: no refresh profile prose" \
        "refresh execution profile" "$rendered"
done

# === Test 4: synthetic profile with remote_drift_check: skip fires the true branch ===

echo "=== Test 4: synthetic remote_drift_check: skip profile ==="
TMP_PROFILE="$(mktemp "${TMPDIR:-/tmp}/test_rdc_XXXXXX.yaml")"
trap 'rm -f "$TMP_PROFILE"' EXIT
cat > "$TMP_PROFILE" <<'YAML'
name: test_rdc_skip
description: "Synthetic profile for t777_7 test (remote_drift_check skip)"
remote_drift_check: skip
YAML
SYNTH_OUT="$($RENDER "$WORKFLOW_DIR/remote-drift-check.md" "$TMP_PROFILE" claude 2>&1)"
assert_contains "synthetic profile triggers true branch (return immediately)" \
    "Profile 'test_rdc_skip' sets" "$SYNTH_OUT"
assert_not_contains "synthetic profile suppresses fallback prose" \
    '**Profile check.** If the active profile has' "$SYNTH_OUT"

# === Test 5: synthetic risk_evaluation: true fires the gated risk steps (t884_3) ===
#
# The risk-evaluation gate is a zero-footprint {%- if profile.risk_evaluation
# is defined and profile.risk_evaluation %} wrap at two dispatch sites:
# planning.md §6.1 (the eval step) and SKILL.md Step 7 (the two-field write).
# fast.yaml sets risk_evaluation: true, so the committed fast goldens
# (planning-fast / SKILL-fast) carry the gated steps, while default/remote omit
# them (all proven by Test 1's per-profile goldens). The synthetic
# risk_evaluation: true profile below still proves both branches fire
# independently of any committed profile, and the default profile (key absent)
# proves absence.
echo "=== Test 5: synthetic risk_evaluation: true profile ==="
TMP_RISK="$(mktemp "${TMPDIR:-/tmp}/test_risk_XXXXXX.yaml")"
trap 'rm -f "$TMP_PROFILE" "$TMP_RISK"' EXIT
cat > "$TMP_RISK" <<'YAML'
name: test_risk_eval
description: "Synthetic profile for t884_3 test (risk_evaluation true)"
risk_evaluation: true
YAML
RISK_PLAN="$($RENDER "$WORKFLOW_DIR/planning.md" "$TMP_RISK" claude 2>&1)"
RISK_SKILL="$($RENDER "$WORKFLOW_DIR/SKILL.md" "$TMP_RISK" claude 2>&1)"
assert_contains "risk_evaluation true: planning.md emits the eval step" \
    'Risk evaluation (end of planning)' "$RISK_PLAN"
assert_contains "risk_evaluation true: planning.md emits the mitigation design step" \
    'Risk-mitigation design (end of planning)' "$RISK_PLAN"
assert_contains "risk_evaluation true: SKILL.md emits the two-field write" \
    '--risk-code-health' "$RISK_SKILL"
assert_contains "risk_evaluation true: SKILL.md write includes goal-achievement flag" \
    '--risk-goal-achievement' "$RISK_SKILL"
assert_contains "risk_evaluation true: SKILL.md emits the Step 7 'before' creation hook" \
    'Risk-mitigation "before" creation' "$RISK_SKILL"
assert_contains "risk_evaluation true: SKILL.md emits Step 8d 'after' creation" \
    'Step 8d: Risk-Mitigation' "$RISK_SKILL"
assert_contains "risk_evaluation true: Step 8c points to Step 8d" \
    'proceed to Step 8d' "$RISK_SKILL"
# Default profile (key absent) shows none — guards the zero-footprint claim.
DEFAULT_RISK_PLAN="$($RENDER "$WORKFLOW_DIR/planning.md" "$PROFILES_DIR/default.yaml" claude 2>&1)"
DEFAULT_RISK_SKILL="$($RENDER "$WORKFLOW_DIR/SKILL.md" "$PROFILES_DIR/default.yaml" claude 2>&1)"
assert_not_contains "default profile: no planning risk step" \
    'Risk evaluation (end of planning)' "$DEFAULT_RISK_PLAN"
assert_not_contains "default profile: no planning mitigation design step" \
    'Risk-mitigation design (end of planning)' "$DEFAULT_RISK_PLAN"
assert_not_contains "default profile: no Step 7 risk write" \
    '--risk-code-health' "$DEFAULT_RISK_SKILL"
assert_not_contains "default profile: no Step 7 'before' creation hook" \
    'Risk-mitigation "before" creation' "$DEFAULT_RISK_SKILL"
assert_not_contains "default profile: no Step 8d" \
    'Step 8d: Risk-Mitigation' "$DEFAULT_RISK_SKILL"
# Step 8c's default pointer to Step 9 must be byte-stable when the key is absent.
assert_contains "default profile: Step 8c points to Step 9" \
    'proceed to Step 9.' "$DEFAULT_RISK_SKILL"

# === Summary ===

echo ""
echo "Tests: $TOTAL, Passed: $PASS, Failed: $FAIL"
[[ "$FAIL" -eq 0 ]] || exit 1
