#!/usr/bin/env bash
# test_skill_render_uniform.sh — Integration tests for t777_22:
#   - .aitask-scripts/aitask_skill_render.sh with the t777_22 dep-walker
#   - .aitask-scripts/lib/skill_template.py walk-write / walk-check sub-commands
#
# Synthetic skill fixtures under .claude/skills/_t777_22_test_*/  exercise
# every ref shape (full / sibling / skill_relative), cycle detection,
# identity transform, closure-aware skip-if-fresh, --force, cross-agent
# rewriting, and walk-check error propagation.
#
# Run: bash tests/test_skill_render_uniform.sh

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
    if echo "$actual" | grep -qF -- "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output containing '$expected', got '$actual')"
    fi
}

assert_file_exists() {
    local desc="$1" path="$2"
    TOTAL=$((TOTAL + 1))
    if [[ -f "$path" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1)); echo "FAIL: $desc (file not found: $path)"
    fi
}

assert_file_absent() {
    local desc="$1" path="$2"
    TOTAL=$((TOTAL + 1))
    if [[ ! -e "$path" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1)); echo "FAIL: $desc (file unexpectedly present: $path)"
    fi
}

assert_nonzero_exit() {
    local desc="$1" rc="$2"
    TOTAL=$((TOTAL + 1))
    if [[ "$rc" -ne 0 ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1)); echo "FAIL: $desc (expected non-zero exit, got 0)"
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

RENDER="$PROJECT_DIR/.aitask-scripts/aitask_skill_render.sh"
SKILL_TEMPLATE_PY="$PROJECT_DIR/.aitask-scripts/lib/skill_template.py"
PREFIX="_t777_22_test_"

cleanup() {
    rm -rf \
        "$PROJECT_DIR"/.claude/skills/"${PREFIX}"* \
        "$PROJECT_DIR"/.agents/skills/"${PREFIX}"* \
        "$PROJECT_DIR"/.opencode/skills/"${PREFIX}"*
}
trap cleanup EXIT
cleanup

_t_mtime() { stat -c %Y "$1" 2>/dev/null || stat -f %m "$1"; }

# ============================================================================
# Test 1 — Synthetic single full-path ref: A → B
# ============================================================================

SK_A="${PREFIX}a"
SK_B="${PREFIX}b"
mkdir -p ".claude/skills/$SK_A" ".claude/skills/$SK_B"

cat > ".claude/skills/$SK_A/SKILL.md.j2" <<EOF
# A entry (agent={{ agent }}, profile={{ profile.name }})
See .claude/skills/${SK_B}/SKILL.md for B.
EOF
cat > ".claude/skills/$SK_B/SKILL.md" <<'EOF'
# B leaf (no Jinja markers — identity transform)
EOF

"$RENDER" "$SK_A" --profile fast --agent claude

assert_file_exists "Test1: A target rendered" ".claude/skills/${SK_A}-fast-/SKILL.md"
assert_file_exists "Test1: B target rendered (walked from A)" ".claude/skills/${SK_B}-fast-/SKILL.md"

A_OUT="$(cat ".claude/skills/${SK_A}-fast-/SKILL.md")"
assert_contains "Test1: A's full-path ref rewritten to per-profile dir" \
    ".claude/skills/${SK_B}-fast-/SKILL.md" "$A_OUT"
assert_contains "Test1: A's Jinja markers expanded" "agent=claude, profile=fast" "$A_OUT"

B_OUT="$(cat ".claude/skills/${SK_B}-fast-/SKILL.md")"
B_SRC="$(cat ".claude/skills/${SK_B}/SKILL.md")"
assert_eq "Test1: B identity transform (no Jinja markers)" "$B_SRC" "$B_OUT"

# ============================================================================
# Test 2 — Sibling ref preserved
# ============================================================================

SK_SIB="${PREFIX}sib"
mkdir -p ".claude/skills/$SK_SIB"
cat > ".claude/skills/$SK_SIB/SKILL.md.j2" <<'EOF'
# Sibling entry
See sibling_proc.md for the procedure.
EOF
cat > ".claude/skills/$SK_SIB/sibling_proc.md" <<'EOF'
# Sibling procedure body
EOF

"$RENDER" "$SK_SIB" --profile fast --agent claude

assert_file_exists "Test2: entry target rendered" ".claude/skills/${SK_SIB}-fast-/SKILL.md"
assert_file_exists "Test2: sibling target rendered into same per-profile dir" \
    ".claude/skills/${SK_SIB}-fast-/sibling_proc.md"

ENTRY_OUT="$(cat ".claude/skills/${SK_SIB}-fast-/SKILL.md")"
assert_contains "Test2: sibling ref preserved unchanged" "sibling_proc.md" "$ENTRY_OUT"
TOTAL=$((TOTAL + 1))
if echo "$ENTRY_OUT" | grep -qF '.claude/skills/'; then
    FAIL=$((FAIL + 1)); echo "FAIL: Test2: sibling ref should NOT be rewritten to full path"
else
    PASS=$((PASS + 1))
fi

# ============================================================================
# Test 3 — Skill-relative ref rewritten to full path
# ============================================================================

SK_SR_A="${PREFIX}sra"
SK_SR_B="${PREFIX}srb"
mkdir -p ".claude/skills/$SK_SR_A" ".claude/skills/$SK_SR_B"
cat > ".claude/skills/$SK_SR_A/SKILL.md.j2" <<EOF
# SR-A entry
See ${SK_SR_B}/SKILL.md for B (skill-relative).
EOF
cat > ".claude/skills/$SK_SR_B/SKILL.md" <<'EOF'
# SR-B leaf
EOF

"$RENDER" "$SK_SR_A" --profile fast --agent claude

assert_file_exists "Test3: SR-A target rendered" ".claude/skills/${SK_SR_A}-fast-/SKILL.md"
assert_file_exists "Test3: SR-B target rendered" ".claude/skills/${SK_SR_B}-fast-/SKILL.md"

SR_A_OUT="$(cat ".claude/skills/${SK_SR_A}-fast-/SKILL.md")"
assert_contains "Test3: skill-relative rewritten to full path" \
    ".claude/skills/${SK_SR_B}-fast-/SKILL.md" "$SR_A_OUT"

# ============================================================================
# Test 4 — Identity transform: byte-for-byte equality on Jinja-free source
# ============================================================================

SK_ID_PARENT="${PREFIX}id_parent"
SK_ID_LEAF="${PREFIX}id_leaf"
mkdir -p ".claude/skills/$SK_ID_PARENT" ".claude/skills/$SK_ID_LEAF"
cat > ".claude/skills/$SK_ID_PARENT/SKILL.md.j2" <<EOF
# Parent
ref .claude/skills/${SK_ID_LEAF}/SKILL.md here.
EOF
# Leaf has NO Jinja markers and arbitrary multi-line content.
cat > ".claude/skills/$SK_ID_LEAF/SKILL.md" <<'EOF'
# Identity leaf

This file has no Jinja markers.
- bullet 1
- bullet 2

Final line.
EOF

"$RENDER" "$SK_ID_PARENT" --profile fast --agent claude
diff -q ".claude/skills/$SK_ID_LEAF/SKILL.md" ".claude/skills/${SK_ID_LEAF}-fast-/SKILL.md" >/dev/null
TOTAL=$((TOTAL + 1))
if [[ $? -eq 0 ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1)); echo "FAIL: Test4: identity transform did not preserve bytes"
fi

# ============================================================================
# Test 5 — Cycle detection: A → B → A
# ============================================================================

SK_CY_A="${PREFIX}cyc_a"
SK_CY_B="${PREFIX}cyc_b"
mkdir -p ".claude/skills/$SK_CY_A" ".claude/skills/$SK_CY_B"
cat > ".claude/skills/$SK_CY_A/SKILL.md.j2" <<EOF
# Cycle A
B at .claude/skills/${SK_CY_B}/SKILL.md
EOF
cat > ".claude/skills/$SK_CY_A/SKILL.md" <<EOF
# Cycle A stub
B at .claude/skills/${SK_CY_B}/SKILL.md
EOF
cat > ".claude/skills/$SK_CY_B/SKILL.md" <<EOF
# Cycle B leaf
A at .claude/skills/${SK_CY_A}/SKILL.md
EOF

"$RENDER" "$SK_CY_A" --profile fast --agent claude

assert_file_exists "Test5: cycle A target rendered" ".claude/skills/${SK_CY_A}-fast-/SKILL.md"
assert_file_exists "Test5: cycle B target rendered" ".claude/skills/${SK_CY_B}-fast-/SKILL.md"
CYC_B_OUT="$(cat ".claude/skills/${SK_CY_B}-fast-/SKILL.md")"
assert_contains "Test5: B's back-ref to A rewritten despite cycle" \
    ".claude/skills/${SK_CY_A}-fast-/SKILL.md" "$CYC_B_OUT"

# ============================================================================
# Test 6 — Missing ref silently skipped (no crash, walk continues)
# ============================================================================

SK_MISS="${PREFIX}miss"
mkdir -p ".claude/skills/$SK_MISS"
cat > ".claude/skills/$SK_MISS/SKILL.md.j2" <<EOF
# Has a dangling ref
See .claude/skills/${PREFIX}does_not_exist/SKILL.md for context.
EOF

set +e
"$RENDER" "$SK_MISS" --profile fast --agent claude
RC=$?
set -e
assert_eq "Test6: missing ref does not crash renderer" "0" "$RC"
assert_file_exists "Test6: entry still rendered" ".claude/skills/${SK_MISS}-fast-/SKILL.md"
# Dangling ref text should remain as-is (not rewritten, since it didn't resolve).
MISS_OUT="$(cat ".claude/skills/${SK_MISS}-fast-/SKILL.md")"
assert_contains "Test6: dangling full-path ref preserved verbatim" \
    ".claude/skills/${PREFIX}does_not_exist/SKILL.md" "$MISS_OUT"

# ============================================================================
# Test 7 — Closure-aware skip-if-fresh: second run no-op, leaf touch re-renders
# ============================================================================

# Re-use Test1's A/B tree. First, capture target mtimes.
A_TARGET=".claude/skills/${SK_A}-fast-/SKILL.md"
B_TARGET=".claude/skills/${SK_B}-fast-/SKILL.md"
A_M1=$(_t_mtime "$A_TARGET")
B_M1=$(_t_mtime "$B_TARGET")
sleep 1
"$RENDER" "$SK_A" --profile fast --agent claude
A_M2=$(_t_mtime "$A_TARGET")
B_M2=$(_t_mtime "$B_TARGET")
assert_eq "Test7: skip-if-fresh keeps A target mtime stable" "$A_M1" "$A_M2"
assert_eq "Test7: skip-if-fresh keeps B target mtime stable" "$B_M1" "$B_M2"

# Touch the LEAF source (B) — closure-aware skip should detect staleness.
sleep 1
touch ".claude/skills/$SK_B/SKILL.md"
"$RENDER" "$SK_A" --profile fast --agent claude
A_M3=$(_t_mtime "$A_TARGET")
B_M3=$(_t_mtime "$B_TARGET")
TOTAL=$((TOTAL + 1))
if (( A_M3 > A_M2 )) && (( B_M3 > B_M2 )); then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Test7: leaf touch did not re-render full chain (A: $A_M2→$A_M3, B: $B_M2→$B_M3)"
fi

# ============================================================================
# Test 7b — Staleness via {% from %} import (t777_28)
#
# The dep-walker's `_resolve_template_deps()` must track {% from %} and
# {% import %} directives the same way it tracks {% include %}: touching
# the imported macro file must invalidate the consumer's cached render.
# ============================================================================

SK_FROM="${PREFIX}from_consumer"
mkdir -p ".claude/skills/$SK_FROM"
cat > ".claude/skills/$SK_FROM/_macros.j2" <<'EOF'
{% macro greet(name) -%}
Hello, {{ name }}!
{%- endmacro %}
EOF
cat > ".claude/skills/$SK_FROM/SKILL.md.j2" <<'EOF'
# From-import consumer
{% from "_macros.j2" import greet %}
{{ greet("world") }}
EOF

"$RENDER" "$SK_FROM" --profile fast --agent claude
FROM_TARGET=".claude/skills/${SK_FROM}-fast-/SKILL.md"
assert_file_exists "Test7b: from-import consumer rendered" "$FROM_TARGET"
assert_contains "Test7b: macro expansion present in render" \
    "Hello, world!" "$(cat "$FROM_TARGET")"

FROM_M1=$(_t_mtime "$FROM_TARGET")
sleep 1
# Touch the imported macro file — staleness check must catch it.
touch ".claude/skills/$SK_FROM/_macros.j2"
"$RENDER" "$SK_FROM" --profile fast --agent claude
FROM_M2=$(_t_mtime "$FROM_TARGET")
TOTAL=$((TOTAL + 1))
if (( FROM_M2 > FROM_M1 )); then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Test7b: touching {% from %} macro file did not invalidate consumer (mtime: $FROM_M1→$FROM_M2)"
fi

# ============================================================================
# Test 8 — --force re-renders unconditionally
# ============================================================================

A_M_BEFORE=$(_t_mtime "$A_TARGET")
sleep 1
"$RENDER" "$SK_A" --profile fast --agent claude --force
A_M_AFTER=$(_t_mtime "$A_TARGET")
TOTAL=$((TOTAL + 1))
if (( A_M_AFTER > A_M_BEFORE )); then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1)); echo "FAIL: Test8: --force should re-render"
fi

# ============================================================================
# Test 9 — (retired: gemini cross-agent rewriting; opencode equivalent in Test 8)
# ============================================================================

# ============================================================================
# Test 10 — walk-check: clean closure exits 0, no disk writes
# ============================================================================

SK_WCHK="${PREFIX}wchk"
mkdir -p ".claude/skills/$SK_WCHK"
cat > ".claude/skills/$SK_WCHK/SKILL.md.j2" <<EOF
# walk-check fixture
See .claude/skills/${SK_B}/SKILL.md for B.
EOF
set +e
"$PYTHON" "$SKILL_TEMPLATE_PY" walk-check \
    ".claude/skills/$SK_WCHK/SKILL.md.j2" \
    "aitasks/metadata/profiles/default.yaml" claude "$PROJECT_DIR"
RC=$?
set -e
assert_eq "Test10: walk-check clean closure exits 0" "0" "$RC"
assert_file_absent "Test10: walk-check writes no disk output" \
    ".claude/skills/${SK_WCHK}-default-/SKILL.md"

# ============================================================================
# Test 11 — walk-check: broken Jinja in a leaf surfaces as non-zero
# ============================================================================

SK_BAD_P="${PREFIX}bad_parent"
SK_BAD_L="${PREFIX}bad_leaf"
mkdir -p ".claude/skills/$SK_BAD_P" ".claude/skills/$SK_BAD_L"
cat > ".claude/skills/$SK_BAD_P/SKILL.md.j2" <<EOF
# Bad parent
ref .claude/skills/${SK_BAD_L}/SKILL.md
EOF
cat > ".claude/skills/$SK_BAD_L/SKILL.md" <<'EOF'
# Bad leaf with malformed Jinja:
{% if missing_endif %}
oops
EOF

set +e
"$PYTHON" "$SKILL_TEMPLATE_PY" walk-check \
    ".claude/skills/$SK_BAD_P/SKILL.md.j2" \
    "aitasks/metadata/profiles/default.yaml" claude "$PROJECT_DIR" 2>/dev/null
RC=$?
set -e
assert_nonzero_exit "Test11: walk-check surfaces bad-Jinja leaf as non-zero" "$RC"

# ============================================================================
# Test 12 — Procedure file mentions the skill's own SKILL.md in prose:
#   the stub must NOT overwrite the rendered entry-point (t817).
# ============================================================================

SK_STUBREF="${PREFIX}stubref"
mkdir -p ".claude/skills/$SK_STUBREF"
# Templated entry: distinguishing rendered content + a Jinja marker.
cat > ".claude/skills/$SK_STUBREF/SKILL.md.j2" <<'EOF'
# Stubref RENDERED ENTRY (agent={{ agent }})
See proc_step.md for the procedure.
EOF
# Stub SKILL.md dispatch surface — must never leak into the entry target.
cat > ".claude/skills/$SK_STUBREF/SKILL.md" <<'EOF'
# Stubref STUB SURFACE — must not overwrite the rendered entry
EOF
# Procedure file mentions the skill's own SKILL.md in prose.
cat > ".claude/skills/$SK_STUBREF/proc_step.md" <<'EOF'
# Procedure step
Referenced from Step 3 of the main SKILL.md workflow.
EOF

set +e
"$RENDER" "$SK_STUBREF" --profile fast --agent claude
RC=$?
set -e
assert_eq "Test12: stub-ref render exits 0" "0" "$RC"
assert_file_exists "Test12: entry target rendered" \
    ".claude/skills/${SK_STUBREF}-fast-/SKILL.md"
assert_file_exists "Test12: procedure file rendered" \
    ".claude/skills/${SK_STUBREF}-fast-/proc_step.md"

STUBREF_OUT="$(cat ".claude/skills/${SK_STUBREF}-fast-/SKILL.md")"
assert_contains "Test12: entry target keeps rendered template content" \
    "RENDERED ENTRY (agent=claude)" "$STUBREF_OUT"
TOTAL=$((TOTAL + 1))
if echo "$STUBREF_OUT" | grep -qF 'STUB SURFACE'; then
    FAIL=$((FAIL + 1))
    echo "FAIL: Test12: stub content leaked into rendered entry-point"
else
    PASS=$((PASS + 1))
fi

# ============================================================================
# Summary
# ============================================================================

echo
echo "PASS: $PASS, FAIL: $FAIL, TOTAL: $TOTAL"
[[ $FAIL -eq 0 ]]
