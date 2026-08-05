#!/usr/bin/env bash
# test_board_column_cli.sh - CLI contract for aitask_board_column.sh (t1377_1).
#
# The shell layer is where an operator or a TUI actually supplies --root,
# --task-dir and --task, so the boundary checks are asserted HERE and not only
# in the Python suite (tests/test_board_columns_seam.py). A Python-only test
# would not cover the real entry point.
#
# Covers: all three subcommands; the `|`-delimited record shape (title LAST,
# because titles may legitimately contain `|`); non-zero exit plus a machine
# `ERROR:<reason>` line for every refusal; the four identifier cases (malformed
# incl. a literal `*` that must not glob, ambiguous, child, missing); and
# --task-dir containment, with a canary planted OUTSIDE --root that must survive.
#
# Run: bash tests/test_board_column_cli.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

COLUMN_SH="$PROJECT_DIR/.aitask-scripts/aitask_board_column.sh"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/ait_board_col_XXXXXX")"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

PROJ="$TMP/proj"
OUTSIDE="$TMP/outside"
CANARY="$OUTSIDE/canary.txt"

# --- Fixture -----------------------------------------------------------------
# Hand-built rather than borrowed from tests/lib/board_fixture.py: this suite is
# about the shell boundary, so the tree stays readable in one screen.

build_tree() {
    local task_dir="$1"
    mkdir -p "$PROJ/$task_dir/metadata" "$PROJ/$task_dir/t100"
    # `Col|One` deliberately carries a pipe: it proves the title is the LAST
    # field and that a parser must split on the first two separators only.
    cat > "$PROJ/$task_dir/metadata/board_config.json" <<'JSON'
{
  "columns": [
    {"id": "c0", "title": "Col|One", "color": "#FF5555"},
    {"id": "c1", "title": "Col Two", "color": "#50FA7B"}
  ],
  "column_order": ["c0", "c1"]
}
JSON
    cat > "$PROJ/$task_dir/t100_alpha.md" <<'MD'
---
priority: medium
issue_type: chore
status: Ready
boardcol: c0
boardidx: 10
---

## Context

Fixture task.
MD
    cat > "$PROJ/$task_dir/t100/t100_1_child.md" <<'MD'
---
priority: medium
issue_type: chore
status: Ready
boardcol: c0
boardidx: 20
---

## Context

Fixture child.
MD
}

tree_checksum() {
    find "$PROJ" -type f -exec sha256sum {} + 2>/dev/null | sort | sha256sum
}

mkdir -p "$OUTSIDE"
echo "untouched" > "$CANARY"
build_tree "aitasks"

echo "=== Test 1: list-columns ==="
out="$("$COLUMN_SH" list-columns --root "$PROJ" 2>&1)"; rc=$?
assert_eq "list-columns exits 0" "0" "$rc"
assert_contains "emits c0 with colour then title" "COLUMN:c0|#FF5555|Col|One" "$out"
assert_contains "emits c1" "COLUMN:c1|#50FA7B|Col Two" "$out"
assert_not_contains "unordered absent by default" "COLUMN:unordered" "$out"

# Title LAST is the whole point: cutting at the first two separators must
# recover the full title even though it contains a pipe.
line="$(printf '%s\n' "$out" | grep '^COLUMN:c0|')"
recovered="$(printf '%s' "${line#COLUMN:}" | cut -d'|' -f3-)"
assert_eq "title survives its own pipe" "Col|One" "$recovered"

echo "=== Test 2: --include-unordered ==="
out="$("$COLUMN_SH" list-columns --root "$PROJ" --include-unordered 2>&1)"
assert_contains "unordered listed" "COLUMN:unordered|gray|Unsorted / Inbox" "$out"
assert_eq "unordered is first" "COLUMN:unordered|gray|Unsorted / Inbox" \
    "$(printf '%s\n' "$out" | head -1)"

echo "=== Test 2b: CR/LF and pipe in the emitted fields (t1433) ==="
# Test 1 proves `|` survives the LAST field. It says nothing about CR/LF, which
# is the half t1433 changed: the shared `sanitize_last_field` collapses a CRLF
# to ONE space (board_columns' old private `_line_safe` left two). Asserting
# that through `bc.sanitize_last_field` would only prove the FUNCTION; this
# proves the CLI writer still places the title last AND runs it through that
# sanitizer, decoded by the documented fixed max-split rule.
CRLF_CONF="$PROJ/aitasks/metadata/board_config.json"
cp "$CRLF_CONF" "$TMP/board_config.orig.json"
cat > "$CRLF_CONF" <<'JSON'
{
  "columns": [{"id": "crlf", "title": "A|B\r\nC", "color": "#FF|00\r00"}],
  "column_order": ["crlf"]
}
JSON
out="$("$COLUMN_SH" list-columns --root "$PROJ" 2>&1)"; rc=$?
assert_eq "CRLF title: list-columns still exits 0" "0" "$rc"
assert_eq "CRLF title does not split the record" "1" \
    "$(printf '%s\n' "$out" | grep -c '^COLUMN:crlf|')"

line="$(printf '%s\n' "$out" | grep '^COLUMN:crlf|')"
recovered="$(printf '%s' "${line#COLUMN:}" | cut -d'|' -f3-)"
assert_eq "title keeps its pipe and collapses CRLF to ONE space" "A|B C" "$recovered"

# The colour is a MIDDLE field, so it must lose BOTH reserved characters —
# otherwise a stray `|` would shift the title field and the decode above would
# recover the wrong text.
colour="$(printf '%s' "${line#COLUMN:}" | cut -d'|' -f2)"
assert_eq "middle colour field is stripped of its pipe and CR" "#FF00 00" "$colour"

cp "$TMP/board_config.orig.json" "$CRLF_CONF"

echo "=== Test 3: current-column ==="
out="$("$COLUMN_SH" current-column --root "$PROJ" --task 100 2>&1)"; rc=$?
assert_eq "current-column exits 0" "0" "$rc"
assert_eq "reports the task's column" "CURRENT:100|c0" "$out"

echo "=== Test 4: move ==="
out="$("$COLUMN_SH" move --root "$PROJ" --task 100 --column c1 2>&1)"; rc=$?
assert_eq "move exits 0" "0" "$rc"
assert_contains "reports filename, column and index" "MOVED:t100_alpha.md|c1|" "$out"
assert_contains "boardcol written" "boardcol: c1" "$(cat "$PROJ/aitasks/t100_alpha.md")"
out="$("$COLUMN_SH" current-column --root "$PROJ" --task 100 2>&1)"
assert_eq "the move is observable" "CURRENT:100|c1" "$out"

echo "=== Test 5: unknown column ==="
before="$(tree_checksum)"
out="$("$COLUMN_SH" move --root "$PROJ" --task 100 --column nope 2>&1)"; rc=$?
assert_exit_nonzero_rc "unknown column exits non-zero" "$rc"
assert_contains "reports unknown_column" "ERROR:unknown_column" "$out"
assert_eq "tree unchanged" "$before" "$(tree_checksum)"

echo "=== Test 6: the four identifier cases ==="
# Malformed. `--task '*'` is the important one: without the digits-only gate it
# would glob t*_*.md and hit a real task file.
for bad in '*' '1*' '../etc' 't100' '42.5' ''; do
    before="$(tree_checksum)"
    out="$("$COLUMN_SH" move --root "$PROJ" --task "$bad" --column c0 2>&1)"; rc=$?
    assert_exit_nonzero_rc "malformed '$bad' exits non-zero" "$rc"
    assert_contains "malformed '$bad' reports reason" "ERROR:malformed_task_id" "$out"
    assert_eq "malformed '$bad' wrote nothing" "$before" "$(tree_checksum)"
done

before="$(tree_checksum)"
out="$("$COLUMN_SH" move --root "$PROJ" --task 100_1 --column c1 2>&1)"; rc=$?
assert_exit_nonzero_rc "child id exits non-zero" "$rc"
assert_contains "child id reports reason" "ERROR:not_a_parent_task" "$out"
assert_eq "child id wrote nothing" "$before" "$(tree_checksum)"

before="$(tree_checksum)"
out="$("$COLUMN_SH" move --root "$PROJ" --task 99999 --column c1 2>&1)"; rc=$?
assert_exit_nonzero_rc "missing task exits non-zero" "$rc"
assert_contains "missing task reports reason" "ERROR:not_found" "$out"
assert_eq "missing task wrote nothing" "$before" "$(tree_checksum)"

cp "$PROJ/aitasks/t100_alpha.md" "$PROJ/aitasks/t200_one.md"
cp "$PROJ/aitasks/t100_alpha.md" "$PROJ/aitasks/t200_two.md"
before="$(tree_checksum)"
out="$("$COLUMN_SH" move --root "$PROJ" --task 200 --column c1 2>&1)"; rc=$?
assert_exit_nonzero_rc "ambiguous id exits non-zero" "$rc"
assert_contains "ambiguous id reports reason" "ERROR:ambiguous_task_id" "$out"
assert_eq "ambiguous id wrote nothing" "$before" "$(tree_checksum)"
rm -f "$PROJ/aitasks/t200_one.md" "$PROJ/aitasks/t200_two.md"

echo "=== Test 7: --task-dir containment (the mutation boundary) ==="
for bad in "/etc" "../outside" "a/../../outside" ""; do
    before="$(tree_checksum)"
    out="$("$COLUMN_SH" move --root "$PROJ" --task-dir "$bad" --task 100 \
        --column c1 2>&1)"; rc=$?
    assert_exit_nonzero_rc "task-dir '$bad' exits non-zero" "$rc"
    assert_contains "task-dir '$bad' reports reason" "ERROR:unsafe_task_dir" "$out"
    assert_eq "task-dir '$bad' wrote nothing" "$before" "$(tree_checksum)"
done
assert_eq "canary outside --root untouched" "untouched" "$(cat "$CANARY")"
assert_file_exists "canary still present" "$CANARY"

out="$("$COLUMN_SH" list-columns --root "$PROJ" --task-dir /etc 2>&1)"; rc=$?
assert_exit_nonzero_rc "list-columns rejects absolute task-dir" "$rc"
assert_contains "list-columns reports reason" "ERROR:unsafe_task_dir" "$out"

echo "=== Test 8: unsupported layout is refused, not degraded ==="
mkdir -p "$TMP/bare"
out="$("$COLUMN_SH" list-columns --root "$TMP/bare" 2>&1)"; rc=$?
assert_exit_nonzero_rc "missing layout exits non-zero" "$rc"
assert_contains "missing layout reports reason" "ERROR:unsupported_layout" "$out"
assert_not_contains "must NOT invent the stock board" "COLUMN:now" "$out"

echo "=== Test 9: non-default --task-dir layout ==="
rm -rf "$PROJ"
build_tree "mytasks"
out="$("$COLUMN_SH" list-columns --root "$PROJ" --task-dir mytasks 2>&1)"; rc=$?
assert_eq "custom layout exits 0" "0" "$rc"
assert_contains "custom layout lists its columns" "COLUMN:c0|" "$out"
out="$("$COLUMN_SH" move --root "$PROJ" --task-dir mytasks --task 100 \
    --column c1 2>&1)"; rc=$?
assert_eq "custom layout move exits 0" "0" "$rc"
assert_contains "custom layout move wrote" "boardcol: c1" \
    "$(cat "$PROJ/mytasks/t100_alpha.md")"
# And the default layout genuinely does not exist, so this was not a fallback.
assert_dir_not_exists "no default layout present" "$PROJ/aitasks"

echo "=== Test 10: --root is honoured from an unrelated cwd ==="
out="$(cd "$TMP" && "$COLUMN_SH" list-columns --root "$PROJ" --task-dir mytasks 2>&1)"
assert_contains "works with cwd outside the project" "COLUMN:c0|" "$out"

echo ""
echo "=========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=========================="
[[ "$FAIL" -eq 0 ]] || exit 1
