#!/usr/bin/env bash
# test_skill_render.sh - Automated tests for t777_2:
#   - .aitask-scripts/aitask_skill_render.sh (per-profile renderer + dispatch)
#   - ./ait skill subcommand
#   - 5-touchpoint whitelist for aitask_skill_render.sh
# Run: bash tests/test_skill_render.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
SKIP=0
TOTAL=0

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if [[ "$expected" == "$actual" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected '$expected', got '$actual')"
    fi
}

assert_contains() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qi -- "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output containing '$expected', got '$actual')"
    fi
}

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
           "$PROJECT_DIR"/.gemini/skills/"${TEST_SKILL_PREFIX}"* \
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

TARGET1=".claude/skills/${SK1}-fast/SKILL.md"
TOTAL=$((TOTAL + 1))
if [[ -f "$TARGET1" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1)); echo "FAIL: basic render did not produce $TARGET1"
fi
RENDERED1="$(cat "$TARGET1" 2>/dev/null || echo "")"
assert_contains "basic render: profile.name substituted"            "Smoke (fast/claude)"           "$RENDERED1"
assert_contains "basic render: skip_task_confirmation substituted"  "skip_task_confirmation: true"  "$RENDERED1"

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
TARGET1_SCRATCH=".claude/skills/${SK1}-${SCRATCH_PROFILE_NAME}/SKILL.md"
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

# --- Test 6: Cross-skill include recursion ---

SK_A="${TEST_SKILL_PREFIX}rec_a"
SK_B="${TEST_SKILL_PREFIX}rec_b"
mkdir -p ".claude/skills/$SK_A" ".claude/skills/$SK_B"
cat > ".claude/skills/$SK_A/SKILL.md.j2" <<'EOF'
# A skill (agent={{ agent }})
EOF
cat > ".claude/skills/$SK_B/SKILL.md.j2" <<EOF
# B skill includes A
{% include "$SK_A/SKILL.md.j2" %}
EOF

"$RENDER" "$SK_B" --profile fast --agent claude

TARGET_A=".claude/skills/${SK_A}-fast/SKILL.md"
TARGET_B=".claude/skills/${SK_B}-fast/SKILL.md"
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
    FAIL=$((FAIL + 1)); echo "FAIL: cross-skill recursion did not render A: $TARGET_A"
fi

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

TARGET_S=".claude/skills/${SK_S}-fast/SKILL.md"
RENDERED_S="$(cat "$TARGET_S" 2>/dev/null || echo "")"
assert_contains "same-skill include inlined into parent output" "PARTIAL_CONTENT" "$RENDERED_S"
# No spurious "_partial" skill dir should be created.
TOTAL=$((TOTAL + 1))
if [[ ! -d ".claude/skills/_partial-fast" && ! -d ".claude/skills/_partial" ]]; then
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
TARGET_MD=".claude/skills/${SK_MD}-fast/SKILL.md"
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
assert_contains "missing template error names the path" "template not found" "$ERR_OUT"

# --- Test 10: Unknown profile — non-zero exit + stderr ---

set +e
ERR_OUT="$("$RENDER" "$SK1" --profile "_t777_2_test_no_such_profile" --agent claude 2>&1)"
RC=$?
set -e
assert_nonzero_exit "unknown profile exits non-zero" "$RC"
assert_contains "unknown profile error" "profile" "$ERR_OUT"
assert_contains "unknown profile error names the value" "not found" "$ERR_OUT"

# --- Test 11: Missing --profile arg — non-zero exit + usage ---

set +e
ERR_OUT="$("$RENDER" "$SK1" --agent claude 2>&1)"
RC=$?
set -e
assert_nonzero_exit "missing --profile exits non-zero" "$RC"
assert_contains "missing --profile usage message" "Usage" "$ERR_OUT"

# --- Test 12: Unknown agent — non-zero exit (propagated from agent_skill_root) ---

set +e
ERR_OUT="$("$RENDER" "$SK1" --profile fast --agent _bogus_agent_ 2>&1)"
RC=$?
set -e
assert_nonzero_exit "unknown agent exits non-zero" "$RC"

# --- Test 13: Portability — Linux branch (stat -c %Y) active in current run ---

# With PATH unmodified on a Linux host, basic render must succeed; this
# implicitly exercises the stat -c %Y branch via skip-if-fresh. We sanity-
# check that _t_mtime returns a positive integer (proves stat invocation).
M13=$(_t_mtime "$TARGET1")
TOTAL=$((TOTAL + 1))
if [[ "$M13" =~ ^[0-9]+$ ]] && (( M13 > 0 )); then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1)); echo "FAIL: _t_mtime did not return positive integer (got '$M13')"
fi

# --- Test 14: Portability — BSD branch (stat -f %m) is present in the script ---
#
# We cannot reliably *simulate* the BSD `stat -f %m` branch on a Linux host:
# GNU and BSD `stat -f` have incompatible semantics (GNU treats -f as
# filesystem-info mode; BSD treats it as a file format selector). A PATH
# shim can intercept the -c branch but cannot convert the GNU semantic of
# -f into the BSD semantic. So we verify portability statically:
#   1) The script contains both code paths (`stat -c %Y` and `stat -f %m`).
#   2) The current-host branch (test 13 above) actually works end-to-end.
# On a real macOS host, the BSD branch will exercise via the same end-to-end
# tests (1-12, 15-17) because BSD stat rejects -c, triggering the || fallback.

SCRIPT_BODY="$(cat "$RENDER")"
assert_contains "script contains GNU/Linux mtime branch (stat -c %Y)" 'stat -c %Y' "$SCRIPT_BODY"
assert_contains "script contains BSD/macOS mtime branch (stat -f %m)" 'stat -f %m' "$SCRIPT_BODY"

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

# --- Test 16: ait skill --help lists 'render' ---

HELP_OUT="$(./ait skill --help 2>&1)"
assert_contains "ait skill --help lists 'render' subcommand" "render" "$HELP_OUT"

# --- Test 17: ait skill bogus exits 1 with 'unknown subcommand' ---

set +e
BOGUS_OUT="$(./ait skill bogus 2>&1)"
RC=$?
set -e
assert_nonzero_exit "ait skill bogus exits non-zero" "$RC"
assert_contains "ait skill bogus error message" "unknown subcommand" "$BOGUS_OUT"

# --- Test 18: 5 whitelist touchpoints each have exactly one entry ---

WL_FILES=(
    ".claude/settings.local.json"
    ".gemini/policies/aitasks-whitelist.toml"
    "seed/claude_settings.local.json"
    "seed/geminicli_policies/aitasks-whitelist.toml"
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
