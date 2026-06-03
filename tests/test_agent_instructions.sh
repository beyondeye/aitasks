#!/usr/bin/env bash
# test_agent_instructions.sh - Tests for unified agent instruction management (t130_2)
# Tests: assemble_aitasks_instructions(), insert_aitasks_instructions(),
#        update_claudemd_git_section(), update_agentsmd(), setup_codex_cli()
# Run: bash tests/test_agent_instructions.sh

set -e

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_DIR/.." && pwd)"
SCRIPT_DIR="$PROJECT_DIR/.aitask-scripts"

# Source setup script in source-only mode to get function definitions
source "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" --source-only

PASS=0
FAIL=0
TOTAL=0
TMPDIR_TEST=""

# --- Test helpers ---
# Shared core helpers (assert_eq, assert_contains, assert_not_contains) live in
# tests/lib/asserts.sh. assert_file_contains is single-use and stays inline.
. "$PROJECT_DIR/tests/lib/asserts.sh"

assert_file_contains() {
    local desc="$1" expected="$2" file="$3"
    TOTAL=$((TOTAL + 1))
    if [[ -f "$file" ]] && grep -qF -- "$expected" "$file"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (file should contain '$expected')"
        if [[ -f "$file" ]]; then
            echo "  file contents: $(head -5 "$file")"
        else
            echo "  file does not exist: $file"
        fi
    fi
}

setup_tmpdir() {
    TMPDIR_TEST=$(mktemp -d)
    # Create mock project structure with seed files
    mkdir -p "$TMPDIR_TEST/aitasks/metadata"
    cat > "$TMPDIR_TEST/aitasks/metadata/aitasks_agent_instructions.seed.md" <<'EOF'
# aitasks Framework — Agent Instructions

This project uses the aitasks framework.

## Git Operations on Task/Plan Files

Use `./ait git` instead of plain `git`.
EOF

    cat > "$TMPDIR_TEST/aitasks/metadata/codex_instructions.seed.md" <<'EOF'
# aitasks Framework — Codex CLI Instructions

For shared conventions, see shared seed file.

## Skills

Invoke skills with `$skill-name` syntax.

## Agent Identification

Identify as `codex/<model_name>`.
EOF
}

cleanup_tmpdir() {
    if [[ -n "$TMPDIR_TEST" && -d "$TMPDIR_TEST" ]]; then
        rm -rf "$TMPDIR_TEST"
    fi
}

trap cleanup_tmpdir EXIT

echo "=== Agent Instruction Management Tests (t130_2) ==="
echo ""

# ============================================================
# Tests for insert_aitasks_instructions()
# ============================================================

echo "--- insert_aitasks_instructions() ---"

# Test 1: Fresh file (no file exists)
setup_tmpdir
target="$TMPDIR_TEST/new_file.md"
insert_aitasks_instructions "$target" "test content here"
result="$(cat "$target")"
assert_contains "T1: fresh file has start marker" ">>>aitasks" "$result"
assert_contains "T1: fresh file has end marker" "<<<aitasks" "$result"
assert_contains "T1: fresh file has content" "test content here" "$result"
cleanup_tmpdir

# Test 2: Existing file without markers — appends
setup_tmpdir
target="$TMPDIR_TEST/existing.md"
echo "# Existing Project Docs" > "$target"
echo "Some existing content." >> "$target"
insert_aitasks_instructions "$target" "new aitask content"
result="$(cat "$target")"
assert_contains "T2: preserves existing content" "# Existing Project Docs" "$result"
assert_contains "T2: preserves existing body" "Some existing content." "$result"
assert_contains "T2: appended start marker" ">>>aitasks" "$result"
assert_contains "T2: appended content" "new aitask content" "$result"
assert_contains "T2: appended end marker" "<<<aitasks" "$result"
cleanup_tmpdir

# Test 3: Existing file with markers — replaces content between markers
setup_tmpdir
target="$TMPDIR_TEST/with_markers.md"
cat > "$target" <<'EOF'
# My Project
Some intro.

>>>aitasks
old aitask content
<<<aitasks

# Footer
More stuff.
EOF
insert_aitasks_instructions "$target" "updated aitask content"
result="$(cat "$target")"
assert_contains "T3: preserves content before markers" "# My Project" "$result"
assert_contains "T3: preserves content after markers" "# Footer" "$result"
assert_contains "T3: has updated content" "updated aitask content" "$result"
assert_not_contains "T3: old content removed" "old aitask content" "$result"
cleanup_tmpdir

# Test 4: Markers with surrounding content preserved exactly
setup_tmpdir
target="$TMPDIR_TEST/surrounded.md"
cat > "$target" <<'EOF'
Line before 1
Line before 2
>>>aitasks
original
<<<aitasks
Line after 1
Line after 2
EOF
insert_aitasks_instructions "$target" "replaced"
result="$(cat "$target")"
assert_contains "T4: line before 1 preserved" "Line before 1" "$result"
assert_contains "T4: line before 2 preserved" "Line before 2" "$result"
assert_contains "T4: line after 1 preserved" "Line after 1" "$result"
assert_contains "T4: line after 2 preserved" "Line after 2" "$result"
assert_contains "T4: new content present" "replaced" "$result"
cleanup_tmpdir

# Test 5: Idempotent — same content twice = same result
setup_tmpdir
target="$TMPDIR_TEST/idempotent.md"
echo "# Header" > "$target"
insert_aitasks_instructions "$target" "stable content"
first_result="$(cat "$target")"
insert_aitasks_instructions "$target" "stable content"
second_result="$(cat "$target")"
assert_eq "T5: idempotent insertion" "$first_result" "$second_result"
cleanup_tmpdir

# ============================================================
# Tests for assemble_aitasks_instructions()
# ============================================================

echo "--- assemble_aitasks_instructions() ---"

# Test 6: Shared + optional agent layer (Claude case, no Layer 2 file)
setup_tmpdir
result="$(assemble_aitasks_instructions "$TMPDIR_TEST" "claude")"
assert_contains "T6: includes shared content" "## Git Operations on Task/Plan Files" "$result"
assert_contains "T6: includes shared body" "Use \`./ait git\` instead of plain \`git\`." "$result"
assert_not_contains "T6: no codex content" "Invoke skills with" "$result"
cleanup_tmpdir

# Test 7: Shared + agent-specific (Codex case)
setup_tmpdir
result="$(assemble_aitasks_instructions "$TMPDIR_TEST" "codex")"
assert_contains "T7: includes shared content" "## Git Operations on Task/Plan Files" "$result"
assert_contains "T7: includes codex Skills section" "## Skills" "$result"
assert_contains "T7: includes codex content" "Invoke skills with" "$result"
assert_contains "T7: includes Agent Identification" "## Agent Identification" "$result"
# Should NOT include the Layer 2 header/preamble lines
assert_not_contains "T7: Layer 2 header stripped" "# aitasks Framework — Codex CLI Instructions" "$result"
assert_not_contains "T7: Layer 2 preamble stripped" "For shared conventions" "$result"
cleanup_tmpdir

# Test 8: Missing shared seed — returns error
setup_tmpdir
rm "$TMPDIR_TEST/aitasks/metadata/aitasks_agent_instructions.seed.md"
result="$(assemble_aitasks_instructions "$TMPDIR_TEST" 2>&1)" && exit_code=0 || exit_code=$?
assert_eq "T8: missing shared seed returns error" "1" "$exit_code"
cleanup_tmpdir

# Test 9: Missing agent-specific seed — outputs Layer 1 only (no error)
setup_tmpdir
rm "$TMPDIR_TEST/aitasks/metadata/codex_instructions.seed.md"
result="$(assemble_aitasks_instructions "$TMPDIR_TEST" "codex")" && exit_code=0 || exit_code=$?
assert_eq "T9: missing agent seed no error" "0" "$exit_code"
assert_contains "T9: shared content present" "## Git Operations" "$result"
cleanup_tmpdir

# Test 9b: metadata seed absent but seed/ copy present — falls back, no error.
# Regression for the silent `set -e` abort in `ait setup`: a legacy install with
# no aitasks/metadata/ copy must fall back to seed/ instead of returning 1 (which
# the warn-swallowing `$(...)` callers would turn into a silent setup crash).
setup_tmpdir
mkdir -p "$TMPDIR_TEST/seed"
mv "$TMPDIR_TEST/aitasks/metadata/aitasks_agent_instructions.seed.md" \
   "$TMPDIR_TEST/seed/aitasks_agent_instructions.seed.md"
result="$(assemble_aitasks_instructions "$TMPDIR_TEST" 2>&1)" && exit_code=0 || exit_code=$?
assert_eq "T9b: seed/ fallback no error" "0" "$exit_code"
assert_contains "T9b: fallback content present" "## Git Operations" "$result"
cleanup_tmpdir

# Test 9c: agent-specific Layer 2 also falls back to seed/
setup_tmpdir
mkdir -p "$TMPDIR_TEST/seed"
mv "$TMPDIR_TEST/aitasks/metadata/codex_instructions.seed.md" \
   "$TMPDIR_TEST/seed/codex_instructions.seed.md"
result="$(assemble_aitasks_instructions "$TMPDIR_TEST" "codex")" && exit_code=0 || exit_code=$?
assert_eq "T9c: agent seed/ fallback no error" "0" "$exit_code"
assert_contains "T9c: Layer 1 present" "## Git Operations" "$result"
assert_contains "T9c: Layer 2 fallback present" "Invoke skills with" "$result"
cleanup_tmpdir

# ============================================================
# Tests for update_claudemd_git_section() (refactored)
# ============================================================

echo "--- update_claudemd_git_section() ---"

# Test 10: Fresh CLAUDE.md
setup_tmpdir
update_claudemd_git_section "$TMPDIR_TEST"
result="$(cat "$TMPDIR_TEST/CLAUDE.md")"
assert_contains "T10: fresh CLAUDE.md has markers" ">>>aitasks" "$result"
assert_contains "T10: has shared content" "## Git Operations" "$result"
assert_contains "T10: has end marker" "<<<aitasks" "$result"
cleanup_tmpdir

# Test 11: Existing CLAUDE.md without markers
setup_tmpdir
cat > "$TMPDIR_TEST/CLAUDE.md" <<'EOF'
# My Project

This is a project readme.
EOF
update_claudemd_git_section "$TMPDIR_TEST"
result="$(cat "$TMPDIR_TEST/CLAUDE.md")"
assert_contains "T11: original content preserved" "# My Project" "$result"
assert_contains "T11: markers appended" ">>>aitasks" "$result"
assert_contains "T11: shared content appended" "## Git Operations" "$result"
cleanup_tmpdir

# Test 12: Existing CLAUDE.md with old markers — update
setup_tmpdir
cat > "$TMPDIR_TEST/CLAUDE.md" <<'EOF'
# My Project

>>>aitasks
OLD INSTRUCTIONS HERE
<<<aitasks

# Other Section
EOF
update_claudemd_git_section "$TMPDIR_TEST"
result="$(cat "$TMPDIR_TEST/CLAUDE.md")"
assert_contains "T12: original header preserved" "# My Project" "$result"
assert_contains "T12: other section preserved" "# Other Section" "$result"
assert_not_contains "T12: old content replaced" "OLD INSTRUCTIONS HERE" "$result"
assert_contains "T12: new content present" "## Git Operations" "$result"
cleanup_tmpdir

# ============================================================
# Tests for setup_codex_cli() (integration-level)
# ============================================================

echo "--- setup_codex_cli() (integration) ---"

# Helper to create mock staging
create_codex_staging() {
    local dir="$1"
    mkdir -p "$dir/aitasks/metadata/codex_skills/aitask-pick"
    echo "# Pick skill" > "$dir/aitasks/metadata/codex_skills/aitask-pick/SKILL.md"
    mkdir -p "$dir/aitasks/metadata/codex_skills/aitask-create"
    echo "# Create skill" > "$dir/aitasks/metadata/codex_skills/aitask-create/SKILL.md"
    echo "# Tool mapping" > "$dir/aitasks/metadata/codex_skills/codex_tool_mapping.md"
    # Create a minimal seed config
    cat > "$dir/aitasks/metadata/codex_config.seed.toml" <<'TOML'
sandbox_mode = "workspace-write"

[features]
default_mode_request_user_input = true
TOML
    cat > "$dir/aitasks/metadata/codex_rules.default.rules" <<'RULES'
prefix_rule(pattern = ["./.aitask-scripts/aitask_skill_render.sh"], decision = "allow", justification = "Aitasks helper script")
prefix_rule(pattern = ["./.aitask-scripts/aitask_skill_resolve_profile.sh"], decision = "allow", justification = "Aitasks helper script")
RULES
}

# Test 13: Fresh install (no existing .codex/)
setup_tmpdir
create_codex_staging "$TMPDIR_TEST"
# Override SCRIPT_DIR for setup_codex_cli
(
    SCRIPT_DIR="$TMPDIR_TEST/.aitask-scripts"
    mkdir -p "$SCRIPT_DIR"
    # Non-interactive mode (stdin not a terminal)
    setup_codex_cli < /dev/null
)
assert_file_contains "T13: instructions.md created with markers" ">>>aitasks" "$TMPDIR_TEST/.codex/instructions.md"
assert_file_contains "T13: instructions.md has shared content" "## Git Operations" "$TMPDIR_TEST/.codex/instructions.md"
assert_file_contains "T13: instructions.md has codex content" "## Skills" "$TMPDIR_TEST/.codex/instructions.md"
assert_file_contains "T13: config.toml created" "sandbox_mode" "$TMPDIR_TEST/.codex/config.toml"
assert_file_contains "T13: config.toml has features table" "[features]" "$TMPDIR_TEST/.codex/config.toml"
assert_file_contains "T13: config.toml enables request_user_input" "default_mode_request_user_input = true" "$TMPDIR_TEST/.codex/config.toml"
assert_file_contains "T13: rules created" "aitask_skill_render.sh" "$TMPDIR_TEST/.codex/rules/default.rules"
assert_file_contains "T13: skill wrapper installed" "# Pick skill" "$TMPDIR_TEST/.agents/skills/aitask-pick/SKILL.md"
assert_file_contains "T13: tool mapping installed" "# Tool mapping" "$TMPDIR_TEST/.agents/skills/codex_tool_mapping.md"
cleanup_tmpdir

# Test 14: Existing instructions.md without markers — appends
setup_tmpdir
create_codex_staging "$TMPDIR_TEST"
mkdir -p "$TMPDIR_TEST/.codex"
echo "# Custom Codex Instructions" > "$TMPDIR_TEST/.codex/instructions.md"
echo "My custom content." >> "$TMPDIR_TEST/.codex/instructions.md"
(
    SCRIPT_DIR="$TMPDIR_TEST/.aitask-scripts"
    mkdir -p "$SCRIPT_DIR"
    setup_codex_cli < /dev/null
)
result="$(cat "$TMPDIR_TEST/.codex/instructions.md")"
assert_contains "T14: custom content preserved" "# Custom Codex Instructions" "$result"
assert_contains "T14: custom body preserved" "My custom content." "$result"
assert_contains "T14: markers appended" ">>>aitasks" "$result"
assert_contains "T14: aitask content appended" "## Git Operations" "$result"
cleanup_tmpdir

# Test 15: Re-run install (markers already present) — updates, doesn't duplicate
setup_tmpdir
create_codex_staging "$TMPDIR_TEST"
mkdir -p "$TMPDIR_TEST/.codex"
cat > "$TMPDIR_TEST/.codex/instructions.md" <<'EOF'
# Custom Header

>>>aitasks
OLD AITASK CONTENT
<<<aitasks

# Custom Footer
EOF
(
    SCRIPT_DIR="$TMPDIR_TEST/.aitask-scripts"
    mkdir -p "$SCRIPT_DIR"
    setup_codex_cli < /dev/null
)
result="$(cat "$TMPDIR_TEST/.codex/instructions.md")"
assert_contains "T15: custom header preserved" "# Custom Header" "$result"
assert_contains "T15: custom footer preserved" "# Custom Footer" "$result"
assert_not_contains "T15: old content replaced" "OLD AITASK CONTENT" "$result"
assert_contains "T15: new content present" "## Git Operations" "$result"
# Count markers — should be exactly one pair
marker_count=$(grep -c ">>>aitasks" "$TMPDIR_TEST/.codex/instructions.md" || true)
assert_eq "T15: exactly one start marker" "1" "$marker_count"
cleanup_tmpdir

# Test 16: Existing Codex config is preserved and missing feature flag is merged idempotently
setup_tmpdir
create_codex_staging "$TMPDIR_TEST"
mkdir -p "$TMPDIR_TEST/.codex"
cat > "$TMPDIR_TEST/.codex/config.toml" <<'TOML'
model = "custom-model"

[features]
custom_existing_feature = true
TOML
(
    SCRIPT_DIR="$TMPDIR_TEST/.aitask-scripts"
    mkdir -p "$SCRIPT_DIR"
    setup_codex_cli < /dev/null
    setup_codex_cli < /dev/null
)
config_result="$(cat "$TMPDIR_TEST/.codex/config.toml")"
assert_contains "T16: custom model preserved" 'model = "custom-model"' "$config_result"
assert_contains "T16: existing feature preserved" "custom_existing_feature = true" "$config_result"
assert_contains "T16: request_user_input feature merged" "default_mode_request_user_input = true" "$config_result"
feature_count=$(grep -c "default_mode_request_user_input = true" "$TMPDIR_TEST/.codex/config.toml" || true)
assert_eq "T16: request_user_input feature not duplicated" "1" "$feature_count"
cleanup_tmpdir

# Test 17: Existing Codex rules are preserved and missing aitask rules are merged
setup_tmpdir
create_codex_staging "$TMPDIR_TEST"
mkdir -p "$TMPDIR_TEST/.codex/rules"
cat > "$TMPDIR_TEST/.codex/rules/default.rules" <<'RULES'
prefix_rule(pattern = ["gh", "pr", "view"], decision = "prompt", justification = "Custom user rule")
prefix_rule(pattern = ["./.aitask-scripts/aitask_skill_render.sh"], decision = "allow", justification = "Aitasks helper script")
RULES
(
    SCRIPT_DIR="$TMPDIR_TEST/.aitask-scripts"
    mkdir -p "$SCRIPT_DIR"
    setup_codex_cli < /dev/null
)
rules_result="$(cat "$TMPDIR_TEST/.codex/rules/default.rules")"
assert_contains "T17: custom rule preserved" "Custom user rule" "$rules_result"
assert_contains "T17: missing aitask rule merged" "aitask_skill_resolve_profile.sh" "$rules_result"
render_rule_count=$(grep -c "aitask_skill_render.sh" "$TMPDIR_TEST/.codex/rules/default.rules" || true)
assert_eq "T17: existing aitask rule not duplicated" "1" "$render_rule_count"
cleanup_tmpdir

# ============================================================
# Tests for update_agentsmd() (AGENTS.md cross-agent convention, t875)
# ============================================================
# AGENTS.md is installed unconditionally by setup_code_agents() and receives
# the shared Layer-1 instructions only (no agent_type passed). setup_tmpdir
# seeds BOTH the shared seed and a codex Layer-2 seed, so the Layer-1-only
# assertion below is meaningful: the codex content is present on disk but must
# NOT leak into AGENTS.md.

echo "--- update_agentsmd() ---"

# Test 18: Create-if-missing — fresh AGENTS.md gets the marked Layer-1 block
setup_tmpdir
update_agentsmd "$TMPDIR_TEST"
result="$(cat "$TMPDIR_TEST/AGENTS.md")"
assert_file_contains "T18: AGENTS.md created when absent" ">>>aitasks" "$TMPDIR_TEST/AGENTS.md"
assert_contains "T18: fresh AGENTS.md has start marker" ">>>aitasks" "$result"
assert_contains "T18: fresh AGENTS.md has end marker" "<<<aitasks" "$result"
assert_contains "T18: fresh AGENTS.md has shared content" "## Git Operations" "$result"
cleanup_tmpdir

# Test 19: Layer-1 only — shared content present, agent-specific Layer 2 excluded
setup_tmpdir
update_agentsmd "$TMPDIR_TEST"
result="$(cat "$TMPDIR_TEST/AGENTS.md")"
assert_contains "T19: shared Layer-1 content present" "## Git Operations" "$result"
assert_not_contains "T19: no codex Skills body" "Invoke skills with" "$result"
assert_not_contains "T19: no codex Agent Identification header" "## Agent Identification" "$result"
assert_not_contains "T19: no codex agent-id blurb" "codex/<model_name>" "$result"
cleanup_tmpdir

# Test 20: Marker idempotency — running twice yields identical output, one block
setup_tmpdir
update_agentsmd "$TMPDIR_TEST"
first_result="$(cat "$TMPDIR_TEST/AGENTS.md")"
update_agentsmd "$TMPDIR_TEST"
second_result="$(cat "$TMPDIR_TEST/AGENTS.md")"
assert_eq "T20: idempotent update" "$first_result" "$second_result"
marker_count=$(grep -c ">>>aitasks" "$TMPDIR_TEST/AGENTS.md" || true)
assert_eq "T20: exactly one start marker" "1" "$marker_count"
cleanup_tmpdir

# Test 21: Preserve surrounding text — prose kept, block appended, then replaced in place
setup_tmpdir
cat > "$TMPDIR_TEST/AGENTS.md" <<'EOF'
# Project Agent Guide

Custom user prose that must survive.
EOF
update_agentsmd "$TMPDIR_TEST"
result="$(cat "$TMPDIR_TEST/AGENTS.md")"
assert_contains "T21: user prose preserved" "Custom user prose that must survive." "$result"
assert_contains "T21: header preserved" "# Project Agent Guide" "$result"
assert_contains "T21: markers appended" ">>>aitasks" "$result"
assert_contains "T21: shared content appended" "## Git Operations" "$result"
# Second run replaces only the marked region, preserving the surrounding prose
update_agentsmd "$TMPDIR_TEST"
result2="$(cat "$TMPDIR_TEST/AGENTS.md")"
assert_contains "T21: prose still preserved after 2nd run" "Custom user prose that must survive." "$result2"
marker_count=$(grep -c ">>>aitasks" "$TMPDIR_TEST/AGENTS.md" || true)
assert_eq "T21: single marker block after 2nd run" "1" "$marker_count"
cleanup_tmpdir

# ============================================================
# Summary
# ============================================================

echo ""
echo "=== Results ==="
echo "PASS: $PASS / $TOTAL"
if [[ $FAIL -gt 0 ]]; then
    echo "FAIL: $FAIL"
    exit 1
else
    echo "All tests passed!"
fi
