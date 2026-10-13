#!/usr/bin/env bash
# test_fold_content.sh - Tests for aitask_fold_content.sh
#
# Covers:
#   - Positional <primary_file> form produces merged body
#   - --primary-stdin form matches positional form when stdin = primary body
#   - Filename parsing: t12_simple, t16_2_child, t100_multi_word_name
#   - Frontmatter correctly stripped
#   - "## Folded Tasks" section references each folded task with filename
#   - Folded tasks' "## Inbox" / "## Gate Runs" land under "## Folded History",
#     inert to the real ledger parsers and cut from task-declared text (t1962)
#   - The primary's own ledgers stay last; a re-fold reuses Folded History
#   - --primary-stdin strips only a recognizable, closed task frontmatter
#
# Run: bash tests/test_fold_content.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

# Shared core helpers (assert_eq, assert_contains, …) live in tests/lib/asserts.sh.
. "$PROJECT_DIR/tests/lib/asserts.sh"

setup_project() {
    local tmpdir
    tmpdir="$(mktemp -d)"
    CLEANUP_DIRS+=("$tmpdir")

    pushd "$tmpdir" > /dev/null || exit 1

    mkdir -p aitasks
    setup_fake_aitask_repo "$PWD"
    cp "$PROJECT_DIR/.aitask-scripts/aitask_fold_content.sh" .aitask-scripts/
    # Marker neutralization runs ledger_block's own grammar (t1962).
    cp "$PROJECT_DIR/.aitask-scripts/lib/ledger_block.py" .aitask-scripts/lib/
    chmod +x .aitask-scripts/*.sh

    PROJECT_UNDER_TEST="$tmpdir"
}

teardown() {
    popd > /dev/null 2>&1 || true
}

write_task() {
    local path="$1"
    local body="$2"
    mkdir -p "$(dirname "$path")"
    cat > "$path" << EOF
---
priority: medium
effort: low
status: Ready
---

${body}
EOF
}

test_positional_basic() {
    echo "=== Test: positional primary file ==="
    setup_project
    write_task aitasks/t12_simple.md "Primary body content"
    write_task aitasks/t13_other.md "Folded content"

    local output
    output=$(bash .aitask-scripts/aitask_fold_content.sh aitasks/t12_simple.md aitasks/t13_other.md)

    assert_contains "primary body preserved" "Primary body content" "$output"
    assert_contains "merged header for folded task" "## Merged from t13: other" "$output"
    assert_contains "folded body preserved" "Folded content" "$output"
    assert_contains "folded tasks section header" "## Folded Tasks" "$output"
    assert_contains "folded tasks reference line" "**t13** (\`t13_other.md\`)" "$output"
    assert_not_contains "frontmatter marker not leaked" "priority: medium" "$output"

    teardown
}

test_stdin_form() {
    echo "=== Test: --primary-stdin form ==="
    setup_project
    write_task aitasks/t20_folded.md "Stdin folded"

    local body="Stdin primary body"
    local output
    output=$(echo "$body" | bash .aitask-scripts/aitask_fold_content.sh --primary-stdin aitasks/t20_folded.md)

    assert_contains "stdin primary body preserved" "Stdin primary body" "$output"
    assert_contains "folded header" "## Merged from t20: folded" "$output"
    assert_contains "folded body" "Stdin folded" "$output"

    teardown
}

test_filename_parsing() {
    echo "=== Test: filename parsing variants ==="
    setup_project
    write_task aitasks/t12_simple.md "B12"
    write_task aitasks/t16/t16_2_child.md "B16c"
    write_task aitasks/t100_multi_word_name.md "B100"
    write_task aitasks/t1_primary.md "Primary"

    local output
    output=$(bash .aitask-scripts/aitask_fold_content.sh \
        aitasks/t1_primary.md \
        aitasks/t12_simple.md \
        aitasks/t16/t16_2_child.md \
        aitasks/t100_multi_word_name.md)

    assert_contains "parent id t12 'simple'" "## Merged from t12: simple" "$output"
    assert_contains "child id t16_2 'child'" "## Merged from t16_2: child" "$output"
    assert_contains "multi-word name normalized" "## Merged from t100: multi word name" "$output"
    assert_contains "ref to t16_2 child file" "**t16_2** (\`t16_2_child.md\`)" "$output"

    teardown
}

test_frontmatter_stripped() {
    echo "=== Test: frontmatter stripped from all inputs ==="
    setup_project
    write_task aitasks/t70_prim.md "Prim body"
    write_task aitasks/t71_a.md "A body"
    write_task aitasks/t72_b.md "B body"

    local output
    output=$(bash .aitask-scripts/aitask_fold_content.sh aitasks/t70_prim.md aitasks/t71_a.md aitasks/t72_b.md)

    assert_not_contains "no priority field" "priority: medium" "$output"
    assert_not_contains "no effort field" "effort: low" "$output"
    assert_not_contains "no status field" "status: Ready" "$output"

    teardown
}

# --- Ledger isolation (t1962) ------------------------------------------------

# Run a python snippet against the REAL ledger / path libs, with $1 on stdin.
py_lib() {
    local text="$1" code="$2"
    printf '%s' "$text" | python3 -c "
import sys
sys.path.insert(0, '$PROJECT_DIR/.aitask-scripts/lib')
import gate_ledger, note_inbox, plan_paths
out = sys.stdin.read()
$code"
}

# A folded task carrying a declared path, bold-quote prose, an inbox (note +
# receipt) and a gate ledger whose body names a path.
write_folded_with_ledgers() {
    write_task "$1" "Folded needs src/required.py
> **Note:** keep

## Inbox

<!-- Appended by the note framework. Do not edit by hand; use \`./ait note\`. -->

> **✉ note:t5** id=2026-10-12T10:00:00Z.0123456789abcdef01234567 at=2026-10-12T10:00:00Z
>
> | see src/unrelated.py

> **👁 note:read** id=2026-10-12T11:00:00Z.0123456789abcdef01234568 by=t13 at=2026-10-12T11:00:00Z mode=explicit ids=2026-10-12T10:00:00Z.0123456789abcdef01234567

## Gate Runs

> **✅ gate:plan_approved** run=2026-10-12T09:00:00Z status=pass attempt=1 type=human
>
> Log: logs/old_review.md

> **❌ gate:plan_approved** run=2026-10-12T09:30:00Z status=fail attempt=2 type=human"
}

# A primary with its own inbox and one gate run.
write_primary_with_ledgers() {
    write_task "$1" "Primary body a/b.py

## Inbox

> **✉ note:t3** id=2026-10-12T08:00:00Z.0123456789abcdef01234569 at=2026-10-12T08:00:00Z
>
> | primary note

## Gate Runs

> **✅ gate:plan_approved** run=2026-10-12T08:30:00Z status=pass attempt=1 type=human"
}

# 1-based line number of the first line equal to $1 in $2 (0 if absent).
line_of() {
    local n
    n=$(printf '%s\n' "$2" | grep -nxF -m1 -- "$1" | cut -d: -f1)
    echo "${n:-0}"
}

test_folded_ledgers_inert() {
    echo "=== Test: folded ledgers are demoted and inert ==="
    setup_project
    write_task aitasks/t12_simple.md "Primary body"
    write_folded_with_ledgers aitasks/t13_other.md

    local output
    output=$(bash .aitask-scripts/aitask_fold_content.sh aitasks/t12_simple.md aitasks/t13_other.md)

    assert_eq "no bare Gate Runs header" "0" \
        "$(printf '%s\n' "$output" | grep -cE '^##[[:space:]]+Gate Runs[[:space:]]*$' || true)"
    assert_eq "no bare Inbox header" "0" \
        "$(printf '%s\n' "$output" | grep -cE '^##[[:space:]]+Inbox[[:space:]]*$' || true)"
    assert_contains "history section" "## Folded History" "$output"
    assert_contains "history entry" "### t13: other" "$output"
    assert_contains "shifted gate heading" "#### Gate Runs" "$output"
    assert_contains "shifted inbox heading" "#### Inbox" "$output"
    assert_contains "gate marker neutralized" "> | **✅ gate:plan_approved**" "$output"
    assert_contains "receipt neutralized" "> | **👁 note:read**" "$output"
    assert_contains "bold prose untouched" "> **Note:** keep" "$output"
    assert_eq "real parser: no gate runs" "0" \
        "$(py_lib "$output" 'print(len(gate_ledger.parse_gate_run_blocks(out)))')"
    assert_eq "real parser: no note blocks" "0" \
        "$(py_lib "$output" 'print(len(note_inbox.parse(out)))')"
    assert_eq "real parser: no inbox section" "False" \
        "$(py_lib "$output" 'print(note_inbox.has_section(out))')"

    teardown
}

test_folded_history_excluded_from_declared_text() {
    echo "=== Test: folded history is not task-declared text ==="
    setup_project
    write_task aitasks/t12_simple.md "Primary body"
    write_folded_with_ledgers aitasks/t13_other.md

    local output declared
    output=$(bash .aitask-scripts/aitask_fold_content.sh aitasks/t12_simple.md aitasks/t13_other.md)
    declared=$(py_lib "$output" 'print(" ".join(plan_paths.extract(plan_paths.task_body_text(out))))')

    assert_contains "merged requirement path declared" "src/required.py" "$declared"
    assert_not_contains "folded note path not declared" "src/unrelated.py" "$declared"
    assert_not_contains "folded gate log path not declared" "logs/old_review.md" "$declared"

    teardown
}

test_primary_ledger_stays_terminal() {
    echo "=== Test: the primary's own ledgers stay last ==="
    setup_project
    write_primary_with_ledgers aitasks/t12_simple.md
    write_folded_with_ledgers aitasks/t13_other.md

    local output merged folded history inbox gates
    output=$(bash .aitask-scripts/aitask_fold_content.sh aitasks/t12_simple.md aitasks/t13_other.md)
    merged=$(line_of "## Merged from t13: other" "$output")
    folded=$(line_of "## Folded Tasks" "$output")
    history=$(line_of "## Folded History" "$output")
    inbox=$(line_of "## Inbox" "$output")
    gates=$(line_of "## Gate Runs" "$output")

    assert_eq "order: merged < folded tasks < history < inbox < gate runs" "yes" \
        "$( (( 0 < merged && merged < folded && folded < history && history < inbox && inbox < gates )) && echo yes || echo "no: $merged $folded $history $inbox $gates")"
    assert_eq "real parser: only the primary's gate run" "1" \
        "$(py_lib "$output" 'print(len(gate_ledger.parse_gate_run_blocks(out)))')"
    assert_eq "real parser: only the primary's note" "1" \
        "$(py_lib "$output" 'print(len(note_inbox.parse(out)))')"
    assert_contains "merged requirement still declared" "src/required.py" \
        "$(py_lib "$output" 'print(" ".join(plan_paths.extract(plan_paths.task_body_text(out))))')"

    teardown
}

test_refold_reuses_folded_history() {
    echo "=== Test: a primary's existing Folded History receives the new entries ==="
    setup_project
    write_task aitasks/t12_simple.md "Primary body

## Folded History

Reference only.

### t9: earlier

#### Gate Runs

> | **✅ gate:plan_approved** status=pass

## Gate Runs

> **✅ gate:plan_approved** run=2026-10-12T08:30:00Z status=pass attempt=1 type=human"
    write_folded_with_ledgers aitasks/t13_other.md

    local output history t9 t13 gates
    output=$(bash .aitask-scripts/aitask_fold_content.sh aitasks/t12_simple.md aitasks/t13_other.md)
    history=$(line_of "## Folded History" "$output")
    t9=$(line_of "### t9: earlier" "$output")
    t13=$(line_of "### t13: other" "$output")
    gates=$(line_of "## Gate Runs" "$output")

    assert_eq "exactly one Folded History" "1" \
        "$(printf '%s\n' "$output" | grep -cxF '## Folded History')"
    assert_eq "order: history < t9 < t13 < gate runs" "yes" \
        "$( (( 0 < history && history < t9 && t9 < t13 && t13 < gates )) && echo yes || echo "no: $history $t9 $t13 $gates")"
    assert_eq "real parser: only the primary's gate run" "1" \
        "$(py_lib "$output" 'print(len(gate_ledger.parse_gate_run_blocks(out)))')"

    teardown
}

test_stdin_whole_task_file() {
    echo "=== Test: --primary-stdin strips a whole task file's frontmatter ==="
    setup_project
    write_task aitasks/t12_simple.md "Primary body content"
    write_task aitasks/t13_other.md "Folded content"

    local positional stdin_out
    positional=$(bash .aitask-scripts/aitask_fold_content.sh aitasks/t12_simple.md aitasks/t13_other.md)
    stdin_out=$(bash .aitask-scripts/aitask_fold_content.sh --primary-stdin aitasks/t13_other.md < aitasks/t12_simple.md)

    assert_eq "stdin output equals positional output" "$positional" "$stdin_out"
    assert_not_contains "no frontmatter leaked" "priority: medium" "$stdin_out"

    teardown
}

test_stdin_commented_frontmatter() {
    echo "=== Test: --primary-stdin strips frontmatter carrying a YAML comment ==="
    setup_project
    cat > aitasks/t12_simple.md << 'EOF'
---
# Metadata annotation
priority: medium
effort: low
status: Ready
---

Primary body content
EOF
    write_task aitasks/t13_other.md "Folded content"

    local positional stdin_out
    positional=$(bash .aitask-scripts/aitask_fold_content.sh aitasks/t12_simple.md aitasks/t13_other.md)
    stdin_out=$(bash .aitask-scripts/aitask_fold_content.sh --primary-stdin aitasks/t13_other.md < aitasks/t12_simple.md)

    assert_eq "stdin output equals positional output" "$positional" "$stdin_out"
    assert_not_contains "comment stripped" "# Metadata annotation" "$stdin_out"
    assert_not_contains "frontmatter stripped" "priority: medium" "$stdin_out"

    teardown
}

test_stdin_leading_rule_preserved() {
    echo "=== Test: --primary-stdin keeps a description that opens with a rule ==="
    setup_project
    write_task aitasks/t13_other.md "Folded content"

    local input output
    input=$'---\nKeep this requirement.'
    output=$(printf '%s\n' "$input" | bash .aitask-scripts/aitask_fold_content.sh --primary-stdin aitasks/t13_other.md)
    assert_eq "unclosed rule: text kept in full" "$input" "$(printf '%s\n' "$output" | head -n 2)"

    input=$'---\nNote: x\n---\nKeep y'
    output=$(printf '%s\n' "$input" | bash .aitask-scripts/aitask_fold_content.sh --primary-stdin aitasks/t13_other.md)
    assert_eq "closed rules without task keys: text kept in full" "$input" "$(printf '%s\n' "$output" | head -n 4)"

    teardown
}

test_large_history_refold() {
    echo "=== Test: a large folded history refolds without losing the primary's ledgers ==="
    setup_project
    write_task aitasks/t12_simple.md "Primary body

## Folded History

Reference only.

### t9: earlier

#### Gate Runs

> | **✅ gate:plan_approved** status=pass

## Gate Runs

> **✅ gate:plan_approved** run=2026-10-12T08:30:00Z status=pass attempt=1 type=human"
    local big i
    big="Folded body

## Gate Runs
"
    for ((i = 0; i < 3000; i++)); do
        big+=$'\n'"> **✅ gate:g${i}** run=2026-10-12T09:00:00Z status=pass attempt=1 type=machine padding_padding"
    done
    write_task aitasks/t13_other.md "$big"

    local output rc=0
    output=$(bash .aitask-scripts/aitask_fold_content.sh aitasks/t12_simple.md aitasks/t13_other.md) || rc=$?
    assert_eq "exit status 0" "0" "$rc"
    assert_eq "history is large (>128 KiB)" "yes" "$( (( ${#output} > 131072 )) && echo yes || echo "no: ${#output}")"
    assert_contains "earlier entry kept" "### t9: earlier" "$output"
    assert_contains "new entry added" "### t13: other" "$output"
    assert_eq "primary Gate Runs kept" "1" "$(printf '%s\n' "$output" | grep -cxF '## Gate Runs')"
    assert_eq "real parser: only the primary's gate run" "1" \
        "$(py_lib "$output" 'print(len(gate_ledger.parse_gate_run_blocks(out)))')"

    teardown
}

test_unicode_whitespace_markers_inert() {
    echo "=== Test: markers the parser reads through Unicode whitespace are neutralized ==="
    setup_project
    write_task aitasks/t12_simple.md "Primary body"
    local nbsp=$'\xc2\xa0' lsep=$'\xe2\x80\xa8'
    write_task aitasks/t13_other.md "Folded body
> **Note:** keep

## Gate Runs

> **✅${nbsp}gate:plan_approved** run=2026-10-12T09:00:00Z status=pass attempt=1 type=human
prose${lsep}> **❌ gate:plan_approved** run=2026-10-12T09:30:00Z status=fail attempt=2 type=human"

    local folded_runs output
    folded_runs=$(py_lib "$(cat aitasks/t13_other.md)" 'print(len(gate_ledger.parse_gate_run_blocks(out)))')
    assert_eq "fixture: the parser reads both markers" "2" "$folded_runs"
    output=$(bash .aitask-scripts/aitask_fold_content.sh aitasks/t12_simple.md aitasks/t13_other.md)
    assert_eq "real parser: no gate runs after the fold" "0" \
        "$(py_lib "$output" 'print(len(gate_ledger.parse_gate_run_blocks(out)))')"
    assert_contains "bold prose untouched" "> **Note:** keep" "$output"

    teardown
}

test_failure_leaves_stdout_empty() {
    echo "=== Test: a failure part-way emits nothing ==="
    setup_project
    write_task aitasks/t12_simple.md "Primary body"
    write_task aitasks/t13_other.md "Folded content"

    local output rc=0
    output=$(bash .aitask-scripts/aitask_fold_content.sh aitasks/t12_simple.md \
        aitasks/t13_other.md aitasks/t99_missing.md 2>/dev/null) || rc=$?
    assert_eq "non-zero exit" "1" "$rc"
    assert_eq "no partial body on stdout" "" "$output"

    teardown
}

# Risk mitigation pin_framework_header_parity: the script must route a folded
# tail into "## Folded History" for EVERY header plan_paths cuts at, read from
# the owning modules -- a header added on one side only fails here.
test_framework_header_parity() {
    echo "=== Test: script recognizes every plan_paths framework header ==="
    setup_project
    write_task aitasks/t12_simple.md "Primary body"

    local headers header output
    headers=$(py_lib "" 'print("\n".join((plan_paths.FOLDED_HISTORY_HEADER, note_inbox.SECTION_HEADER, gate_ledger.SECTION_HEADER)))')
    assert_eq "three cut headers" "3" "$(printf '%s\n' "$headers" | grep -c '^## ')"
    while IFS= read -r header; do
        [[ -n "$header" ]] || continue
        write_task aitasks/t13_other.md "Folded body

${header}

> | ledger text"
        output=$(bash .aitask-scripts/aitask_fold_content.sh aitasks/t12_simple.md aitasks/t13_other.md)
        assert_contains "'${header}' routed to history" "#### ${header#\#\# }" "$output"
        assert_eq "'${header}' cut from declared text" "no" \
            "$(py_lib "$output" 'print("yes" if "ledger text" in plan_paths.task_body_text(out) else "no")')"
    done <<< "$headers"

    teardown
}

teardown_all() {
    local d
    for d in "${CLEANUP_DIRS[@]}"; do
        [[ -d "$d" ]] && rm -rf "$d"
    done
}
trap teardown_all EXIT

test_positional_basic
test_stdin_form
test_filename_parsing
test_frontmatter_stripped
test_folded_ledgers_inert
test_folded_history_excluded_from_declared_text
test_primary_ledger_stays_terminal
test_refold_reuses_folded_history
test_stdin_whole_task_file
test_stdin_commented_frontmatter
test_stdin_leading_rule_preserved
test_framework_header_parity
test_large_history_refold
test_unicode_whitespace_markers_inert
test_failure_leaves_stdout_empty

echo ""
echo "=========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=========================="
[[ "$FAIL" -eq 0 ]] || exit 1
