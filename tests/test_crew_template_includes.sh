#!/usr/bin/env bash
# test_crew_template_includes.sh - Tests for <!-- include: filename --> template resolution.
# Run: bash tests/test_crew_template_includes.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"
ORIG_DIR="$(pwd)"

# File-based counters (work across subshells)
COUNTER_FILE="$(mktemp "${TMPDIR:-/tmp}/ait_test_counters_XXXXXX")"
echo "0 0 0" > "$COUNTER_FILE"
trap 'rm -f "$COUNTER_FILE"' EXIT

_inc_pass() {
    local p f t
    read -r p f t < "$COUNTER_FILE"
    echo "$((p + 1)) $f $((t + 1))" > "$COUNTER_FILE"
}
_inc_fail() {
    local p f t
    read -r p f t < "$COUNTER_FILE"
    echo "$p $((f + 1)) $((t + 1))" > "$COUNTER_FILE"
}

# --- Test helpers ---

# Shared assertion helpers (see tests/lib/asserts.sh)
. "$PROJECT_DIR/tests/lib/asserts.sh"




# --- Setup: create isolated git repo ---

setup_test_repo() {
    local tmpdir
    tmpdir="$(mktemp -d)"

    (
        cd "$tmpdir"
        git init --quiet
        git config user.email "test@test.com"
        git config user.name "Test"

        mkdir -p aitasks/metadata
        setup_fake_aitask_repo "$PWD"

        cp "$PROJECT_DIR/.aitask-scripts/lib/agentcrew_utils.sh" .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/lib/launch_modes_sh.sh" .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/lib/launch_modes.py"    .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_crew_init.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_crew_addwork.sh" .aitask-scripts/
        chmod +x .aitask-scripts/aitask_crew_init.sh .aitask-scripts/aitask_crew_addwork.sh

        echo "email: test@test.com" > aitasks/metadata/userconfig.yaml

        git add -A
        git commit -m "Initial setup" --quiet
    )

    echo "$tmpdir"
}

cleanup_test_repo() {
    local tmpdir="$1"
    cd "$ORIG_DIR"
    if [[ -d "$tmpdir" ]]; then
        (cd "$tmpdir" && git worktree prune 2>/dev/null || true)
        rm -rf "$tmpdir"
    fi
}

# ============================================================
# Tests: resolve_template_includes (unit tests via sourcing)
# ============================================================

echo "=== Template Include Tests ==="
echo ""

# --- Test 1: Basic single include ---
echo "Test 1: basic single include"
TMPDIR_T1="$(mktemp -d)"
(
    mkdir -p "$TMPDIR_T1/templates"
    cat > "$TMPDIR_T1/templates/_partial.md" <<'EOF'
### Section Format
Use HTML comment markers.
EOF
    cat > "$TMPDIR_T1/templates/main.md" <<'EOF'
# Main Template
<!-- include: _partial.md -->
Rest of template.
EOF

    source "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh"
    source "$PROJECT_DIR/.aitask-scripts/lib/agentcrew_utils.sh"

    result="$(cat "$TMPDIR_T1/templates/main.md" | resolve_template_includes "$TMPDIR_T1/templates")"
    assert_contains_ci "include resolved" "Section Format" "$result"
    assert_contains_ci "include content present" "HTML comment markers" "$result"
    assert_not_contains_ci "directive removed" "<!-- include:" "$result"
    assert_contains_ci "surrounding content preserved" "Rest of template" "$result"
    assert_contains_ci "header preserved" "# Main Template" "$result"
)
rm -rf "$TMPDIR_T1"

# --- Test 2: Multiple includes ---
echo "Test 2: multiple includes"
TMPDIR_T2="$(mktemp -d)"
(
    mkdir -p "$TMPDIR_T2/templates"
    cat > "$TMPDIR_T2/templates/_header.md" <<'EOF'
HEADER CONTENT
EOF
    cat > "$TMPDIR_T2/templates/_footer.md" <<'EOF'
FOOTER CONTENT
EOF
    cat > "$TMPDIR_T2/templates/main.md" <<'EOF'
# Template
<!-- include: _header.md -->
Middle section.
<!-- include: _footer.md -->
End.
EOF

    source "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh"
    source "$PROJECT_DIR/.aitask-scripts/lib/agentcrew_utils.sh"

    result="$(cat "$TMPDIR_T2/templates/main.md" | resolve_template_includes "$TMPDIR_T2/templates")"
    assert_contains_ci "first include resolved" "HEADER CONTENT" "$result"
    assert_contains_ci "second include resolved" "FOOTER CONTENT" "$result"
    assert_contains_ci "middle preserved" "Middle section" "$result"
)
rm -rf "$TMPDIR_T2"

# --- Test 3: No includes (passthrough) ---
echo "Test 3: no includes passthrough"
TMPDIR_T3="$(mktemp -d)"
(
    cat > "$TMPDIR_T3/plain.md" <<'EOF'
# Plain Template
No include directives here.
Just plain content.
EOF

    source "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh"
    source "$PROJECT_DIR/.aitask-scripts/lib/agentcrew_utils.sh"

    result="$(cat "$TMPDIR_T3/plain.md" | resolve_template_includes "$TMPDIR_T3")"
    assert_contains_ci "content preserved" "No include directives" "$result"
    assert_contains_ci "all lines present" "Just plain content" "$result"
)
rm -rf "$TMPDIR_T3"

# --- Test 4: Missing include file ---
echo "Test 4: missing include file"
TMPDIR_T4="$(mktemp -d)"
(
    cat > "$TMPDIR_T4/broken.md" <<'EOF'
# Template
<!-- include: _nonexistent.md -->
After missing include.
EOF

    source "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh"
    source "$PROJECT_DIR/.aitask-scripts/lib/agentcrew_utils.sh"

    result="$(cat "$TMPDIR_T4/broken.md" | resolve_template_includes "$TMPDIR_T4" 2>/dev/null)"
    assert_contains_ci "directive preserved" "<!-- include: _nonexistent.md -->" "$result"
    assert_contains_ci "subsequent content preserved" "After missing include" "$result"

    # Verify warning is emitted to stderr
    stderr="$(cat "$TMPDIR_T4/broken.md" | resolve_template_includes "$TMPDIR_T4" 2>&1 1>/dev/null || true)"
    assert_contains_ci "warning emitted" "not found" "$stderr"
)
rm -rf "$TMPDIR_T4"

# ============================================================
# Tests: addwork integration with includes
# ============================================================

# --- Test 5: addwork resolves includes in work2do file ---
echo "Test 5: addwork resolves includes"
TMPDIR_T5="$(setup_test_repo)"
(
    cd "$TMPDIR_T5"
    bash .aitask-scripts/aitask_crew_init.sh --id incl --add-type impl:claudecode/opus4_6 --batch >/dev/null 2>&1

    mkdir -p /tmp/ait_test_templates
    cat > /tmp/ait_test_templates/_shared.md <<'EOF'
SHARED PARTIAL CONTENT
EOF
    cat > /tmp/ait_test_templates/work.md <<'EOF'
# Agent Work
<!-- include: _shared.md -->
Do the rest.
EOF

    output=$(bash .aitask-scripts/aitask_crew_addwork.sh --crew incl --name resolver --work2do /tmp/ait_test_templates/work.md --type impl --batch 2>&1)
    assert_contains_ci "addwork succeeds" "ADDED:resolver" "$output"

    work2do_content="$(cat .aitask-crews/crew-incl/resolver_work2do.md)"
    assert_contains_ci "include resolved in work2do" "SHARED PARTIAL CONTENT" "$work2do_content"
    assert_not_contains_ci "directive absent in work2do" "<!-- include:" "$work2do_content"
    assert_contains_ci "surrounding content in work2do" "Do the rest" "$work2do_content"

    rm -rf /tmp/ait_test_templates
)
cleanup_test_repo "$TMPDIR_T5"

# --- Test 6: stdin input skips include resolution ---
echo "Test 6: stdin skips include resolution"
TMPDIR_T6="$(setup_test_repo)"
(
    cd "$TMPDIR_T6"
    bash .aitask-scripts/aitask_crew_init.sh --id stdin --add-type impl:claudecode/opus4_6 --batch >/dev/null 2>&1

    output=$(echo '<!-- include: _nonexistent.md -->' | bash .aitask-scripts/aitask_crew_addwork.sh --crew stdin --name raw --work2do - --type impl --batch 2>&1)
    assert_contains_ci "addwork succeeds" "ADDED:raw" "$output"

    work2do_content="$(cat .aitask-crews/crew-stdin/raw_work2do.md)"
    assert_contains_ci "directive preserved for stdin" "<!-- include:" "$work2do_content"
)
cleanup_test_repo "$TMPDIR_T6"

# --- Test 7: Brainstorm-style integration ---
echo "Test 7: brainstorm-style section format include"
TMPDIR_T7="$(mktemp -d)"
(
    mkdir -p "$TMPDIR_T7/templates"
    cp "$PROJECT_DIR/.aitask-scripts/brainstorm/templates/_section_format.md" "$TMPDIR_T7/templates/"

    cat > "$TMPDIR_T7/templates/agent.md" <<'EOF'
# Task: Test Agent

## Output

<!-- include: _section_format.md -->

Write output to _output.md.
EOF

    source "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh"
    source "$PROJECT_DIR/.aitask-scripts/lib/agentcrew_utils.sh"

    result="$(cat "$TMPDIR_T7/templates/agent.md" | resolve_template_includes "$TMPDIR_T7/templates")"
    assert_contains_ci "section format heading present" "### Section Format" "$result"
    assert_contains_ci "section opening syntax present" "<!-- section: name" "$result"
    assert_contains_ci "section closing syntax present" "<!-- /section: name -->" "$result"
    assert_contains_ci "snake_case instruction present" "lowercase_snake_case" "$result"
    assert_not_contains_ci "include directive removed" "<!-- include: _section_format" "$result"
)
rm -rf "$TMPDIR_T7"

# --- Test 8: Multi-base-dir resolution (t818) ---
# resolve_template_includes accepts multiple base dirs and searches them in
# order; the first existing match wins. The capability is general
# infrastructure — useful when a brainstorm template wants to consume an
# include that lives outside its own templates dir (e.g., a future shared
# fragment in .aitask-scripts/skill_templates/). Production callers
# currently only need primary-dir resolution, but the multi-arg signature
# guards the bridge mechanism against silent regressions.
echo "Test 8: multi-base-dir resolution"
TMPDIR_T8="$(mktemp -d)"
(
    mkdir -p "$TMPDIR_T8/primary" "$TMPDIR_T8/fallback"

    cat > "$TMPDIR_T8/primary/_primary_only.md" <<'EOF'
PRIMARY_ONLY_CONTENT
EOF

    cat > "$TMPDIR_T8/fallback/_fallback_only.md" <<'EOF'
FALLBACK_ONLY_CONTENT
EOF

    cat > "$TMPDIR_T8/primary/agent.md" <<'EOF'
# Multi-include
<!-- include: _primary_only.md -->
Middle.
<!-- include: _fallback_only.md -->
End.
EOF

    source "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh"
    source "$PROJECT_DIR/.aitask-scripts/lib/agentcrew_utils.sh"

    result="$(cat "$TMPDIR_T8/primary/agent.md" | resolve_template_includes "$TMPDIR_T8/primary" "$TMPDIR_T8/fallback")"
    assert_contains_ci "primary-dir include resolved" "PRIMARY_ONLY_CONTENT" "$result"
    assert_contains_ci "fallback-dir include resolved" "FALLBACK_ONLY_CONTENT" "$result"
    assert_not_contains_ci "no residual directives" "<!-- include:" "$result"
    assert_contains_ci "middle preserved" "Middle." "$result"
    assert_contains_ci "end preserved" "End." "$result"

    # First-hit-wins: place a same-named file in the fallback dir; primary still wins.
    cat > "$TMPDIR_T8/fallback/_primary_only.md" <<'EOF'
FALLBACK_SHADOW_CONTENT
EOF
    result2="$(cat "$TMPDIR_T8/primary/agent.md" | resolve_template_includes "$TMPDIR_T8/primary" "$TMPDIR_T8/fallback")"
    assert_contains_ci "primary wins over fallback (same name)" "PRIMARY_ONLY_CONTENT" "$result2"
    assert_not_contains_ci "shadowed fallback content not used" "FALLBACK_SHADOW_CONTENT" "$result2"

    # Missing-in-all-dirs path: directive preserved + warning emitted.
    cat > "$TMPDIR_T8/primary/missing.md" <<'EOF'
<!-- include: _nowhere.md -->
EOF
    stderr_missing="$(cat "$TMPDIR_T8/primary/missing.md" | resolve_template_includes "$TMPDIR_T8/primary" "$TMPDIR_T8/fallback" 2>&1 1>/dev/null || true)"
    assert_contains_ci "missing-in-all-dirs warns" "not found in any base_dir" "$stderr_missing"
)
rm -rf "$TMPDIR_T8"

# --- Test 9: Production bridge — detailer.md consumes skill_templates fragment (t818) ---
# detailer.md's `## Rules` section is sourced from
# .aitask-scripts/skill_templates/_detailer_rules.md via the multi-base-dir
# resolver. This is the actual production cross-pipeline include — the
# brainstorm template lives in brainstorm/templates/ but pulls a fragment
# from the neutral skill_templates/ dir. Without this test, the bridge
# would only be exercised in synthetic fixtures (Test 8) and a regression
# could land that breaks production but passes the rest of the suite.
echo "Test 9: production bridge — detailer.md → skill_templates/_detailer_rules.md"
(
    source "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh"
    source "$PROJECT_DIR/.aitask-scripts/lib/agentcrew_utils.sh"

    # WITH the skill_templates fallback dir: the include resolves and the
    # rules section is materialized verbatim inside detailer.md.
    resolved="$(cat "$PROJECT_DIR/.aitask-scripts/brainstorm/templates/detailer.md" \
        | resolve_template_includes \
            "$PROJECT_DIR/.aitask-scripts/brainstorm/templates" \
            "$PROJECT_DIR/.aitask-scripts/skill_templates" 2>/dev/null)"
    assert_contains_ci "rules fragment resolved (rule 1 prose)" \
        "Be maximally specific" "$resolved"
    assert_contains_ci "rules fragment resolved (rule 3 prose)" \
        "Every assumption from the node's YAML" "$resolved"
    assert_contains_ci "rules fragment resolved (rule 5 prose)" \
        "Do not include architectural discussion" "$resolved"
    assert_not_contains_ci "rules include directive removed" \
        "<!-- include: _detailer_rules.md -->" "$resolved"

    # Brainstorm section markers MUST remain in their original positions —
    # the bash resolver only touches `<!-- include: -->` directives, never
    # `<!-- section: -->` markers. If a future change relocates a marker
    # into a fragment, brainstorm's section parser breaks silently.
    assert_contains_ci "section marker 'prerequisites' preserved" \
        "<!-- section: prerequisites -->" "$resolved"
    # `[...]` in grep BRE is a character class; check the bare section name
    # plus the closing marker and rely on Test 9's overall resolved-output
    # diff for full-fidelity dimension-attribute coverage.
    assert_contains_ci "section marker 'step_by_step' opening preserved" \
        "section: step_by_step " "$resolved"
    assert_contains_ci "section marker 'step_by_step' closing preserved" \
        "/section: step_by_step" "$resolved"
    assert_contains_ci "section marker 'verification' opening preserved" \
        "section: verification " "$resolved"
    assert_contains_ci "section marker 'verification' closing preserved" \
        "/section: verification" "$resolved"
    # Spot-check the dimension attribute survives (escape brackets via word match).
    assert_contains_ci "step_by_step dimensions attribute present" \
        "dimensions: component_" "$resolved"
    assert_contains_ci "verification dimensions attribute present" \
        "dimensions: assumption_" "$resolved"

    # WITHOUT the skill_templates fallback: the include cannot be resolved
    # (proves the fragment really lives in skill_templates/, not in
    # brainstorm/templates/ — guards against an accidental copy/move).
    stderr_only_primary="$(cat "$PROJECT_DIR/.aitask-scripts/brainstorm/templates/detailer.md" \
        | resolve_template_includes "$PROJECT_DIR/.aitask-scripts/brainstorm/templates" \
            2>&1 1>/dev/null || true)"
    assert_contains_ci "warn when skill_templates fallback omitted" \
        "_detailer_rules.md" "$stderr_only_primary"
    assert_contains_ci "warn message is the missing-include path" \
        "not found in any base_dir" "$stderr_only_primary"
)

# ============================================================
# Summary
# ============================================================

read -r PASS FAIL TOTAL < "$COUNTER_FILE"

echo ""
echo "=== Results ==="
echo "PASS: $PASS"
echo "FAIL: $FAIL"
echo "TOTAL: $TOTAL"

if [[ $FAIL -gt 0 ]]; then
    echo "SOME TESTS FAILED"
    exit 1
else
    echo "ALL TESTS PASSED"
fi
