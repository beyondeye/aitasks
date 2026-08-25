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

# Drive the real setup_code_agents against <project_dir> (t1612).
#
# Only _is_agent_installed is stubbed, and only for determinism: it is
# `command -v codex/opencode` (aitask_setup.sh), i.e. a property of the
# developer's machine -- both ARE present on some dev boxes, so without the stub
# the drive would really run setup_codex_cli/setup_opencode against the fixture.
# setup_claude_code and prune_retired_skills self-no-op here (no
# aitasks/metadata/claude_settings.seed.json, no
# $SCRIPT_DIR/aitask_prune_retired_skills.sh). Note that in PRODUCTION both DO
# run -- ensure_agent_config_seeds installs the settings seed before
# setup_code_agents -- so this fixture is deliberately unrepresentative there.
# update_agentsmd and update_claudemd_git_section run for real, which is the point.
#
# stdout: setup_code_agents' own output, unmerged -- T41/T42 assert on info()
#         lines, and info() writes to STDOUT (aitask_setup.sh:137).
# stderr: passed through, so assemble_aitasks_instructions' warn stays visible on
#         failure without being able to satisfy a stdout message assertion.
# exit:   setup_code_agents' real status. Callers MUST use
#             out=""; rc=0; out="$(run_setup_code_agents "$d")" || rc=$?
#         -- this file runs under `set -e` (:7) AND inherits -u/-o pipefail from
#         sourcing aitask_setup.sh, so a bare assignment on a non-zero return
#         would abort the whole file before any FAIL: line or the summary.
# The subshell keeps the stub from leaking into later tests; assertions must stay
# OUTSIDE it, since PASS/FAIL/TOTAL are in-process counters (t1207).
run_setup_code_agents() {
    local project_dir="$1"
    (
        SCRIPT_DIR="$project_dir/.aitask-scripts"
        mkdir -p "$SCRIPT_DIR"
        # Overrides the sourced aitask_setup.sh definition that setup_code_agents
        # calls; shellcheck cannot see that indirect invocation.
        # shellcheck disable=SC2329
        _is_agent_installed() { return 1; }
        setup_code_agents </dev/null
    )
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

# --- hand-maintained CLAUDE.md guard (t1607) --------------------------------
# CLAUDE.md is the only project-OWNED instruction surface: AGENTS.md and the two
# mirrors are framework-owned files whose whole body IS the marked block, but
# CLAUDE.md can carry the aitasks conventions as hand-written prose (this repo's
# own does, as does every project set up before the markers existed). t130_2
# dropped t221_3's content-based skip guard when it generalized the function to
# the marker system, so setup would append a duplicate block on top of that
# prose. T12b-T12d pin the restored guard from all three sides.

# Test 12b: a markerless CLAUDE.md that already documents the conventions is left
# alone -- AND says so. The byte-identity assertions alone cannot tell the
# intended guard from a bare `return 0`: a regression to a silent no-op passes
# every one of them while destroying both the discoverability of the skip and the
# warning that keeps the opt-in from eating the user's prose. So the messages are
# asserted too, on captured stdout (info() writes to stdout, aitask_setup.sh:137).
setup_tmpdir
cat > "$TMPDIR_TEST/CLAUDE.md" <<'EOF'
# My Project

## Git Operations on Task/Plan Files

Use `./ait git` for task files. My own wording, hand-maintained.

## House rules

Never reformat the config.
EOF
before_hm="$(cat "$TMPDIR_TEST/CLAUDE.md")"
hm_out="$(update_claudemd_git_section "$TMPDIR_TEST")"
after_hm="$(cat "$TMPDIR_TEST/CLAUDE.md")"
assert_eq "T12b: hand-maintained CLAUDE.md untouched" "$before_hm" "$after_hm"
assert_not_contains "T12b: no markers appended" ">>>aitasks" "$after_hm"
assert_contains "T12b: skip reason announced" "leaving it hand-maintained" "$hm_out"
assert_contains "T12b: opt-in path announced" "'>>>aitasks' / '<<<aitasks' line pair" "$hm_out"
assert_contains "T12b: overwrite warning announced" "overwritten on every setup" "$hm_out"
cleanup_tmpdir

# Test 12c: negative control -- the guard is NOT a blanket skip. A markerless
# CLAUDE.md with no aitasks prose still gets the block. T11 walks the same path
# but not this dimension; without T12c a widened sentinel could silently disable
# bootstrap for every project with a pre-existing CLAUDE.md and stay green.
setup_tmpdir
cat > "$TMPDIR_TEST/CLAUDE.md" <<'EOF'
# My Project

## Build

Run make.
EOF
update_claudemd_git_section "$TMPDIR_TEST" >/dev/null
result="$(cat "$TMPDIR_TEST/CLAUDE.md")"
assert_contains "T12c: no-sentinel file still gets markers" ">>>aitasks" "$result"
assert_contains "T12c: no-sentinel file still gets content" "## Git Operations" "$result"
assert_contains "T12c: original content preserved" "Run make." "$result"
cleanup_tmpdir

# Test 12d: marker precedence. A marker-MANAGED block necessarily contains the
# sentinel, so the marker check must be evaluated first; an inverted condition
# order would freeze every legitimate refresh. T12 cannot catch that -- its
# fixture body is "OLD INSTRUCTIONS HERE", which carries no sentinel.
setup_tmpdir
cat > "$TMPDIR_TEST/CLAUDE.md" <<'EOF'
# My Project

>>>aitasks
## Git Operations on Task/Plan Files

STALE GENERATED BLOCK
<<<aitasks
EOF
update_claudemd_git_section "$TMPDIR_TEST" >/dev/null
result="$(cat "$TMPDIR_TEST/CLAUDE.md")"
assert_not_contains "T12d: managed block refreshed despite sentinel" "STALE GENERATED BLOCK" "$result"
assert_contains "T12d: regenerated content present" "Use \`./ait git\` instead of plain \`git\`." "$result"
marker_count_12d=$(grep -c '^>>>aitasks$' "$TMPDIR_TEST/CLAUDE.md" || true)
assert_eq "T12d: still exactly one start marker" "1" "${marker_count_12d:-0}"
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
# Tests for committed codex/opencode instruction mirrors (t1028)
# ============================================================
# Regression guard: the committed .codex/instructions.md and
# .opencode/instructions.md mirrors MUST carry the >>>aitasks/<<<aitasks markers.
# Without them, a future `ait setup` takes the append branch of
# insert_aitasks_instructions() and duplicates the whole aitasks block instead
# of replacing it in place (the t1028 bug). These assert the real repo
# artifacts, so they catch the markerless drift directly.

echo "--- committed instruction mirrors (t1028) ---"

assert_marker_pair() {
    local desc="$1" file="$2"
    local starts ends
    starts=$(grep -c '^>>>aitasks$' "$file" 2>/dev/null || true)
    ends=$(grep -c '^<<<aitasks$' "$file" 2>/dev/null || true)
    assert_eq "$desc: exactly one start marker" "1" "${starts:-0}"
    assert_eq "$desc: exactly one end marker" "1" "${ends:-0}"
}

# Test 22: committed .codex/instructions.md carries exactly one marker pair
assert_marker_pair "T22: committed .codex/instructions.md" "$PROJECT_DIR/.codex/instructions.md"

# Test 23: committed .opencode/instructions.md carries exactly one marker pair
assert_marker_pair "T23: committed .opencode/instructions.md" "$PROJECT_DIR/.opencode/instructions.md"

# Test 24: opencode marker idempotency — a second setup-style insert does not
# duplicate the block in the opencode mirror (parity with codex T15/T20; both
# mirrors go through the same insert_aitasks_instructions()).
setup_tmpdir
cat > "$TMPDIR_TEST/aitasks/metadata/opencode_instructions.seed.md" <<'EOF'
# aitasks Framework — OpenCode Instructions

For shared conventions, see shared seed file.

## Agent Identification

Identify as `opencode/<model_name>`.
EOF
oc_content="$(assemble_aitasks_instructions "$TMPDIR_TEST" "opencode")"
oc_target="$TMPDIR_TEST/.opencode/instructions.md"
mkdir -p "$TMPDIR_TEST/.opencode"
rm -f "$oc_target"
insert_aitasks_instructions "$oc_target" "$oc_content"   # first (create) run
first_oc="$(cat "$oc_target")"
insert_aitasks_instructions "$oc_target" "$oc_content"   # second (replace) run
second_oc="$(cat "$oc_target")"
assert_eq "T24: opencode insert idempotent across runs" "$first_oc" "$second_oc"
oc_marker_count=$(grep -c '^>>>aitasks$' "$oc_target" || true)
assert_eq "T24: opencode mirror has exactly one start marker after 2nd run" "1" "$oc_marker_count"
assert_contains "T24: opencode mirror has shared content" "## Git Operations" "$second_oc"
assert_contains "T24: opencode mirror has agent-specific content" "## Agent Identification" "$second_oc"
cleanup_tmpdir

# ============================================================
# Seed -> mirror content drift guard (t1601)
# ============================================================
# T22/T23 above prove the committed mirrors still carry their markers. They never
# look at what is BETWEEN the markers, so the block can rot silently:
# setup_codex_cli / setup_opencode are skipped whenever the agent CLI is not
# installed (_is_agent_installed), the aitasks/metadata/<agent>_skills staging
# dir is absent, or the user declines the prompt -- while update_agentsmd is
# ungated. That asymmetry is exactly how the gates:/active_gates* lines went
# missing from both mirrors while AGENTS.md stayed current (t1601).
#
# DERIVED, NOT DUPLICATED: nothing below hardcodes expected text. Each surface is
# compared against what the LIVE generator produces from the LIVE seeds -- the
# same assemble_aitasks_instructions() that `ait setup` calls.

echo "--- seed -> mirror content drift (t1601) ---"

# resolved_shared_seed <project_dir> -- the shared seed assemble_aitasks_instructions
# will actually read, mirroring its precedence (aitask_setup.sh assemble_*).
# Diagnostic only: a red guard can mean "the mirror drifted" OR "this checkout's
# aitasks/metadata seed copy drifted", and the diff alone cannot tell them apart.
resolved_shared_seed() {
    local pdir="$1"
    if [[ -f "$pdir/aitasks/metadata/aitasks_agent_instructions.seed.md" ]]; then
        echo "$pdir/aitasks/metadata/aitasks_agent_instructions.seed.md"
    elif [[ -f "$pdir/seed/aitasks_agent_instructions.seed.md" ]]; then
        echo "$pdir/seed/aitasks_agent_instructions.seed.md"
    else
        echo "(none)"
    fi
}

# _extract_marked_block <file> <outfile> -- writes the block body to <outfile>
# and echoes exactly one structural verdict:
#   OK | NO_START_MARKER | NO_END_MARKER | MULTIPLE_BLOCKS | MARKERS_OUT_OF_ORDER
#
# ONE pass does both the extraction and the structural verdict, deliberately.
# Counting the markers with grep and extracting with a separate awk cannot
# express ORDER: a file whose <<<aitasks precedes its >>>aitasks counts 1 and 1,
# and a start-to-EOF extraction then yields the whole tail -- so an unterminated
# block compared equal and returned MATCH (t1601 review). A single state machine
# has no second pass to disagree with.
_extract_marked_block() {
    : > "$2"
    awk -v out="$2" '
        /^>>>aitasks$/ {
            starts++
            if (ends > 0) { order_bad = 1 }   # an end marker preceded this start
            state = 1
            next
        }
        /^<<<aitasks$/ {
            ends++
            if (state == 1) { state = 2 }     # closes the open start
            else { order_bad = 1 }            # end with no open start before it
            next
        }
        state == 1 { print > out }
        END {
            if (starts == 0)            { print "NO_START_MARKER";      exit }
            if (ends == 0)              { print "NO_END_MARKER";        exit }
            if (starts > 1 || ends > 1) { print "MULTIPLE_BLOCKS";      exit }
            if (order_bad || state != 2){ print "MARKERS_OUT_OF_ORDER"; exit }
            print "OK"
        }
    ' "$1"
}

# block_status <project_dir> <file> <workdir> [agent] -- echoes exactly one of:
#   MATCH | MISMATCH | ASSEMBLE_FAILED | NO_SUCH_FILE
#   NO_START_MARKER | NO_END_MARKER | MULTIPLE_BLOCKS | MARKERS_OUT_OF_ORDER
# Leaves $workdir/expected and $workdir/actual behind for the failure dump.
#
# The comparison goes through FILES, never "$(...)": bash strips ALL trailing
# newlines from a command substitution, on BOTH sides, so a blank line added just
# before <<<aitasks would compare equal and the guard would fail open. T35 pins
# that exact case. The structural verdict is resolved BEFORE the comparison, so a
# malformed block can never reach cmp and read as MATCH (T30/T31/T34/T36).
block_status() {
    local pdir="$1" file="$2" work="$3" agent="${4:-}"
    local rc=0 struct
    local -a args=("$pdir")
    if [[ -n "$agent" ]]; then
        args+=("$agent")
    fi

    if [[ ! -f "$file" ]]; then
        echo "NO_SUCH_FILE"; return 0
    fi

    struct="$(_extract_marked_block "$file" "$work/actual")"
    if [[ "$struct" != "OK" ]]; then
        echo "$struct"; return 0
    fi

    assemble_aitasks_instructions "${args[@]}" > "$work/expected" 2>"$work/assemble.err" || rc=$?
    if [[ "$rc" -ne 0 || ! -s "$work/expected" ]]; then
        echo "ASSEMBLE_FAILED"; return 0
    fi

    if cmp -s "$work/expected" "$work/actual"; then
        echo "MATCH"
    else
        echo "MISMATCH"
    fi
}

# check_surface <label> <file> [agent] -- assert one tracked surface matches the
# generator, dumping an actionable diff (and the resolved seed) on failure.
check_surface() {
    local label="$1" file="$2" agent="${3:-}"
    local work status
    work="$(mktemp -d)"
    status="$(block_status "$PROJECT_DIR" "$file" "$work" "$agent")"
    assert_eq "$label: block matches the generated instructions" "MATCH" "$status"
    if [[ "$status" != "MATCH" ]]; then
        echo "  resolved shared seed: $(resolved_shared_seed "$PROJECT_DIR")"
        echo "  fix: source .aitask-scripts/aitask_setup.sh --source-only && \\"
        echo "       insert_aitasks_instructions <file> \"\$(assemble_aitasks_instructions . [agent])\""
        if [[ -s "$work/expected" && -s "$work/actual" ]]; then
            echo "  --- diff (expected = generator, actual = file) ---"
            diff -u "$work/expected" "$work/actual" 2>/dev/null | head -40 || true
        fi
        if [[ -s "$work/assemble.err" ]]; then
            echo "  assemble stderr: $(head -3 "$work/assemble.err")"
        fi
    fi
    rm -rf "$work"
}

# Test 25: committed AGENTS.md matches the shared layer
check_surface "T25: committed AGENTS.md" "$PROJECT_DIR/AGENTS.md"

# Test 26: committed .codex/instructions.md matches shared + codex layer
check_surface "T26: committed .codex/instructions.md" "$PROJECT_DIR/.codex/instructions.md" "codex"

# Test 27: committed .opencode/instructions.md matches shared + opencode layer
check_surface "T27: committed .opencode/instructions.md" "$PROJECT_DIR/.opencode/instructions.md" "opencode"

# --- negative controls (T28-T37) --------------------------------------------
# Every outcome block_status's contract names is exercised here, so none is
# advertised-but-unproven. The mapping is NOT one-to-one and must not be
# "tidied" into one: MISMATCH is asserted three times (T28/T29/T35) and
# MULTIPLE_BLOCKS twice (T34/T37) because T35 and T36 exist to pin two specific
# fail-opens found in review -- a trailing blank line before <<<aitasks, which a
# "$(...)" comparison cannot see, and an inverted marker pair whose counts still
# read 1 and 1. Deleting either as "redundant by verdict" restores its bug.
# All operate on throwaway COPIES under a temp dir -- no tracked file is ever
# mutated, so an interrupted run cannot leave the working tree corrupt and no
# restore step has to survive a signal.
NEG_DIR="$(mktemp -d)"

neg_status() {   # neg_status <fixture-file> [agent]
    local f="$1" agent="${2:-}" work status
    work="$(mktemp -d "$NEG_DIR/work.XXXXXX")"
    status="$(block_status "$PROJECT_DIR" "$f" "$work" "$agent")"
    rm -rf "$work"
    echo "$status"
}

# Test 28: the EXACT t1601 drift on a copy -- deleting the gates: line must be
# caught. This is the proof that this guard would have caught the bug it was
# written for, with the tracked mirror never leaving a good state.
grep -v '^gates: \[risk_evaluated\]' "$PROJECT_DIR/.codex/instructions.md" > "$NEG_DIR/deleted.md"
assert_eq "T28: deleted seed line detected" "MISMATCH" "$(neg_status "$NEG_DIR/deleted.md" codex)"

# Test 29: an ADDED line is caught too -- drift is not one-directional
awk '/^issue: https/{print "bogus_field: 1"} {print}' "$PROJECT_DIR/.codex/instructions.md" > "$NEG_DIR/added.md"
assert_eq "T29: inserted line detected" "MISMATCH" "$(neg_status "$NEG_DIR/added.md" codex)"

# Test 30: a missing end marker is its own state, never a silent pass
grep -v '^<<<aitasks$' "$PROJECT_DIR/.codex/instructions.md" > "$NEG_DIR/noend.md"
assert_eq "T30: missing end marker reported" "NO_END_MARKER" "$(neg_status "$NEG_DIR/noend.md" codex)"

# Test 31: no markers at all
grep -v -e '^>>>aitasks$' -e '^<<<aitasks$' "$PROJECT_DIR/.codex/instructions.md" > "$NEG_DIR/nomarkers.md"
assert_eq "T31: missing start marker reported" "NO_START_MARKER" "$(neg_status "$NEG_DIR/nomarkers.md" codex)"

# Test 32: a project dir resolving NO seed must fail closed. "Cannot verify" is
# its own state -- it must never degrade into an empty expected block that
# compares equal to an empty actual one.
mkdir -p "$NEG_DIR/emptyproj"
work32="$(mktemp -d "$NEG_DIR/work.XXXXXX")"
assert_eq "T32: unresolvable seed fails closed" "ASSEMBLE_FAILED" \
    "$(block_status "$NEG_DIR/emptyproj" "$PROJECT_DIR/.codex/instructions.md" "$work32" codex)"
rm -rf "$work32"

# Test 33: a path that does not exist
assert_eq "T33: missing file reported" "NO_SUCH_FILE" "$(neg_status "$NEG_DIR/does_not_exist.md" codex)"

# Test 34: a DUPLICATED block -- the t1028 failure mode -- is reported as its own
# state, not silently reduced to the first block and compared as MATCH.
cat "$PROJECT_DIR/.codex/instructions.md" "$PROJECT_DIR/.codex/instructions.md" > "$NEG_DIR/dup.md"
assert_eq "T34: duplicated block reported" "MULTIPLE_BLOCKS" "$(neg_status "$NEG_DIR/dup.md" codex)"

# Test 35: a blank line added immediately before <<<aitasks. This is the fixture
# that distinguishes the file-based comparison from a "$(...)" one: bash strips
# trailing newlines from command substitutions, so this exact drift reads as
# MATCH the moment anyone "simplifies" block_status back to string capture.
awk '/^<<<aitasks$/{print ""} {print}' "$PROJECT_DIR/.codex/instructions.md" > "$NEG_DIR/trailing.md"
assert_eq "T35: trailing blank line before end marker detected" "MISMATCH" \
    "$(neg_status "$NEG_DIR/trailing.md" codex)"

# Test 36: an INVERTED pair -- <<<aitasks first, then >>>aitasks followed by the
# real generated content, with nothing closing the block. Marker COUNTS are 1 and
# 1, so any count-plus-separate-extraction scheme reports MATCH on a block that
# is never terminated (the t1601 review defect). Order is structural state, not
# something a count can carry, so the single-pass extractor must reject it.
{
    echo '<<<aitasks'
    echo '>>>aitasks'
    awk '/^>>>aitasks$/{f=1;next} /^<<<aitasks$/{f=0} f' "$PROJECT_DIR/.codex/instructions.md"
} > "$NEG_DIR/inverted.md"
assert_eq "T36: inverted marker order reported" "MARKERS_OUT_OF_ORDER" \
    "$(neg_status "$NEG_DIR/inverted.md" codex)"

# Test 37: a stray <<<aitasks BEFORE a well-formed block. Counts are 2 ends /
# 1 start, so this exits via MULTIPLE_BLOCKS -- asserted explicitly so the
# precedence between the structural verdicts is pinned, not incidental.
{
    echo '<<<aitasks'
    cat "$PROJECT_DIR/.codex/instructions.md"
} > "$NEG_DIR/stray_end.md"
assert_eq "T37: stray leading end marker reported" "MULTIPLE_BLOCKS" \
    "$(neg_status "$NEG_DIR/stray_end.md" codex)"

rm -rf "$NEG_DIR"

# ============================================================
# CLAUDE.md: the fourth surface, pinned to the OPPOSITE state (t1607)
# ============================================================
# T22-T27 pin three surfaces as marker-managed and matching the generator.
# CLAUDE.md is deliberately NOT one of them -- it is project-owned mixed content
# that this repo maintains by hand (aidocs/framework/aitasks_extension_points.md).
# That contract used to hold for the wrong reason: before t1607 there was no
# guard at all, and the only thing keeping this repo's CLAUDE.md markerless was
# that update_claudemd_git_section sat in setup_data_branch Step 8, which
# early-returns whenever .aitask-data/.git exists. t1612 then moved the call to
# setup_code_agents, so `ait setup` in THIS repo now really does reach the
# function on every run -- and T38 passes because the t1607 sentinel guard fires,
# not because the code path is unreachable. Same assertions, real coverage.

echo "--- CLAUDE.md hand-maintained contract (t1607) ---"

# Test 38: committed CLAUDE.md is markerless AND self-documenting. Both halves
# are load-bearing. Markers-absent alone would still pass if someone deleted the
# "## Git Operations on Task/Plan Files" section -- which is exactly what would
# make the file append-eligible again, silently reopening the bug.
claudemd_starts=$(grep -c '^>>>aitasks$' "$PROJECT_DIR/CLAUDE.md" 2>/dev/null || true)
claudemd_ends=$(grep -c '^<<<aitasks$' "$PROJECT_DIR/CLAUDE.md" 2>/dev/null || true)
assert_eq "T38: committed CLAUDE.md has no start marker" "0" "${claudemd_starts:-0}"
assert_eq "T38: committed CLAUDE.md has no end marker" "0" "${claudemd_ends:-0}"
assert_file_contains "T38: committed CLAUDE.md carries the guard sentinel" \
    "$CLAUDEMD_HAND_MAINTAINED_SENTINEL" "$PROJECT_DIR/CLAUDE.md"

# Test 39: the sentinel is a single named constant in aitask_setup.sh, so it can
# drift from the seed it is supposed to identify. Pin it to the seed the live
# generator actually resolves (same helper T25-T27's failure dump uses), so a
# heading rename in the seed fails here instead of quietly turning the guard off.
CLAUDEMD_SEED="$(resolved_shared_seed "$PROJECT_DIR")"
assert_file_contains "T39: sentinel still present in the resolved shared seed" \
    "$CLAUDEMD_HAND_MAINTAINED_SENTINEL" "$CLAUDEMD_SEED"

# ============================================================
# CLAUDE.md refresh lifecycle: reachable from setup_code_agents (t1612)
# ============================================================
# Until t1612, update_claudemd_git_section had exactly one production call site --
# setup_data_branch Step 8 -- behind four early returns, so CLAUDE.md was written
# only on a successful FIRST-TIME data-branch setup: never refreshed on re-runs,
# never written at all in legacy mode. AGENTS.md never had that problem because
# update_agentsmd is called unconditionally from setup_code_agents. T40-T42 drive
# the REAL setup_code_agents to prove the call now lives there; T43 proves it no
# longer lives in setup_data_branch.
#
# Deliberately NOT added here: a marker-refresh test (T12d already pins stale-body
# removal and the one-marker-pair invariant) and a separate "legacy layout" test
# (setup_tmpdir already IS a legacy layout -- real aitasks/, no .aitask-data/ --
# and nothing in setup_code_agents' call graph reads .aitask-data/, symlinks or
# branch mode, so such a test could not distinguish any implementation from any
# other). The legacy-mode DECLINE branch cannot be driven at all: it needs
# [[ -t 0 ]] true and tests/ has no pty harness. T43 is what generalizes T40-T42
# to every setup_data_branch early return, decline included.

echo "--- CLAUDE.md refresh lifecycle via setup_code_agents (t1612) ---"

# Test 40: reachability. A fixture with no CLAUDE.md gets the managed block from
# setup_code_agents. The AGENTS.md half is the positive control: without it a
# drive that no-opped entirely would be indistinguishable from one that ran.
setup_tmpdir
out=""; rc=0
out="$(run_setup_code_agents "$TMPDIR_TEST")" || rc=$?
assert_eq "T40: setup_code_agents exited 0" "0" "$rc"
result="$(cat "$TMPDIR_TEST/CLAUDE.md" 2>/dev/null || true)"
assert_contains "T40: setup_code_agents wrote CLAUDE.md start marker" ">>>aitasks" "$result"
assert_contains "T40: CLAUDE.md carries the shared content" "## Git Operations" "$result"
assert_contains "T40: CLAUDE.md has end marker" "<<<aitasks" "$result"
agents_result="$(cat "$TMPDIR_TEST/AGENTS.md" 2>/dev/null || true)"
assert_contains "T40: positive control -- AGENTS.md written by the same drive" ">>>aitasks" "$agents_result"
cleanup_tmpdir

# Test 41: the upgrade path t1612 actually unlocks. An already-installed project
# whose markerless CLAUDE.md carries user prose and NO sentinel now receives the
# whole block on its next `ait setup`. That is a large, unsolicited mutation of a
# project-owned file, so pin both runs: the block lands once, the user's prose
# survives, and the second run REFRESHES in place rather than appending a second
# block. The two stdout assertions pin the append-vs-refresh announcement -- the
# file writes are byte-identical either way, so nothing else can see a regression
# that collapses the two messages back into one.
setup_tmpdir
cat > "$TMPDIR_TEST/CLAUDE.md" <<'EOF'
# My Project

## Build

Run make. This line is mine and must survive setup.
EOF
out1=""; rc=0
out1="$(run_setup_code_agents "$TMPDIR_TEST")" || rc=$?
assert_eq "T41: first run exited 0" "0" "$rc"
result="$(cat "$TMPDIR_TEST/CLAUDE.md")"
assert_contains "T41: block appended on upgrade" ">>>aitasks" "$result"
assert_contains "T41: user prose survives the append" "This line is mine and must survive setup." "$result"
assert_contains "T41: append is announced as an append" "Added a managed '>>>aitasks' block" "$out1"
out2=""; rc=0
out2="$(run_setup_code_agents "$TMPDIR_TEST")" || rc=$?
assert_eq "T41: second run exited 0" "0" "$rc"
result="$(cat "$TMPDIR_TEST/CLAUDE.md")"
assert_contains "T41: user prose survives the refresh too" "This line is mine and must survive setup." "$result"
marker_starts_41=$(grep -c '^>>>aitasks$' "$TMPDIR_TEST/CLAUDE.md" || true)
marker_ends_41=$(grep -c '^<<<aitasks$' "$TMPDIR_TEST/CLAUDE.md" || true)
assert_eq "T41: still exactly one start marker after two runs" "1" "${marker_starts_41:-0}"
assert_eq "T41: still exactly one end marker after two runs" "1" "${marker_ends_41:-0}"
assert_contains "T41: refresh announced as a refresh" "Updated aitasks instructions in CLAUDE.md" "$out2"
assert_not_contains "T41: refresh does NOT repeat the append announcement" "Added a managed '>>>aitasks' block" "$out2"
cleanup_tmpdir

# Test 42: the t1607 hand-maintained guard now stands on the path `ait setup`
# really takes. T12b asserts the same behavior against a direct call; the whole
# point of t1612 is that the guard used to be near-unreachable, so it needs an
# assertion through setup_code_agents too. T40 and T42 together cover both
# branches of the new call site.
setup_tmpdir
cat > "$TMPDIR_TEST/CLAUDE.md" <<'EOF'
# My Project

## Git Operations on Task/Plan Files

Use `./ait git` for task files. My own wording, hand-maintained.

## House rules

Never reformat the config.
EOF
before_42="$(cat "$TMPDIR_TEST/CLAUDE.md")"
out=""; rc=0
out="$(run_setup_code_agents "$TMPDIR_TEST")" || rc=$?
assert_eq "T42: setup_code_agents exited 0" "0" "$rc"
after_42="$(cat "$TMPDIR_TEST/CLAUDE.md")"
assert_eq "T42: hand-maintained CLAUDE.md untouched via setup_code_agents" "$before_42" "$after_42"
assert_not_contains "T42: no markers appended via setup_code_agents" ">>>aitasks" "$after_42"
assert_contains "T42: skip reason announced on the live path" "leaving it hand-maintained" "$out"
assert_contains "T42: opt-in path announced on the live path" "'>>>aitasks' / '<<<aitasks' line pair" "$out"
assert_contains "T42: overwrite warning announced on the live path" "overwritten on every setup" "$out"
cleanup_tmpdir

# Test 43: structural pair, both halves load-bearing. Probes the SOURCED function
# bodies -- declare -f reproduces from the parsed AST and strips comments, so the
# explanatory comments t1612 left at both sites cannot skew either half
# (precedent: tests/test_setup_git.sh Test 22).
#
# The negative half is the ONLY detector of "added the new call but forgot to
# delete Step 8": a double write is functionally invisible, because
# insert_aitasks_instructions' marker replacement makes the second write
# byte-identical to the first. It is also what generalizes T40-T42 to the
# setup_data_branch decline branch, which no test can drive.
# The positive half keeps the probe from being vacuous -- renaming the function
# would otherwise zero out both greps and read green.
data_branch_body="$(declare -f setup_data_branch)"
code_agents_body="$(declare -f setup_code_agents)"
assert_not_contains "T43: setup_data_branch no longer calls update_claudemd_git_section" \
    "update_claudemd_git_section" "$data_branch_body"
assert_contains "T43: setup_code_agents calls update_claudemd_git_section" \
    "update_claudemd_git_section" "$code_agents_body"
assert_contains "T43: control -- setup_code_agents still calls update_agentsmd" \
    "update_agentsmd" "$code_agents_body"

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
