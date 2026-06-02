#!/usr/bin/env bash
# test_skill_verify.sh - Automated tests for t777_4:
#   - .aitask-scripts/aitask_skill_verify.sh
#   - helper whitelist touchpoints for aitask_skill_verify.sh
# Run: bash tests/test_skill_verify.sh

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
        echo "FAIL: $desc (expected output containing '$expected', got first 200 chars: '${actual:0:200}')"
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

assert_zero_exit() {
    local desc="$1" rc="$2"
    TOTAL=$((TOTAL + 1))
    if [[ "$rc" -eq 0 ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected zero exit, got $rc)"
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

VERIFY="$PROJECT_DIR/.aitask-scripts/aitask_skill_verify.sh"

# --- Scratch workspace ---

TEST_SKILL_PREFIX="_t777_4_test_"

cleanup() {
    # Scratch skill authoring dirs + stub-surface command files under tracked agent roots.
    # shellcheck disable=SC2115
    rm -rf "$PROJECT_DIR"/.claude/skills/"${TEST_SKILL_PREFIX}"* \
           "$PROJECT_DIR"/.agents/skills/"${TEST_SKILL_PREFIX}"* \
           "$PROJECT_DIR"/.opencode/skills/"${TEST_SKILL_PREFIX}"*
    rm -f "$PROJECT_DIR"/.opencode/commands/"${TEST_SKILL_PREFIX}"*.md
}
trap cleanup EXIT
# Pre-clean in case a prior aborted run left scratch dirs / files.
cleanup
# Also wipe any scratch leftovers from t777_2's test_skill_render.sh — they would
# otherwise be auto-discovered by Claude AND counted as .j2 templates by Test 1.
# shellcheck disable=SC2115
rm -rf "$PROJECT_DIR"/.claude/skills/_t777_2_test_* \
       "$PROJECT_DIR"/.agents/skills/_t777_2_test_* \
       "$PROJECT_DIR"/.opencode/skills/_t777_2_test_*

# Helper: write the canonical 4 stub surfaces for a given skill name.
# Caller can override individual stub bodies by writing them AFTER calling this.
_write_canonical_stubs() {
    local skill="$1"

    mkdir -p ".claude/skills/$skill" ".agents/skills/$skill"
    cat > ".claude/skills/$skill/SKILL.md" <<EOF
---
name: $skill
description: stub for test
---
1. ./.aitask-scripts/aitask_skill_resolve_profile.sh $skill
2. ./.aitask-scripts/aitask_skill_render.sh $skill --profile <profile> --agent claude
3. Read .claude/skills/$skill-<profile>-/SKILL.md
EOF
    cat > ".agents/skills/$skill/SKILL.md" <<EOF
---
name: $skill
description: stub for test
---
1. ./.aitask-scripts/aitask_skill_resolve_profile.sh $skill
2. ./.aitask-scripts/aitask_skill_render.sh $skill --profile <profile> --agent codex
3. Read .agents/skills/$skill-<profile>-codex-/SKILL.md
EOF
    mkdir -p ".opencode/commands"
    cat > ".opencode/commands/$skill.md" <<EOF
---
description: stub for test
---
1. ./.aitask-scripts/aitask_skill_resolve_profile.sh $skill
2. ./.aitask-scripts/aitask_skill_render.sh $skill --profile <profile> --agent opencode
3. Read .opencode/skills/$skill-<profile>-/SKILL.md
EOF
}

# Helper: write a well-formed .j2 referencing only fields that exist in default.yaml.
# default.yaml has just `name:` and `description:` — keep templates minimal.
_write_clean_j2() {
    local skill="$1"
    mkdir -p ".claude/skills/$skill"
    cat > ".claude/skills/$skill/SKILL.md.j2" <<'EOF'
# Smoke template for {{ profile.name }} ({{ agent }})
EOF
}

# --- Test 1: baseline repository templates verify cleanly ---

set +e
OUT="$("$VERIFY" 2>&1)"
RC=$?
set -e
assert_zero_exit "test 1: baseline templates → exit 0" "$RC"
assert_contains "test 1: stdout reports verifier OK" "aitask_skill_verify.sh: OK" "$OUT"

# --- Test 2: broken .j2 (strict-undefined) → exit non-zero, stderr contains VERIFY_FAIL ---

SK_BROKEN="${TEST_SKILL_PREFIX}broken"
mkdir -p ".claude/skills/$SK_BROKEN"
cat > ".claude/skills/$SK_BROKEN/SKILL.md.j2" <<'EOF'
{{ profile.this_field_does_not_exist_anywhere }}
EOF
# Give it canonical stubs so STUB_FAIL noise doesn't drown VERIFY_FAIL.
_write_canonical_stubs "$SK_BROKEN"

set +e
OUT="$("$VERIFY" 2>&1)"
RC=$?
set -e
assert_nonzero_exit "test 2: broken .j2 → exit non-zero" "$RC"
assert_contains "test 2: stderr contains VERIFY_FAIL" "VERIFY_FAIL" "$OUT"
assert_contains "test 2: failure names the broken skill" "$SK_BROKEN" "$OUT"

# Clean up scratch from test 2 before the next case.
cleanup
mkdir -p ".claude/skills" ".agents/skills" ".opencode/commands"

# --- Test 3: well-formed .j2 with no stubs → exit non-zero, 4 STUB_FAILs ---

SK_NOSTUB="${TEST_SKILL_PREFIX}nostub"
_write_clean_j2 "$SK_NOSTUB"

set +e
OUT="$("$VERIFY" 2>&1)"
RC=$?
set -e
assert_nonzero_exit "test 3: no stubs → exit non-zero" "$RC"
assert_contains "test 3: missing claude stub" ".claude/skills/$SK_NOSTUB/SKILL.md: missing stub for claude" "$OUT"
assert_contains "test 3: missing codex stub"  ".agents/skills/$SK_NOSTUB/SKILL.md: missing stub for codex" "$OUT"
assert_contains "test 3: missing opencode stub" ".opencode/commands/$SK_NOSTUB.md: missing stub for opencode" "$OUT"

cleanup
mkdir -p ".claude/skills" ".agents/skills" ".opencode/commands"

# --- Test 4: well-formed .j2 + valid stubs in all 4 surfaces → exit 0 ---

SK_GOOD="${TEST_SKILL_PREFIX}good"
_write_clean_j2 "$SK_GOOD"
_write_canonical_stubs "$SK_GOOD"

set +e
OUT="$("$VERIFY" 2>&1)"
RC=$?
set -e
assert_zero_exit "test 4: happy path → exit 0" "$RC"
assert_contains "test 4: stdout reports 'OK'" "aitask_skill_verify.sh: OK" "$OUT"

cleanup
mkdir -p ".claude/skills" ".agents/skills" ".opencode/commands"

# --- Test 5: stub missing resolver call → STUB_FAIL: missing resolver call ---

SK_NORES="${TEST_SKILL_PREFIX}nores"
_write_clean_j2 "$SK_NORES"
_write_canonical_stubs "$SK_NORES"
# Strip the resolver call from the Claude stub.
cat > ".claude/skills/$SK_NORES/SKILL.md" <<EOF
---
name: $SK_NORES
description: stub for test (no resolver)
---
2. ./.aitask-scripts/aitask_skill_render.sh $SK_NORES --profile <profile> --agent claude
3. Read .claude/skills/$SK_NORES-<profile>-/SKILL.md
EOF

set +e
OUT="$("$VERIFY" 2>&1)"
RC=$?
set -e
assert_nonzero_exit "test 5: missing resolver call → exit non-zero" "$RC"
assert_contains "test 5: STUB_FAIL names missing resolver call" "missing resolver call" "$OUT"

cleanup
mkdir -p ".claude/skills" ".agents/skills" ".opencode/commands"

# --- Test 6: stub missing render call → STUB_FAIL: missing render call ---

SK_NOREN="${TEST_SKILL_PREFIX}noren"
_write_clean_j2 "$SK_NOREN"
_write_canonical_stubs "$SK_NOREN"
cat > ".claude/skills/$SK_NOREN/SKILL.md" <<EOF
---
name: $SK_NOREN
description: stub for test (no render)
---
1. ./.aitask-scripts/aitask_skill_resolve_profile.sh $SK_NOREN
3. Read .claude/skills/$SK_NOREN-<profile>-/SKILL.md
EOF

set +e
OUT="$("$VERIFY" 2>&1)"
RC=$?
set -e
assert_nonzero_exit "test 6: missing render call → exit non-zero" "$RC"
assert_contains "test 6: STUB_FAIL names missing render call" "missing render call" "$OUT"

cleanup
mkdir -p ".claude/skills" ".agents/skills" ".opencode/commands"

# --- Test 7: stub missing trailing-hyphen Read path → STUB_FAIL: missing trailing-hyphen Read path ---

SK_NOREAD="${TEST_SKILL_PREFIX}noread"
_write_clean_j2 "$SK_NOREAD"
_write_canonical_stubs "$SK_NOREAD"
cat > ".claude/skills/$SK_NOREAD/SKILL.md" <<EOF
---
name: $SK_NOREAD
description: stub for test (no trailing-hyphen Read path)
---
1. ./.aitask-scripts/aitask_skill_resolve_profile.sh $SK_NOREAD
2. ./.aitask-scripts/aitask_skill_render.sh $SK_NOREAD --profile <profile> --agent claude
3. Read .claude/skills/$SK_NOREAD/SKILL.md
EOF

set +e
OUT="$("$VERIFY" 2>&1)"
RC=$?
set -e
assert_nonzero_exit "test 7: missing Read path → exit non-zero" "$RC"
assert_contains "test 7: STUB_FAIL names missing trailing-hyphen Read path" "missing trailing-hyphen Read path" "$OUT"

cleanup
mkdir -p ".claude/skills" ".agents/skills" ".opencode/commands"

# --- Test 8 (t894): prerender_for_headless skill with no committed prerender
#     → PRERENDER_FAIL. Exercises the generalized headless-prerender check:
#     the `headless: true` profile (real `remote`) × the `prerender_for_headless`
#     j2-frontmatter marker discover a (skill, profile, agent) triple whose
#     committed prerender is absent. ---

SK_PRERENDER="${TEST_SKILL_PREFIX}prerender"
mkdir -p ".claude/skills/$SK_PRERENDER"
cat > ".claude/skills/$SK_PRERENDER/SKILL.md.j2" <<'EOF'
---
name: scratch-prerender
description: scratch headless prerender skill for t894 test
prerender_for_headless: true
---
# Smoke template for {{ profile.name }} ({{ agent }})
EOF
# Canonical stubs so STUB_FAIL noise doesn't drown the PRERENDER_FAIL we assert.
_write_canonical_stubs "$SK_PRERENDER"

set +e
OUT="$("$VERIFY" 2>&1)"
RC=$?
set -e
assert_nonzero_exit "test 8: prerender marker + missing committed prerender → exit non-zero" "$RC"
assert_contains "test 8: PRERENDER_FAIL names the scratch skill" "PRERENDER_FAIL: .claude/skills/$SK_PRERENDER-remote-" "$OUT"

cleanup
mkdir -p ".claude/skills" ".agents/skills" ".opencode/commands"

# --- Test 10: helper whitelist touchpoints — exactly one entry per file ---

declare -a WHITELIST_FILES=(
    ".claude/settings.local.json"
    ".codex/rules/default.rules"
    "seed/claude_settings.local.json"
    "seed/codex_rules.default.rules"
    "seed/opencode_config.seed.json"
)
for f in "${WHITELIST_FILES[@]}"; do
    count=$(grep -c "aitask_skill_verify" "$f" 2>/dev/null || echo 0)
    assert_eq "test 10: $f has exactly 1 aitask_skill_verify entry" "1" "$count"
done

# --- Summary ---

echo
echo "PASS: $PASS, FAIL: $FAIL, TOTAL: $TOTAL"
[[ $FAIL -eq 0 ]]
