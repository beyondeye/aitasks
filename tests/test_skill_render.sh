#!/usr/bin/env bash
# test_skill_render.sh - Automated tests for t777_2:
#   - .aitask-scripts/aitask_skill_render.sh (per-profile renderer + dispatch)
#   - helper whitelist touchpoints for aitask_skill_render.sh
# Run: bash tests/test_skill_render.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
SKIP=0
TOTAL=0

# Shared assertion helpers (see tests/lib/asserts.sh)
. "$PROJECT_DIR/tests/lib/asserts.sh"


assert_nonzero_exit() {
    local desc="$1" rc="$2"
    TOTAL=$((TOTAL + 1))
    if [[ "$rc" -ne 0 ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected non-zero exit, got 0)"
    fi
}

# --- Resolve Python interpreter ---

cd "$PROJECT_DIR"
# shellcheck source=.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"
PYTHON="$(require_ait_python)"
if ! "$PYTHON" -c 'import minijinja' 2>/dev/null; then
    echo "SKIP: minijinja not installed in framework venv ($PYTHON). Run 'ait setup' first."
    exit 0
fi

RENDER="$PROJECT_DIR/.aitask-scripts/aitask_skill_render.sh"

# --- Scratch workspace ---

TMP_DIR="$(mktemp -d)"

# Scratch skills under .claude/skills/ that the script will discover via
# agent_authoring_template. Prefix _t777_2_test_ to make cleanup unambiguous.
TEST_SKILL_PREFIX="_t777_2_test_"

cleanup() {
    rm -rf "$TMP_DIR"
    # Remove any scratch skill dirs (template authoring dirs + rendered output dirs).
    # shellcheck disable=SC2115
    rm -rf "$PROJECT_DIR"/.claude/skills/"${TEST_SKILL_PREFIX}"* \
           "$PROJECT_DIR"/.agents/skills/"${TEST_SKILL_PREFIX}"* \
           "$PROJECT_DIR"/.opencode/skills/"${TEST_SKILL_PREFIX}"*
}
trap cleanup EXIT
# Pre-clean in case a prior aborted run left scratch dirs.
cleanup

# Resolve mtime portably for assertions inside the test.
_t_mtime() { stat -c %Y "$1" 2>/dev/null || stat -f %m "$1"; }

# --- Test 1: Basic render ---

SK1="${TEST_SKILL_PREFIX}basic"
mkdir -p ".claude/skills/$SK1"
cat > ".claude/skills/$SK1/SKILL.md.j2" <<'EOF'
# Smoke ({{ profile.name }}/{{ agent }})
skip_task_confirmation: {{ profile.skip_task_confirmation }}
EOF

"$RENDER" "$SK1" --profile fast --agent claude

TARGET1=".claude/skills/${SK1}-fast-/SKILL.md"
TOTAL=$((TOTAL + 1))
if [[ -f "$TARGET1" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1)); echo "FAIL: basic render did not produce $TARGET1"
fi
RENDERED1="$(cat "$TARGET1" 2>/dev/null || echo "")"
assert_contains_ci "basic render: profile.name substituted"            "Smoke (fast/claude)"           "$RENDERED1"
assert_contains_ci "basic render: skip_task_confirmation substituted"  "skip_task_confirmation: true"  "$RENDERED1"

# --- Test 2: Skip-if-fresh — second run no-op ---

MTIME_BEFORE=$(_t_mtime "$TARGET1")
sleep 1
"$RENDER" "$SK1" --profile fast --agent claude
MTIME_AFTER=$(_t_mtime "$TARGET1")
assert_eq "skip-if-fresh: second run does not rewrite target" "$MTIME_BEFORE" "$MTIME_AFTER"

# --- Test 3: Newer template mtime triggers re-render ---

sleep 1
touch ".claude/skills/$SK1/SKILL.md.j2"
"$RENDER" "$SK1" --profile fast --agent claude
MTIME_NEW=$(_t_mtime "$TARGET1")
TOTAL=$((TOTAL + 1))
if (( MTIME_NEW > MTIME_AFTER )); then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1)); echo "FAIL: newer template should re-render (before=$MTIME_AFTER, after=$MTIME_NEW)"
fi

# --- Test 4: Newer profile YAML mtime triggers re-render ---

# Use a scratch profile YAML so the test does NOT touch the real fast.yaml mtime.
SCRATCH_PROFILE_DIR="$PROJECT_DIR/aitasks/metadata/profiles"
SCRATCH_PROFILE_FILE="${TEST_SKILL_PREFIX}testprofile.yaml"
SCRATCH_PROFILE_PATH="$SCRATCH_PROFILE_DIR/$SCRATCH_PROFILE_FILE"
SCRATCH_PROFILE_NAME="_t777_2_test_profile"
cat > "$SCRATCH_PROFILE_PATH" <<EOF
name: $SCRATCH_PROFILE_NAME
description: scratch profile for test_skill_render.sh
skip_task_confirmation: false
EOF
# Augment cleanup to also remove the scratch profile YAML.
cleanup_with_profile() {
    rm -f "$SCRATCH_PROFILE_PATH"
    cleanup
}
trap cleanup_with_profile EXIT

"$RENDER" "$SK1" --profile "$SCRATCH_PROFILE_NAME" --agent claude
TARGET1_SCRATCH=".claude/skills/${SK1}-${SCRATCH_PROFILE_NAME}-/SKILL.md"
SCRATCH_MTIME_BEFORE=$(_t_mtime "$TARGET1_SCRATCH")
sleep 1
touch "$SCRATCH_PROFILE_PATH"
"$RENDER" "$SK1" --profile "$SCRATCH_PROFILE_NAME" --agent claude
SCRATCH_MTIME_AFTER=$(_t_mtime "$TARGET1_SCRATCH")
TOTAL=$((TOTAL + 1))
if (( SCRATCH_MTIME_AFTER > SCRATCH_MTIME_BEFORE )); then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1)); echo "FAIL: newer profile YAML should re-render (before=$SCRATCH_MTIME_BEFORE, after=$SCRATCH_MTIME_AFTER)"
fi

# --- Test 5: --force re-renders unconditionally ---

MTIME_FRESH=$(_t_mtime "$TARGET1")
sleep 1
"$RENDER" "$SK1" --profile fast --agent claude --force
MTIME_FORCED=$(_t_mtime "$TARGET1")
TOTAL=$((TOTAL + 1))
if (( MTIME_FORCED > MTIME_FRESH )); then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1)); echo "FAIL: --force should re-render (before=$MTIME_FRESH, after=$MTIME_FORCED)"
fi

# --- Test 6: Cross-skill .md-reference recursion (t777_22 dep-walker) ---
# Was a {% include %} cross-skill test pre-t777_22. The new model walks plain
# .md refs in the rendered output and renders each referenced source into a
# per-profile sibling dir.

SK_A="${TEST_SKILL_PREFIX}rec_a"
SK_B="${TEST_SKILL_PREFIX}rec_b"
mkdir -p ".claude/skills/$SK_A" ".claude/skills/$SK_B"
# A is a leaf with no Jinja markers (only needs SKILL.md, no .md.j2).
cat > ".claude/skills/$SK_A/SKILL.md" <<'EOF'
# A skill leaf
EOF
# B is the entry (rendered from .md.j2) and references A via full path.
cat > ".claude/skills/$SK_B/SKILL.md.j2" <<EOF
# B skill (agent={{ agent }})
See .claude/skills/${SK_A}/SKILL.md for A.
EOF

"$RENDER" "$SK_B" --profile fast --agent claude

TARGET_A=".claude/skills/${SK_A}-fast-/SKILL.md"
TARGET_B=".claude/skills/${SK_B}-fast-/SKILL.md"
TOTAL=$((TOTAL + 1))
if [[ -f "$TARGET_B" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1)); echo "FAIL: B render did not produce $TARGET_B"
fi
TOTAL=$((TOTAL + 1))
if [[ -f "$TARGET_A" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1)); echo "FAIL: dep-walker did not render A leaf: $TARGET_A"
fi
B_OUT="$(cat "$TARGET_B" 2>/dev/null || echo "")"
assert_contains_ci "B's full-path ref rewritten to per-profile dir" \
    ".claude/skills/${SK_A}-fast-/SKILL.md" "$B_OUT"

# --- Test 7: Same-skill include is inlined, not rendered as separate skill ---

SK_S="${TEST_SKILL_PREFIX}same"
mkdir -p ".claude/skills/$SK_S"
cat > ".claude/skills/$SK_S/_partial.j2" <<'EOF'
PARTIAL_CONTENT
EOF
cat > ".claude/skills/$SK_S/SKILL.md.j2" <<'EOF'
# Same-skill include
{% include "_partial.j2" %}
EOF

"$RENDER" "$SK_S" --profile fast --agent claude

TARGET_S=".claude/skills/${SK_S}-fast-/SKILL.md"
RENDERED_S="$(cat "$TARGET_S" 2>/dev/null || echo "")"
assert_contains_ci "same-skill include inlined into parent output" "PARTIAL_CONTENT" "$RENDERED_S"
# No spurious "_partial" skill dir should be created.
TOTAL=$((TOTAL + 1))
if [[ ! -d ".claude/skills/_partial-fast-" && ! -d ".claude/skills/_partial" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1)); echo "FAIL: same-skill include should not spawn a sibling skill dir"
fi

# --- Test 8: Plain .md includes do NOT trigger recursive render ---

SK_MD="${TEST_SKILL_PREFIX}md_inc"
mkdir -p ".claude/skills/$SK_MD"
# A reference to a plain .md filename in the template (NOT an include directive
# since .md isn't a valid minijinja include extension; the regex skips it).
# We embed something that LOOKS like an include but targets a .md file —
# regex must NOT match it.
cat > ".claude/skills/$SK_MD/SKILL.md.j2" <<'EOF'
# Skill referencing plain md
See {% raw %}{% include "something.md" %}{% endraw %} (this is escaped, not a real include).
Plain text reference: something.md
EOF
"$RENDER" "$SK_MD" --profile fast --agent claude
TARGET_MD=".claude/skills/${SK_MD}-fast-/SKILL.md"
TOTAL=$((TOTAL + 1))
if [[ -f "$TARGET_MD" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1)); echo "FAIL: .md-include test did not produce target file"
fi

# --- Test 9: Missing template — non-zero exit + stderr ---

set +e
ERR_OUT="$("$RENDER" "${TEST_SKILL_PREFIX}_does_not_exist" --profile fast --agent claude 2>&1)"
RC=$?
set -e
assert_nonzero_exit "missing template exits non-zero" "$RC"
assert_contains_ci "missing template error names the path" "template not found" "$ERR_OUT"

# --- Test 10: Unknown profile — non-zero exit + stderr ---

set +e
ERR_OUT="$("$RENDER" "$SK1" --profile "_t777_2_test_no_such_profile" --agent claude 2>&1)"
RC=$?
set -e
assert_nonzero_exit "unknown profile exits non-zero" "$RC"
assert_contains_ci "unknown profile error" "profile" "$ERR_OUT"
assert_contains_ci "unknown profile error names the value" "not found" "$ERR_OUT"

# --- Test 11: Missing --profile arg — non-zero exit + usage ---

set +e
ERR_OUT="$("$RENDER" "$SK1" --agent claude 2>&1)"
RC=$?
set -e
assert_nonzero_exit "missing --profile exits non-zero" "$RC"
assert_contains_ci "missing --profile usage message" "Usage" "$ERR_OUT"

# --- Test 12: Unknown agent — non-zero exit (propagated from agent_skill_root) ---

set +e
ERR_OUT="$("$RENDER" "$SK1" --profile fast --agent _bogus_agent_ 2>&1)"
RC=$?
set -e
assert_nonzero_exit "unknown agent exits non-zero" "$RC"

# --- Test 13: Sanity — _t_mtime helper returns a positive integer ---
# Post-t777_22 the bash-side skip-if-fresh moved to Python (closure-aware), so
# the bash script no longer contains stat calls. The local _t_mtime helper
# (used by other tests in this file) is sanity-checked here.

M13=$(_t_mtime "$TARGET1")
TOTAL=$((TOTAL + 1))
if [[ "$M13" =~ ^[0-9]+$ ]] && (( M13 > 0 )); then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1)); echo "FAIL: _t_mtime did not return positive integer (got '$M13')"
fi

# --- Test 15: realpath without -m — missing .j2 include is skipped, no crash ---

SK_MISSING="${TEST_SKILL_PREFIX}missing_inc"
mkdir -p ".claude/skills/$SK_MISSING"
# Reference an include file that does NOT exist. The recursive-scan resolves
# the path via plain `realpath`, then gates on `[[ -f ... ]]`. The minijinja
# render itself uses {% raw %} to avoid actually trying to inline the file.
cat > ".claude/skills/$SK_MISSING/SKILL.md.j2" <<'EOF'
# Skill with missing include reference
{% raw %}{% include "../_t777_2_test_does_not_exist/SKILL.md.j2" %}{% endraw %}
EOF

set +e
"$RENDER" "$SK_MISSING" --profile fast --agent claude
RC=$?
set -e
TOTAL=$((TOTAL + 1))
if [[ "$RC" -eq 0 ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1)); echo "FAIL: missing-include reference should not crash renderer (rc=$RC)"
fi

# --- Test 18: whitelist touchpoints each have exactly one entry ---

WL_FILES=(
    ".claude/settings.local.json"
    ".codex/rules/default.rules"
    "seed/claude_settings.local.json"
    "seed/codex_rules.default.rules"
    "seed/opencode_config.seed.json"
)
for wlf in "${WL_FILES[@]}"; do
    count=$(grep -c "aitask_skill_render" "$wlf" 2>/dev/null || echo 0)
    # macOS `grep -c` on missing pattern returns "0"; tr-strip just in case.
    count="$(echo "$count" | tr -d ' ')"
    assert_eq "whitelist entry count in $wlf" "1" "$count"
done

# --- Summary ---

echo
echo "PASS: $PASS, FAIL: $FAIL, SKIP: $SKIP, TOTAL: $TOTAL"
[[ $FAIL -eq 0 ]]
