#!/usr/bin/env bash
# Regression tests for the experimental task-workflown staging workflow.
# Run: bash tests/test_skill_render_task_workflown.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Shared assertion helpers (see tests/lib/asserts.sh).
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

cd "$PROJECT_DIR"

# shellcheck source=.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"
PYTHON="$(require_ait_python)"
if ! "$PYTHON" -c 'import minijinja' 2>/dev/null; then
    echo "SKIP: minijinja not installed in framework venv ($PYTHON). Run 'ait setup' first."
    exit 0
fi

RENDER="$PYTHON $PROJECT_DIR/.aitask-scripts/lib/skill_template.py"
PROFILES_DIR="aitasks/metadata/profiles"
PROD_DIR=".claude/skills/task-workflow"
EXP_DIR=".claude/skills/task-workflown"

echo "=== Test 1: workflown copied complete source file set ==="
PROD_FILES="$(cd "$PROD_DIR" && find . -maxdepth 1 -type f | sort)"
EXP_FILES="$(cd "$EXP_DIR" && find . -maxdepth 1 -type f | sort)"
assert_eq "source file list parity" "$PROD_FILES" "$EXP_FILES"

echo "=== Test 2: rendered workflow contains experimental gates ==="
SKILL_FAST="$($RENDER "$EXP_DIR/SKILL.md" "$PROFILES_DIR/fast.yaml" claude 2>&1)"
PLANNING_FAST="$($RENDER "$EXP_DIR/planning.md" "$PROFILES_DIR/fast.yaml" claude 2>&1)"
SAT_FAST="$($RENDER "$EXP_DIR/satisfaction-feedback.md" "$PROFILES_DIR/fast.yaml" claude 2>&1)"

assert_contains "SKILL fast render names workflown" "name: task-workflown" "$SKILL_FAST"
assert_contains "SKILL fast render marks staging" "Experimental staging workflow" "$SKILL_FAST"
assert_contains "SKILL fast render has pre-implementation risk gate" "Pre-implementation Risk Gate" "$SKILL_FAST"
assert_contains "SKILL fast render has fail-closed risk write" "Missing \`## Risk\`, missing risk headings, or missing parsed risk levels is an error" "$SKILL_FAST"
assert_contains "SKILL fast render has archive-time risk gate" "Archive-time Risk Gate" "$SKILL_FAST"
assert_contains "SKILL fast render has final-response gate" "Final-response gate" "$SKILL_FAST"
assert_contains "SKILL fast render requires satisfaction status" "satisfaction_feedback_status=rated" "$SKILL_FAST"
assert_contains "SKILL fast render requires risk frontmatter" "risk_goal_achievement" "$SKILL_FAST"

assert_contains "planning fast render requires code-health heading" "### Code-health risk:" "$PLANNING_FAST"
assert_contains "planning fast render requires goal-achievement heading" "### Goal-achievement risk:" "$PLANNING_FAST"
assert_contains "planning fast render says incomplete risk is missing" "produced an incomplete risk section" "$PLANNING_FAST"

assert_contains "satisfaction fast render exposes return contract" "Return contract for task-workflown Step 9b gate" "$SAT_FAST"
assert_contains "satisfaction fast render records skip status" "satisfaction_feedback_status=skipped" "$SAT_FAST"
assert_contains "satisfaction fast render records skip reason" "satisfaction_skip_reason" "$SAT_FAST"
assert_contains "satisfaction fast render forbids silent skip" "Silent skip is not allowed" "$SAT_FAST"

echo "=== Test 3: production workflow does not contain experimental gates ==="
PROD_SKILL="$(cat "$PROD_DIR/SKILL.md")"
PROD_PLANNING="$(cat "$PROD_DIR/planning.md")"
PROD_SAT="$(cat "$PROD_DIR/satisfaction-feedback.md")"
assert_not_contains "production SKILL has no pre-implementation risk gate" "Pre-implementation Risk Gate" "$PROD_SKILL"
assert_not_contains "production SKILL has no archive-time risk gate" "Archive-time Risk Gate" "$PROD_SKILL"
assert_not_contains "production SKILL has no final-response gate" "Final-response gate" "$PROD_SKILL"
assert_not_contains "production planning has no incomplete risk wording" "produced an incomplete risk section" "$PROD_PLANNING"
assert_not_contains "production satisfaction has no workflown return contract" "Return contract for task-workflown Step 9b gate" "$PROD_SAT"

echo ""
echo "Tests: $TOTAL, Passed: $PASS, Failed: $FAIL"
[[ "$FAIL" -eq 0 ]] || exit 1
