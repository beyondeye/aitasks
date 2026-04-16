#!/usr/bin/env bash
# test_crew_template_includes.sh - Tests for <!-- include: filename --> template resolution.
# Run: bash tests/test_crew_template_includes.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
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

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    if [[ "$expected" == "$actual" ]]; then
        _inc_pass
    else
        _inc_fail
        echo "FAIL: $desc (expected '$expected', got '$actual')"
    fi
}

assert_contains() {
    local desc="$1" expected="$2" actual="$3"
    if echo "$actual" | grep -qi "$expected"; then
        _inc_pass
    else
        _inc_fail
        echo "FAIL: $desc (expected output containing '$expected', got '$actual')"
    fi
}

assert_not_contains() {
    local desc="$1" unexpected="$2" actual="$3"
    if echo "$actual" | grep -qi "$unexpected"; then
        _inc_fail
        echo "FAIL: $desc (output should NOT contain '$unexpected')"
    else
        _inc_pass
    fi
}

assert_file_exists() {
    local desc="$1" file="$2"
    if [[ -f "$file" ]]; then
        _inc_pass
    else
        _inc_fail
        echo "FAIL: $desc (file '$file' does not exist)"
    fi
}

# --- Setup: create isolated git repo ---

setup_test_repo() {
    local tmpdir
    tmpdir="$(mktemp -d)"

    (
        cd "$tmpdir"
        git init --quiet
        git config user.email "test@test.com"
        git config user.name "Test"

        mkdir -p .aitask-scripts/lib aitasks/metadata

        cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" .aitask-scripts/lib/
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
    assert_contains "include resolved" "Section Format" "$result"
    assert_contains "include content present" "HTML comment markers" "$result"
    assert_not_contains "directive removed" "<!-- include:" "$result"
    assert_contains "surrounding content preserved" "Rest of template" "$result"
    assert_contains "header preserved" "# Main Template" "$result"
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
    assert_contains "first include resolved" "HEADER CONTENT" "$result"
    assert_contains "second include resolved" "FOOTER CONTENT" "$result"
    assert_contains "middle preserved" "Middle section" "$result"
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
    assert_contains "content preserved" "No include directives" "$result"
    assert_contains "all lines present" "Just plain content" "$result"
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
    assert_contains "directive preserved" "<!-- include: _nonexistent.md -->" "$result"
    assert_contains "subsequent content preserved" "After missing include" "$result"

    # Verify warning is emitted to stderr
    stderr="$(cat "$TMPDIR_T4/broken.md" | resolve_template_includes "$TMPDIR_T4" 2>&1 1>/dev/null || true)"
    assert_contains "warning emitted" "not found" "$stderr"
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
    assert_contains "addwork succeeds" "ADDED:resolver" "$output"

    work2do_content="$(cat .aitask-crews/crew-incl/resolver_work2do.md)"
    assert_contains "include resolved in work2do" "SHARED PARTIAL CONTENT" "$work2do_content"
    assert_not_contains "directive absent in work2do" "<!-- include:" "$work2do_content"
    assert_contains "surrounding content in work2do" "Do the rest" "$work2do_content"

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
    assert_contains "addwork succeeds" "ADDED:raw" "$output"

    work2do_content="$(cat .aitask-crews/crew-stdin/raw_work2do.md)"
    assert_contains "directive preserved for stdin" "<!-- include:" "$work2do_content"
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
    assert_contains "section format heading present" "### Section Format" "$result"
    assert_contains "section opening syntax present" "<!-- section: name" "$result"
    assert_contains "section closing syntax present" "<!-- /section: name -->" "$result"
    assert_contains "snake_case instruction present" "lowercase_snake_case" "$result"
    assert_not_contains "include directive removed" "<!-- include: _section_format" "$result"
)
rm -rf "$TMPDIR_T7"

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
